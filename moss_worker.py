"""Run MOSS-Transcribe-Diarize in its isolated Transformers 5 environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import copy
import gc
import threading
from collections import Counter
from pathlib import Path


DEFAULT_PROMPT = (
    "请将音频转写为文本，每一段需以起始时间戳和说话人编号"
    "（[S01]、[S02]、[S03]…）开头，正文为对应的语音内容，"
    "并在段末标注结束时间戳，以清晰标明该段语音范围。"
)

# Application metadata, never passed as invented model.generate parameters.
INFERENCE_MODE = "full_context"
CACHE_VERSION = "moss-full-context-v1"
PROMPT_VERSION = "native-transcript-v1"
GENERATION_POLICY = {"tokens_per_second": 24, "minimum_output_tokens": 2048,
                     "context_reserve": 32, "do_sample": False,
                     "encoder_batch_size": 2, "oom_retries": 1}


def generation_budget(duration, input_tokens, context_limit):
    requested = max(GENERATION_POLICY["minimum_output_tokens"], math.ceil(duration * GENERATION_POLICY["tokens_per_second"]))
    available = int(context_limit) - int(input_tokens) - GENERATION_POLICY["context_reserve"]
    if available < GENERATION_POLICY["minimum_output_tokens"]:
        raise ValueError(f"整段输入上下文容量不足：input_tokens={input_tokens}, context_limit={context_limit}, available_output={available}")
    return min(requested, available), requested


def ending_assessment(generated_tokens, budget, last_token, eos_ids):
    eos_ids = eos_ids if isinstance(eos_ids, (list, tuple)) else [eos_ids]
    if generated_tokens >= budget:
        return "token_limit", False
    if generated_tokens and last_token in eos_ids:
        return "eos", True
    return "unexpected_stop", False


def audio_fingerprint(audio, sample_rate):
    import numpy as np
    digest = hashlib.sha256(f"float32-mono:{int(sample_rate)}:".encode())
    # Bound scratch memory while hashing the complete ordered task waveform.
    for start in range(0, len(audio), 1024 * 1024):
        digest.update(np.asarray(audio[start:start + 1024 * 1024], dtype="<f4").tobytes())
    return digest.hexdigest()


class ExecutionProgress:
    def __init__(self):
        self.started = time.monotonic()
        self.last_activity = self.started
        self.phase = "audio_preparation"
        self.tokens = 0
        self.stop = threading.Event()

    def emit(self, *, activity=True, **fields):
        if activity:
            self.last_activity = time.monotonic()
        row = {"phase": self.phase, "elapsed_seconds": round(time.monotonic() - self.started, 3),
               "last_activity_elapsed_seconds": round(self.last_activity - self.started, 3),
               "generated_tokens": self.tokens, "progress_percent": None, **fields}
        print("MOSS_EVENT " + json.dumps(row, ensure_ascii=False), flush=True)

    def set_phase(self, phase):
        self.phase = phase
        self.emit()

    def heartbeat(self):
        while not self.stop.wait(10):
            self.emit(activity=False, heartbeat=True)


def install_encoder_batching(model, batch_size, progress):
    """Batch the official Whisper encoder only, preserving all feature rows.

    The installed MOSS calls whisper_encoder(features, return_dict=True) and
    consumes last_hidden_state. Its mapping/merge/adaptor and decoder are intact.
    """
    import torch
    from transformers.modeling_outputs import BaseModelOutput
    encoder = model.model.whisper_encoder
    original = encoder.forward
    state = {"batch_size": batch_size}

    def forward(input_features, **kwargs):
        if not kwargs.get("return_dict") or kwargs.get("output_attentions") or kwargs.get("output_hidden_states"):
            return original(input_features, **kwargs)
        outputs = []
        for start in range(0, input_features.shape[0], state["batch_size"]):
            outputs.append(original(input_features[start:start + state["batch_size"]], **kwargs).last_hidden_state)
            progress.emit(encoder_feature_rows_done=min(input_features.shape[0], start + state["batch_size"]),
                          encoder_feature_rows_total=int(input_features.shape[0]))
        progress.set_phase("generation")
        return BaseModelOutput(last_hidden_state=torch.cat(outputs, dim=0))

    encoder.forward = forward
    return state


def generate_full_context(model, processor, audio, messages, device, dtype, progress, receipt):
    import torch
    from moss_transcribe_diarize.inference_utils import ProgressStreamer
    context_limit = int(model.config.text_config.max_position_embeddings)
    progress.set_phase("audio_encoding")
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    # Processor owns its 30s feature blocks and ordered audio_chunk_mapping.
    # Do not use truncation, VAD concatenation, or a shorter raw waveform.
    with torch.inference_mode():
        inputs = processor(text=text, audio=[audio], max_length=context_limit,
                           return_tensors="pt").to(device)
    prompt_len = int(inputs["attention_mask"][0].sum().item())
    budget, requested = generation_budget(len(audio) / processor.feature_extractor.sampling_rate, prompt_len, context_limit)
    receipt.update(input_tokens=prompt_len, max_new_tokens=budget, requested_output_tokens=requested,
                   context_limit=context_limit, processor_feature_chunk_count=int(inputs["input_features"].shape[0]))
    progress.emit(input_tokens=prompt_len, max_new_tokens=budget, context_limit=context_limit)
    config = copy.deepcopy(model.generation_config)
    config.max_new_tokens = budget
    config.do_sample = False
    config.num_beams = 1
    encoder_state = install_encoder_batching(model, GENERATION_POLICY["encoder_batch_size"], progress)

    def token_callback(count):
        progress.tokens = count
        progress.last_activity = time.monotonic()
        if count % 100 == 0:
            progress.emit()

    def attempt():
        receipt["generation_attempts"] += 1
        progress.tokens = 0
        progress.set_phase("audio_encoding")
        progress.emit(generation_attempt=receipt["generation_attempts"], encoder_batch_size=encoder_state["batch_size"])
        # Real generate invocations are counted here, including failed attempts.
        with torch.inference_mode(), torch.amp.autocast("cuda", dtype=dtype):
            return model.generate(**inputs, generation_config=config, streamer=ProgressStreamer(token_callback))

    try:
        outputs = attempt()
    except torch.cuda.OutOfMemoryError as exc:
        receipt["retries"].append({"reason": "cuda_oom", "detail": str(exc), "encoder_batch_size": 1})
        encoder_state["batch_size"] = 1
        # Release this attempt's traceback/tensors before retrying the SAME input.
        exc.__traceback__ = None
        gc.collect()
        torch.cuda.empty_cache()
        progress.emit(retry_reason="cuda_oom", encoder_batch_size=1)
        outputs = attempt()  # One bounded retry; never independent audio requests.
    generated = outputs[0][prompt_len:]
    count = int(generated.numel())
    reason, complete = ending_assessment(count, budget, int(generated[-1].item()) if count else None, config.eos_token_id)
    receipt.update(generated_tokens=count, end_reason=reason, complete=complete,
                   encoder_batch_size=encoder_state["batch_size"],
                   truncation_reasons=[] if complete else [reason])
    return processor.tokenizer.decode(generated, skip_special_tokens=True).strip()


def parsed_speaker_label(value, chunk_id):
    label = str(value).strip('[] ') if value is not None else ''
    if not label:
        raise RuntimeError(f'MOSS 第 {chunk_id} 块说话人标签解析失败：标签为空，未默认归入 S00。')
    return label


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio")
    parser.add_argument("--manifest")
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--checkpoint-dir", default="")
    parser.add_argument("--run-signature", default="")
    parser.add_argument("--task-audio-fingerprint", default="")
    return parser.parse_args()


def media_duration(path):
    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        return max(0.0, float(completed.stdout.strip()))
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


class ModelIntegrityError(RuntimeError):
    pass


class AudioInputAudit:
    """Observe the original processor input without decoding or altering it."""

    def __init__(self, processor, on_input=None):
        self.processor = processor
        self.on_input = on_input
        self.inputs = None

    def __getattr__(self, name):
        return getattr(self.processor, name)

    def __call__(self, *args, **kwargs):
        audios = kwargs.get("audio")
        if audios is not None and self.inputs is None:
            rate = int(self.processor.feature_extractor.sampling_rate)
            self.inputs = {
                "sampling_rate": rate,
                "sample_counts": [int(len(audio)) for audio in audios],
                "audio_seconds": [len(audio) / rate for audio in audios],
                "clock": "decoded_pcm_samples",
            }
            if self.on_input is not None:
                self.on_input(self.inputs)
        return self.processor(*args, **kwargs)


def _vendored_model_root():
    """Registered MODEL_ROOT: 2BYTEASR_MODEL_ROOT env, then runtime_paths.json."""
    override = os.environ.get("2BYTEASR_MODEL_ROOT", "").strip()
    if override and os.path.isdir(override):
        return override
    base = (Path(os.environ.get("LOCALAPPDATA") or Path.home())).resolve()
    config = (base / "2ByteASR" / "runtime_paths.json").resolve()
    try:
        with config.open(encoding="utf-8") as stream:
            payload = json.load(stream)
        candidate = str(payload.get("model_root") or "").strip()
        if candidate and os.path.isdir(candidate):
            return candidate
    except (OSError, ValueError):
        pass
    return ""


def _vendored_verify_model_files(model_name, model_root, *, install_root):
    """Minimal stand-in for twobyteasr.model_integrity.verify_model_files.

    Importing the package executes twobyteasr/__init__, whose service-chain
    side effects load the GUI bundle's cp310 .pyd files and break this 3.12
    worker ("Module use of python310.dll conflicts"). Same contract here:
    required files must exist inside the model directory, sha256-pinned
    files must match, and the location must be a known root.
    """
    lock_path = (Path(install_root) / "dependencies.lock.json").resolve()
    with lock_path.open(encoding="utf-8") as stream:
        lock = json.load(stream)
    try:
        spec = lock["models"][model_name]
    except KeyError as exc:
        raise ModelIntegrityError(f"依赖锁中没有模型：{model_name}") from exc
    target = Path(model_root).resolve()
    allowed = [(Path(install_root).resolve())]
    registered = _vendored_model_root()
    if registered:
        allowed.append(Path(registered).resolve())
    inside = any(target.is_relative_to(root) for root in allowed)
    if not inside and not target.is_dir():
        raise ModelIntegrityError(f"拒绝校验未知位置的模型：{target}")

    def _safe(relative):
        candidate = (target / relative).resolve()
        if candidate == target or candidate.is_relative_to(target):
            return candidate
        raise ModelIntegrityError(f"模型锁包含非法路径：{relative}")

    for relative in dict.fromkeys(spec.get("required_files", ())):
        candidate = _safe(relative)
        if not candidate.is_file():
            raise ModelIntegrityError(
                f"模型必需文件缺失：{candidate}\n"
                "请重新运行 download_models.bat，程序会断点续传并只补下载缺失文件。"
            )
    for relative, expected in (spec.get("sha256") or {}).items():
        candidate = _safe(relative)
        if not candidate.is_file():
            raise ModelIntegrityError(
                f"模型关键文件缺失：{candidate}\n"
                "请重新运行 download_models.bat，程序会断点续传并只补下载缺失文件。"
            )
        digest = hashlib.sha256()
        with candidate.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != str(expected).lower():
            raise ModelIntegrityError(
                f"模型文件校验失败，已拒绝加载：{candidate.name}。"
                f"请删除损坏文件 {candidate} 后重新运行 download_models.bat。"
            )
    return target


def resolve_model(requested, install_root):
    script_local = (Path(__file__).resolve().parent / "models" / "MOSS-Transcribe-Diarize")
    if (script_local / "config.json").is_file():
        return str(script_local)
    # Registered MODEL_ROOT: env override, then the persisted runtime_paths.json.
    override = os.environ.get("2BYTEASR_MODEL_ROOT", "").strip()
    if override:
        found = Path(override) / "MOSS-Transcribe-Diarize"
        if (found / "config.json").is_file():
            return str(found)
    base = (Path(os.environ.get("LOCALAPPDATA") or Path.home())).resolve()
    runtime_paths_file = (base / "2ByteASR" / "runtime_paths.json").resolve()
    try:
        with runtime_paths_file.open(encoding="utf-8") as stream:
            payload = json.load(stream)
        model_root = str(payload.get("model_root") or "").strip()
        if model_root:
            found = Path(model_root) / "MOSS-Transcribe-Diarize"
            if (found / "config.json").is_file():
                return str(found)
    except (OSError, ValueError):
        pass
    # Last resort: models shipped beside the install root.
    found = Path(install_root) / "models" / "MOSS-Transcribe-Diarize"
    if (found / "config.json").is_file():
        return str(found)
    return requested


def atomic_write_json(path, payload):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def load_chunk_checkpoint(checkpoint_dir, run_signature, job, job_index):
    checkpoint_dir = str(job.get("checkpoint_dir") or checkpoint_dir or "")
    run_signature = str(job.get("run_signature") or run_signature or "")
    if not checkpoint_dir or not run_signature:
        return None
    path = Path(checkpoint_dir) / f"chunk_{int(job.get('chunk_id', job_index)):03d}.json"
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if payload.get("run_signature") != run_signature:
            return None
        if abs(float(payload.get("offset", -1)) - float(job.get("offset", 0.0))) > 0.001:
            return None
        result = payload.get("result")
        if not isinstance(result, dict) or not result.get("segments"):
            return None
        return result
    except (OSError, ValueError, TypeError):
        return None


def save_chunk_checkpoint(checkpoint_dir, run_signature, result):
    checkpoint_dir = str(result.get("checkpoint_dir") or checkpoint_dir or "")
    run_signature = str(result.get("run_signature") or run_signature or "")
    if not checkpoint_dir or not run_signature:
        return
    path = Path(checkpoint_dir) / f"chunk_{int(result['chunk_id']):03d}.json"
    atomic_write_json(
        path,
        {
            "run_signature": run_signature,
            "offset": result["offset"],
            "result": result,
        },
    )


def main():
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    install_root = script_dir if (script_dir / "dependencies.lock.json").is_file() else script_dir.parent
    # Old block manifests must never execute, even through a direct CLI call.
    if args.manifest:
        jobs = json.loads(Path(args.manifest).read_text("utf8")).get("jobs", [])
        if len(jobs) != 1 or float(jobs[0].get("offset", 0)) != 0:
            raise ValueError("MOSS full_context 仅允许一个从任务0秒开始的完整音频请求；旧分块清单已停用。")
        args.audio = jobs[0]["audio"]
    else:
        jobs = [{"audio": args.audio, "offset": 0}]
    if not args.audio:
        raise ValueError("需要完整任务 --audio。")
    module_cache = Path(args.output).resolve().parent / ".hf_modules_cache"
    module_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_MODULES_CACHE", str(module_cache))
    progress = ExecutionProgress()
    receipt = {"inference_mode": INFERENCE_MODE, "cache_version": CACHE_VERSION,
               "application_chunk_count": 0, "worker_pids": [os.getpid()], "worker_count": len({os.getpid()}),
               "generation_attempts": 0, "retries": [], "cache_hit": False,
               "input_tokens": None, "max_new_tokens": None, "generated_tokens": None,
               "attention_backend": None, "dtype": None, "complete": False}
    payload = {"inference_mode": INFERENCE_MODE, "cache_version": CACHE_VERSION,
               "title": args.title, "execution": receipt, "chunks": []}
    heartbeat = threading.Thread(target=progress.heartbeat, daemon=True)
    heartbeat.start()
    try:
        import numpy as np
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoProcessor
        from moss_transcribe_diarize import parse_transcript
        from moss_transcribe_diarize.inference_utils import build_transcription_messages, load_audio_item
        if not torch.cuda.is_available():
            raise RuntimeError("MOSS 当前工作流要求 CUDA GPU。")
        device = torch.device("cuda:0")
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        receipt.update(dtype=str(dtype), torch_version=torch.__version__,
                       transformers_version=transformers.__version__, runtime=sys.executable)
        model_source = resolve_model(args.model, install_root)
        payload["model"] = model_source
        _vendored_verify_model_files("moss", model_source, install_root=install_root)
        if Path(args.audio).suffix.lower() == ".npy":
            audio = np.load(args.audio, mmap_mode="r", allow_pickle=False)
            if audio.ndim != 1 or audio.dtype != np.dtype("float32"):
                raise ValueError("任务音频必须是完整 mono float32 PCM。")
        else:
            audio = load_audio_item(args.audio, sampling_rate=16000)
        if not len(audio) or not np.isfinite(audio).all():
            raise ValueError("任务音频为空或含非有限样本。")
        fingerprint = audio_fingerprint(audio, 16000)
        receipt.update(task_audio_duration=len(audio) / 16000, sample_rate=16000,
                       sample_count=len(audio), task_audio_fingerprint=fingerprint,
                       application_chunk_count=len(jobs), clock="task_pcm_zero")
        if args.task_audio_fingerprint and fingerprint != args.task_audio_fingerprint:
            raise ValueError("worker完整任务音频指纹与调度器不一致。")
        progress.emit(**receipt)
        progress.set_phase("model_loading")
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        model_started = time.monotonic()
        model = AutoModelForCausalLM.from_pretrained(model_source, trust_remote_code=True,
                    dtype="auto", attn_implementation="sdpa").to(dtype=dtype).to(device).eval()
        processor = AutoProcessor.from_pretrained(model_source, trust_remote_code=True)
        if int(processor.feature_extractor.sampling_rate) != 16000:
            raise ValueError("MOSS processor采样率不匹配任务16k时钟。")
        receipt.update(attention_backend={"model": model.config._attn_implementation,
                       "text": model.config.text_config._attn_implementation,
                       "audio": model.config.audio_config._attn_implementation},
                       model_load_seconds=round(time.monotonic() - model_started, 3))
        messages = build_transcription_messages(args.audio, prompt=DEFAULT_PROMPT)
        raw_text = generate_full_context(model, processor, audio, messages, device, dtype, progress, receipt)
        payload["raw_text"] = raw_text
        # Preserve native raw output even if parsing fails.
        atomic_write_json(args.output, payload)
        progress.set_phase("parsing")
        segments = []
        for segment in parse_transcript(raw_text):
            text = str(segment.text).strip()
            if text:
                start, end = float(segment.start), float(segment.end)
                if start < 0 or end <= start or end > receipt["task_audio_duration"] + 1:
                    receipt["complete"] = False
                    receipt.setdefault("truncation_reasons", []).append("invalid_timestamp")
                segments.append({"start": start, "end": end,
                                 "speaker": parsed_speaker_label(segment.speaker, 1), "text": text})
        if not segments:
            raise RuntimeError("MOSS 整段输出无法解析为说话人时间段；原始输出已保留。")
        segments.sort(key=lambda row: (row["start"], row["end"]))
        # A parser can silently skip an unfinished final clause: retain a review flag.
        import re
        if not re.search(r"\[[0-9]+(?:\.[0-9]+)?\]\s*$", raw_text):
            receipt["complete"] = False
            receipt.setdefault("truncation_reasons", []).append("unfinished_transcript_tail")
        receipt.update(raw_segment_count=len(segments),
                       raw_speaker_distribution=dict(Counter(row["speaker"] for row in segments)),
                       last_transcript_end=max(row["end"] for row in segments))
        chunk = {"chunk_id": 1, "offset": 0.0, "duration": receipt["task_audio_duration"],
                 "audio_input": {"sampling_rate": 16000, "sample_counts": [len(audio)],
                                 "audio_seconds": [len(audio) / 16000], "clock": "task_pcm_zero"},
                 "raw_text": raw_text, "segments": segments,
                 "prompt_tokens": receipt["input_tokens"], "max_new_tokens": receipt["max_new_tokens"],
                 "generated_tokens": receipt["generated_tokens"]}
        payload["chunks"] = [chunk]
        payload["generated_tokens"] = receipt["generated_tokens"]
        progress.set_phase("handoff")
    except Exception as exc:
        receipt.update(failure_stage=progress.phase, end_reason=type(exc).__name__,
                       error=str(exc), complete=False)
        progress.emit(**receipt)
        raise
    finally:
        receipt["elapsed_seconds"] = round(time.monotonic() - progress.started, 3)
        try:
            import torch
            receipt["peak_allocated_gb"] = round(torch.cuda.max_memory_allocated() / 1024**3, 3)
            receipt["peak_reserved_gb"] = round(torch.cuda.max_memory_reserved() / 1024**3, 3)
        except Exception:
            pass
        payload["performance"] = {key: receipt.get(key) for key in ("model_load_seconds", "elapsed_seconds", "peak_allocated_gb", "peak_reserved_gb")}
        atomic_write_json(args.output, payload)
        progress.stop.set()
        heartbeat.join(timeout=1)
    progress.set_phase("completed" if receipt["complete"] else "needs_review")
    progress.emit(**receipt)


if __name__ == "__main__":
    main()
