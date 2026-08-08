import gc
import json
import math
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from statistics import median

import numpy as np

from twobyteasr.processes import hidden_subprocess_kwargs
from twobyteasr.runtime import get_runtime_context
from twobyteasr.pipeline_runtime import (
    complete_media_run,
    finalize_cues,
    run_parallel_stages,
)


PIPELINE_BUILD_ID = "2026.08.05-v7.14-strict-length-number-style"


_CANCELLATION_TOKEN = None


MOSS_MODEL = "OpenMOSS-Team/MOSS-Transcribe-Diarize"
MOSS_TIMEOUT_SECONDS = 7200
MOSS_NO_PROGRESS_TIMEOUT_SECONDS = 900
MOSS_CHUNK_SECONDS = 180.0
MOSS_CHUNK_OVERLAP_SECONDS = 20.0
MOSS_SINGLE_PASS_MAX_SECONDS = 210.0
MOSS_SPEAKER_PAD_SECONDS = 0.30
MOSS_OVERLAP_CONFLICT_SECONDS = 0.15
# 自动模式最多保留四位持续出现的主播；手动模式允许到六位。
# 二者分开，避免为了三主播直播而把大量一次性节目/角色声全部写入成片。
MOSS_AUTO_MAX_HOST_SPEAKERS = 4
MOSS_MAX_EXPECTED_SPEAKERS = 6
MOSS_HOST_MIN_SPAN_RATIO = 0.80
MOSS_HOST_MIN_ACTIVE_BIN_RATIO = 0.75
FIRERED_LLM_MIN_GPU_GB = 24.0
SPEAKER_EMBEDDING_MIN_SIMILARITY = 0.42
SPEAKER_EMBEDDING_MAX_AUDIO_SECONDS = 14.0
REGISTERED_HOST_MIN_SIMILARITY = 0.55
REGISTERED_HOST_MIN_MARGIN = 0.05
REGISTERED_HOST_MIN_SEGMENTS = 2
TRANSIENT_HOST_MAX_LABEL_SEGMENTS = 3
TRANSIENT_HOST_MAX_DURATION_SECONDS = 2.20
TRANSIENT_HOST_MAX_CHARS = 8
TRANSIENT_HOST_MIN_CROSS_SPEAKER_OVERLAP = 0.12
TRANSIENT_HOST_NEARBY_PAD_SECONDS = 0.12
TRANSIENT_HOST_MIN_SIMILARITY = 0.12
TRANSIENT_HOST_MIN_MARGIN = 0.055


def set_cancellation_token(token):
    global _CANCELLATION_TOKEN
    _CANCELLATION_TOKEN = token


def verify_pipeline_contract(legacy, launcher_path, launcher_build_id):
    """确保入口与两个核心模块来自同一目录、同一构建版本。"""
    expected_root = os.path.normcase(
        os.path.realpath(os.path.dirname(os.path.abspath(launcher_path)))
    )
    entries = (
        ("auto_asr", launcher_path, launcher_build_id),
        ("subtitle_core", getattr(legacy, "__file__", ""), getattr(legacy, "PIPELINE_BUILD_ID", "")),
        ("moss_firered_pipeline", __file__, PIPELINE_BUILD_ID),
    )
    normalized = []
    problems = []
    for name, path, build_id in entries:
        resolved = os.path.realpath(os.path.abspath(path)) if path else ""
        root = os.path.normcase(os.path.dirname(resolved)) if resolved else ""
        normalized.append((name, resolved, str(build_id or "")))
        if not resolved or not os.path.isfile(resolved):
            problems.append(f"{name} 路径无效：{resolved or '<missing>'}")
        elif root != expected_root:
            problems.append(f"{name} 不在入口目录：{resolved}")

    build_ids = {build_id for _, _, build_id in normalized if build_id}
    if len(build_ids) != 1 or any(not build_id for _, _, build_id in normalized):
        detail = "；".join(f"{name}={build_id or '<missing>'}" for name, _, build_id in normalized)
        problems.append(f"构建版本不一致：{detail}")
    if problems:
        raise RuntimeError("流水线文件自检失败：\n- " + "\n- ".join(problems))

    print(f"[流水线版本] {normalized[0][2]}")
    for name, path, _ in normalized:
        print(f"   {name}: {path}")
    return {
        "build_id": normalized[0][2],
        "paths": {name: path for name, path, _ in normalized},
    }


def _script_paths(legacy):
    script_dir = legacy.SCRIPT_DIR
    return {
        "moss_python": os.path.join(script_dir, ".venv-moss", "Scripts", "python.exe"),
        "moss_worker": os.path.join(script_dir, "moss_worker.py"),
        "firered_llm_worker": os.path.join(script_dir, "firered_llm_worker.py"),
        "firered_vad": os.path.join(script_dir, "models", "FireRedVAD", "VAD"),
        "firered_llm": os.path.join(script_dir, "models", "FireRedASR2-LLM"),  # 可选本地复核；不在 dependencies.lock.json，需手动放置模型
        "speaker_embedding": os.path.join(script_dir, "models", "spkrec-ecapa-voxceleb"),
    }


def _path_signature(path):
    if not os.path.exists(path):
        return {"path": os.path.normcase(os.path.abspath(path)), "missing": True}
    if os.path.isfile(path):
        stat = os.stat(path)
        return {"path": os.path.normcase(os.path.abspath(path)), "size": stat.st_size, "mtime": stat.st_mtime_ns}
    newest = 0
    count = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                stat = os.stat(os.path.join(root, name))
            except OSError:
                continue
            count += 1
            newest = max(newest, stat.st_mtime_ns)
    return {"path": os.path.normcase(os.path.abspath(path)), "files": count, "mtime": newest}


def check_runtime(legacy):
    legacy.check_runtime()
    from twobyteasr.model_integrity import verify_model_files
    from importlib.metadata import PackageNotFoundError, version as package_version

    try:
        package_version("speechbrain")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "缺少说话人分块拼接依赖 speechbrain。请运行：python -m pip install speechbrain==1.0.3"
        ) from exc
    paths = _script_paths(legacy)
    required = (
        (legacy.FIRERED_SOURCE_DIR, "FireRedASR2S 源码"),
        (legacy.FIRERED_MODEL_DIR, "FireRedASR2-AED 模型"),
        (paths["firered_vad"], "FireRedVAD 模型"),
        (paths["moss_python"], "MOSS 独立 Python 环境"),
        (paths["moss_worker"], "MOSS 子进程桥接脚本"),
        (paths["speaker_embedding"], "ECAPA 说话人嵌入模型"),
    )
    missing = []
    for path, label in required:
        if not os.path.exists(path):
            missing.append(f"{label}（{os.path.normcase(os.path.abspath(path))}）")
    if missing:
        raise RuntimeError(
            "缺少新流水线组件：" + "、".join(missing)
            + "。\n请运行 setup_2byteasr.bat 重新配置，或直接运行 download_models.bat 下载模型。"
        )
    verify_model_files("moss", os.path.join(legacy.SCRIPT_DIR, "models", "MOSS-Transcribe-Diarize"))
    verify_model_files("firered_vad", os.path.join(legacy.SCRIPT_DIR, "models", "FireRedVAD"))
    verify_model_files("firered_aed", legacy.FIRERED_MODEL_DIR)
    verify_model_files("speaker_embedding", paths["speaker_embedding"])
    status = getattr(legacy, "host_voiceprint_status_summary", None)
    if callable(status):
        print(f"   [主播声纹] {status()}")


def _stop_process_tree(process):
    """只终止本次启动的子进程树，避免超时后遗留 GPU 进程。"""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            **hidden_subprocess_kwargs(),
        )
        # 受限环境下 taskkill 可能无法结束根进程；直接 kill 作为立即兜底。
        if process.poll() is None:
            process.kill()
    else:
        process.kill()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _cancel_requested():
    if _CANCELLATION_TOKEN is not None and _CANCELLATION_TOKEN.is_cancelled:
        return True
    if os.name != "nt" or not sys.stdin or not sys.stdin.isatty():
        return False
    try:
        import msvcrt

        if msvcrt.kbhit():
            return msvcrt.getwch().lower() == "q"
    except (ImportError, OSError):
        pass
    return False


def _run_streaming_worker(
    command,
    timeout_seconds,
    no_progress_seconds=MOSS_NO_PROGRESS_TIMEOUT_SECONDS,
    *,
    abort_event=None,
    line_prefix="",
):
    # Python 3.12 子进程的 stdout 接到 PIPE 后会回落到 Windows 本地代码页；
    # 主进程按 UTF-8 解码时就会把中文进度替换成问号/�。显式固定双方编码。
    worker_env = os.environ.copy()
    worker_env["PYTHONIOENCODING"] = "utf-8"
    worker_env["PYTHONUTF8"] = "1"
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=worker_env,
        **hidden_subprocess_kwargs(),
    )
    if sys.stdin and sys.stdin.isatty():
        print("      MOSS 运行中可按 Q 安全取消本次任务。", flush=True)
    output_queue = queue.Queue()

    def read_output():
        try:
            for line in process.stdout:
                output_queue.put(line.rstrip())
        finally:
            output_queue.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    lines = []
    finished_output = False
    started = time.monotonic()
    last_output = started
    try:
        while process.poll() is None or not finished_output:
            now = time.monotonic()
            if now - started > timeout_seconds:
                raise TimeoutError(f"MOSS 子进程超过 {timeout_seconds / 60:.0f} 分钟未完成。")
            if process.poll() is None and now - last_output > no_progress_seconds:
                raise TimeoutError(
                    f"MOSS 连续 {no_progress_seconds / 60:.0f} 分钟没有任何进度输出，"
                    "已停止疑似卡死进程；已完成分块可在下次继续。"
                )
            if _cancel_requested():
                raise KeyboardInterrupt("用户按 Q 取消 MOSS。")
            if abort_event is not None and abort_event.is_set():
                raise RuntimeError("同组 MOSS 工作进程失败，已停止当前进程。")
            try:
                line = output_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if line is None:
                finished_output = True
                continue
            last_output = time.monotonic()
            if line:
                lines.append(line)
                print(f"      MOSS{line_prefix}: {line}", flush=True)
        reader.join(timeout=2.0)
        return process.returncode, lines
    except BaseException:
        _stop_process_tree(process)
        reader.join(timeout=2.0)
        raise
    finally:
        if process.poll() is None:
            _stop_process_tree(process)


def _chunk_moss_audio(shared_audio, temp_dir, legacy):
    duration = len(shared_audio) / legacy.AUDIO_SAMPLE_RATE
    if duration <= MOSS_SINGLE_PASS_MAX_SECONDS:
        return []
    jobs = []
    step = MOSS_CHUNK_SECONDS - MOSS_CHUNK_OVERLAP_SECONDS
    offset = 0.0
    chunk_id = 0
    while offset < duration - 0.01:
        chunk_id += 1
        end = min(duration, offset + MOSS_CHUNK_SECONDS)
        left = int(round(offset * legacy.AUDIO_SAMPLE_RATE))
        right = int(round(end * legacy.AUDIO_SAMPLE_RATE))
        wav_path = os.path.join(temp_dir, f"moss_chunk_{chunk_id:03d}.wav")
        legacy.write_pcm16_wav(wav_path, shared_audio[left:right])
        jobs.append(
            {
                "chunk_id": chunk_id,
                "audio": wav_path,
                "offset": offset,
                "duration": end - offset,
                "global_end": end,
            }
        )
        if end >= duration - 0.01:
            break
        offset += step
    return jobs


def _moss_parallel_worker_count(jobs, legacy, total_vram_gb=None):
    """Return a conservative MOSS worker count without changing inference output."""
    configured = max(1, min(2, int(getattr(legacy, "MOSS_PARALLEL_WORKERS", 1))))
    if configured < 2 or len(jobs) < 2:
        return 1
    if total_vram_gb is None:
        total_vram_gb = _cuda_total_memory_gb()
    minimum = float(getattr(legacy, "MOSS_PARALLEL_MIN_VRAM_GB", 14.0))
    if total_vram_gb < minimum:
        return 1
    return min(configured, len(jobs))


def _read_moss_worker_payload(output_path, returncode, output_lines, label):
    if returncode != 0 or not os.path.isfile(output_path):
        detail = "\n".join(output_lines[-30:])[-3000:]
        raise RuntimeError(f"{label}失败（退出码 {returncode}）：{detail}")
    with open(output_path, "r", encoding="utf-8") as file:
        payload = json.load(file)
    if not payload.get("chunks"):
        raise RuntimeError(f"{label}没有返回任何分块。")
    return payload


def _run_moss_manifest_jobs(jobs, temp_dir, paths, legacy, title, *, force_workers=None):
    """Run disjoint MOSS chunks in one or two isolated processes and combine them."""
    worker_count = (
        max(1, min(2, int(force_workers)))
        if force_workers is not None
        else _moss_parallel_worker_count(jobs, legacy)
    )

    def run_partition(worker_index, partition, abort_event=None):
        manifest_path = os.path.join(temp_dir, f"manifest_{worker_index:02d}.json")
        output_path = os.path.join(temp_dir, f"moss_{worker_index:02d}.json")
        with open(manifest_path, "w", encoding="utf-8") as file:
            json.dump({"jobs": partition}, file, ensure_ascii=False)
        command = [
            paths["moss_python"],
            paths["moss_worker"],
            "--manifest",
            manifest_path,
            "--output",
            output_path,
            "--model",
            MOSS_MODEL,
            "--title",
            title,
        ]
        returncode, output_lines = _run_streaming_worker(
            command,
            MOSS_TIMEOUT_SECONDS,
            abort_event=abort_event,
            line_prefix=(f"[{worker_index}/{worker_count}]" if worker_count > 1 else ""),
        )
        return _read_moss_worker_payload(
            output_path,
            returncode,
            output_lines,
            f"MOSS 工作进程 {worker_index}",
        )

    if worker_count == 1:
        return run_partition(1, jobs)

    print(
        f"   [并行加速] MOSS {len(jobs)} 个分块由 {worker_count} 个 GPU 进程并行处理。"
    )
    recorder = getattr(legacy, "record_run_event", None)
    if callable(recorder):
        recorder(
            "moss_chunks_parallel",
            chunks=len(jobs),
            workers=worker_count,
            total_vram_gb=round(_cuda_total_memory_gb(), 2),
        )
    abort_event = threading.Event()
    partitions = [jobs[index::worker_count] for index in range(worker_count)]
    payloads = []
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(
            max_workers=worker_count, thread_name_prefix="moss-gpu"
        ) as pool:
            futures = [
                pool.submit(run_partition, index + 1, partition, abort_event)
                for index, partition in enumerate(partitions)
            ]
            for future in as_completed(futures):
                try:
                    payloads.append(future.result())
                except BaseException:
                    abort_event.set()
                    raise
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        # A failed process may already have produced valid per-chunk checkpoints.
        # Retrying once with one model is both safer on low free VRAM and cheap.
        print(f"   [显存回退] MOSS 双路并行失败，改用单路续跑：{exc}")
        if callable(recorder):
            recorder("moss_chunks_parallel_fallback", reason=str(exc))
        return _run_moss_manifest_jobs(
            jobs,
            temp_dir,
            paths,
            legacy,
            title,
            force_workers=1,
        )

    chunks = []
    generated_tokens = 0
    worker_performance = []
    for payload in payloads:
        chunks.extend(payload.get("chunks", []))
        generated_tokens += int(payload.get("generated_tokens", 0))
        worker_performance.append(payload.get("performance", {}))
    chunks.sort(
        key=lambda item: (
            str(item.get("group_id", "default")),
            int(item.get("chunk_id", 0)),
            float(item.get("offset", 0.0)),
        )
    )
    return {
        "model": payloads[0].get("model", MOSS_MODEL),
        "title": title,
        "chunks": chunks,
        "generated_tokens": generated_tokens,
        "performance": {
            "parallel_workers": worker_count,
            "workers": worker_performance,
        },
    }


def _speaker_match_score(current_segments, previous_segments, local_speaker, global_speaker, legacy):
    score = 0.0
    for current in current_segments:
        if current["speaker"] != local_speaker:
            continue
        for previous in previous_segments:
            if previous["speaker"] != global_speaker:
                continue
            time_score = _time_overlap(
                float(current["start"]),
                float(current["end"]),
                float(previous["start"]),
                float(previous["end"]),
            )
            center_gap = abs(
                (float(current["start"]) + float(current["end"])) / 2.0
                - (float(previous["start"]) + float(previous["end"])) / 2.0
            )
            if time_score <= 0.0 and center_gap > 1.0:
                continue
            similarity = legacy.asr_consensus_similarity(current["text"], previous["text"])
            score += similarity * (0.20 + time_score) * max(0.20, 1.0 - center_gap / 2.0)
    return score


def _map_chunk_speakers(
    chunk_segments,
    previous_segments,
    known_speakers,
    next_speaker_id,
    legacy,
    local_embeddings=None,
    global_embeddings=None,
):
    local_speakers = sorted({item["speaker"] for item in chunk_segments})
    if not previous_segments:
        mapping = {}
        for local in local_speakers:
            mapping[local] = f"S{next_speaker_id:02d}"
            next_speaker_id += 1
        return mapping, next_speaker_id

    mapping = {}
    used_global = set()
    local_embeddings = local_embeddings or {}
    global_embeddings = global_embeddings or {}

    # MOSS 每块会重新编号；声纹相似度先负责身份延续，文字重叠只作后备。
    voice_candidates = []
    for local in local_speakers:
        local_embedding = local_embeddings.get(local)
        if local_embedding is None:
            continue
        for global_speaker, global_embedding in global_embeddings.items():
            similarity = float(np.dot(local_embedding, global_embedding))
            if similarity >= SPEAKER_EMBEDDING_MIN_SIMILARITY:
                voice_candidates.append((similarity, local, global_speaker))
    for _, local, global_speaker in sorted(voice_candidates, reverse=True):
        if local in mapping or global_speaker in used_global:
            continue
        mapping[local] = global_speaker
        used_global.add(global_speaker)

    candidates = []
    previous_speakers = sorted({item["speaker"] for item in previous_segments})
    for local in local_speakers:
        if local in mapping:
            continue
        for global_speaker in previous_speakers:
            if global_speaker in used_global:
                continue
            score = _speaker_match_score(
                chunk_segments, previous_segments, local, global_speaker, legacy
            )
            if score >= 0.18:
                candidates.append((score, local, global_speaker))
    for _, local, global_speaker in sorted(candidates, reverse=True):
        if local in mapping or global_speaker in used_global:
            continue
        mapping[local] = global_speaker
        used_global.add(global_speaker)

    # 重叠区恰好静音时没有文字可比；同名标签作为保守后备，避免主播被切成多个全局标签。
    for local in local_speakers:
        if local not in mapping and local in known_speakers and local not in used_global:
            mapping[local] = local
            used_global.add(local)
    for local in local_speakers:
        if local in mapping:
            continue
        while f"S{next_speaker_id:02d}" in known_speakers or f"S{next_speaker_id:02d}" in used_global:
            next_speaker_id += 1
        mapping[local] = f"S{next_speaker_id:02d}"
        used_global.add(mapping[local])
        next_speaker_id += 1
    return mapping, next_speaker_id


def _speaker_group_signal(chunk, local_speaker, chunk_index, chunk_count, audio_seconds, shared_audio, legacy):
    offset = float(chunk.get("offset", 0.0))
    duration = float(chunk.get("duration", 0.0))
    owned_start = offset if chunk_index == 0 else offset + MOSS_CHUNK_OVERLAP_SECONDS / 2.0
    chunk_end = min(audio_seconds, offset + duration)
    owned_end = chunk_end if chunk_index == chunk_count - 1 else chunk_end - MOSS_CHUNK_OVERLAP_SECONDS / 2.0
    rows = []
    for raw in chunk.get("segments", []):
        if str(raw.get("speaker") or "S00").strip("[] ") != local_speaker:
            continue
        start = max(0.0, offset + float(raw["start"]))
        end = min(audio_seconds, max(start + 0.01, offset + float(raw["end"])))
        center = (start + end) / 2.0
        if owned_start <= center < owned_end or (chunk_index == chunk_count - 1 and center <= owned_end):
            rows.append((start, end))
    rows.sort(key=lambda item: min(4.0, item[1] - item[0]), reverse=True)
    pieces = []
    remaining = int(SPEAKER_EMBEDDING_MAX_AUDIO_SECONDS * legacy.AUDIO_SAMPLE_RATE)
    for start, end in rows:
        left = max(0, int((start + 0.08) * legacy.AUDIO_SAMPLE_RATE))
        right = min(len(shared_audio), int((end - 0.08) * legacy.AUDIO_SAMPLE_RATE))
        if right - left < int(0.35 * legacy.AUDIO_SAMPLE_RATE):
            continue
        piece = np.asarray(shared_audio[left:right], dtype=np.float32)[:remaining]
        pieces.append(piece)
        remaining -= len(piece)
        if remaining <= 0:
            break
    if not pieces:
        return None
    signal = np.concatenate(pieces)
    peak = float(np.max(np.abs(signal)))
    return signal / max(peak, 1e-4)


def _compute_chunk_speaker_embeddings(chunks, shared_audio, audio_seconds, legacy):
    if len(chunks) <= 1 or shared_audio is None:
        return {}
    paths = _script_paths(legacy)
    model_dir = paths["speaker_embedding"]
    if not os.path.isfile(os.path.join(model_dir, "embedding_model.ckpt")):
        raise RuntimeError("缺少 ECAPA 声纹模型，已停止分块说话人拼接。")
    try:
        import warnings

        import torch
        import torchaudio

        # SpeechBrain 1.0.3 仍查询已被新版 torchaudio 移除的旧接口；
        # 本流程直接传入张量，不调用其音频加载器，因此声明 soundfile 后端即可兼容。
        if not hasattr(torchaudio, "list_audio_backends"):
            torchaudio.list_audio_backends = lambda: ["soundfile"]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from speechbrain.inference.speaker import EncoderClassifier
            from speechbrain.utils.fetching import LocalStrategy

            encoder = EncoderClassifier.from_hparams(
                source=model_dir,
                savedir=model_dir,
                overrides={"pretrained_path": model_dir},
                local_strategy=LocalStrategy.NO_LINK,
                run_opts={"device": "cpu"},
            )
        keys = []
        signals = []
        for chunk_index, chunk in enumerate(chunks):
            local_speakers = sorted(
                {str(item.get("speaker") or "S00").strip("[] ") for item in chunk.get("segments", [])}
            )
            for local_speaker in local_speakers:
                signal = _speaker_group_signal(
                    chunk,
                    local_speaker,
                    chunk_index,
                    len(chunks),
                    audio_seconds,
                    shared_audio,
                    legacy,
                )
                if signal is None:
                    continue
                keys.append((chunk_index, local_speaker))
                signals.append(torch.from_numpy(signal))
        if not signals:
            return {}
        lengths = torch.tensor([len(item) for item in signals], dtype=torch.float32)
        padded = torch.nn.utils.rnn.pad_sequence(signals, batch_first=True)
        relative_lengths = lengths / padded.shape[1]
        with torch.inference_mode():
            matrix = encoder.encode_batch(padded, relative_lengths).squeeze(1)
            matrix = torch.nn.functional.normalize(matrix, dim=-1).cpu().numpy()
        print(f"   [完成] ECAPA 声纹：{len(keys)} 个分块说话人嵌入。")
        return {key: vector for key, vector in zip(keys, matrix)}
    except Exception as exc:
        raise RuntimeError(f"ECAPA 声纹失败，已停止以避免说话人串号：{exc}") from exc
    finally:
        gc.collect()


def _transient_host_candidates(moss_segments, host_speakers, legacy):
    """只挑出极短、极少出现且压在另一说话人上的临时 MOSS 标签。"""
    label_counts = {}
    for row in moss_segments:
        speaker = str(row.get("speaker") or "S00")
        label_counts[speaker] = label_counts.get(speaker, 0) + 1
    candidates = []
    for row in moss_segments:
        speaker = str(row.get("speaker") or "S00")
        if speaker in host_speakers or label_counts.get(speaker, 0) > TRANSIENT_HOST_MAX_LABEL_SEGMENTS:
            continue
        start = float(row["start"])
        end = float(row["end"])
        if end - start < 0.45 or end - start > TRANSIENT_HOST_MAX_DURATION_SECONDS:
            continue
        text = legacy.content_only(row.get("text", ""))
        if not text or len(text) > TRANSIENT_HOST_MAX_CHARS:
            continue
        if not any(
            other is not row
            and str(other.get("speaker") or "S00") != speaker
            and (
                _time_overlap(start, end, float(other["start"]), float(other["end"]))
                >= TRANSIENT_HOST_MIN_CROSS_SPEAKER_OVERLAP
                or (
                    float(other["end"]) >= start - TRANSIENT_HOST_NEARBY_PAD_SECONDS
                    and float(other["start"]) <= end + TRANSIENT_HOST_NEARBY_PAD_SECONDS
                )
            )
            for other in moss_segments
        ):
            continue
        candidates.append(row)
    return candidates


def _speaker_signal_from_rows(rows, shared_audio, legacy, max_seconds, trim_seconds=0.08):
    pieces = []
    remaining = int(max_seconds * legacy.AUDIO_SAMPLE_RATE)
    for row in rows:
        start = float(row["start"])
        end = float(row["end"])
        left = max(0, int((start + trim_seconds) * legacy.AUDIO_SAMPLE_RATE))
        right = min(len(shared_audio), int((end - trim_seconds) * legacy.AUDIO_SAMPLE_RATE))
        if right - left < int(0.35 * legacy.AUDIO_SAMPLE_RATE):
            left = max(0, int(start * legacy.AUDIO_SAMPLE_RATE))
            right = min(len(shared_audio), int(end * legacy.AUDIO_SAMPLE_RATE))
        if right - left < int(0.30 * legacy.AUDIO_SAMPLE_RATE):
            continue
        piece = np.asarray(shared_audio[left:right], dtype=np.float32)[:remaining]
        if not len(piece):
            break
        pieces.append(piece)
        remaining -= len(piece)
        if remaining <= 0:
            break
    if not pieces:
        return None
    signal = np.concatenate(pieces)
    peak = float(np.max(np.abs(signal)))
    return signal / max(peak, 1e-4)


def _clean_host_prototype_signal(moss_segments, host_speaker, shared_audio, legacy):
    rows = []
    for row in moss_segments:
        if str(row.get("speaker") or "S00") != host_speaker:
            continue
        start = float(row["start"])
        end = float(row["end"])
        if end - start < 0.75:
            continue
        if any(
            other is not row
            and str(other.get("speaker") or "S00") != host_speaker
            and _time_overlap(start, end, float(other["start"]), float(other["end"]))
            >= TRANSIENT_HOST_MIN_CROSS_SPEAKER_OVERLAP
            for other in moss_segments
        ):
            continue
        rows.append(row)
    rows.sort(key=lambda row: float(row["end"]) - float(row["start"]), reverse=True)
    return _speaker_signal_from_rows(
        rows,
        shared_audio,
        legacy,
        SPEAKER_EMBEDDING_MAX_AUDIO_SECONDS,
    )


def _encode_speaker_signals(encoder, signals):
    import torch

    tensors = [torch.from_numpy(np.asarray(signal, dtype=np.float32)) for signal in signals]
    lengths = torch.tensor([len(item) for item in tensors], dtype=torch.float32)
    padded = torch.nn.utils.rnn.pad_sequence(tensors, batch_first=True)
    with torch.inference_mode():
        matrix = encoder.encode_batch(padded, lengths / padded.shape[1]).squeeze(1)
        matrix = torch.nn.functional.normalize(matrix, dim=-1).cpu().numpy()
    return matrix


def _rescue_transient_host_segments(moss_segments, host_speakers, shared_audio, legacy):
    """以双重保守门槛找回重叠时被 MOSS 临时拆出的主播短句。"""
    if shared_audio is None or len(host_speakers) < 2:
        return 0
    candidates = _transient_host_candidates(moss_segments, host_speakers, legacy)
    if not candidates:
        return 0
    prototype_signals = []
    usable_hosts = []
    for host_speaker in host_speakers:
        signal = _clean_host_prototype_signal(
            moss_segments, host_speaker, shared_audio, legacy
        )
        if signal is None:
            continue
        usable_hosts.append(host_speaker)
        prototype_signals.append(signal)
    if len(usable_hosts) < 2:
        print("   [声纹保守补漏] 主播干净声纹不足，跳过临时标签认领。")
        return 0
    candidate_rows = []
    candidate_signals = []
    for row in candidates:
        signal = _speaker_signal_from_rows(
            [row],
            shared_audio,
            legacy,
            TRANSIENT_HOST_MAX_DURATION_SECONDS,
        )
        if signal is None:
            continue
        candidate_rows.append(row)
        candidate_signals.append(signal)
    if not candidate_signals:
        return 0
    paths = _script_paths(legacy)
    model_dir = paths["speaker_embedding"]
    try:
        import warnings
        import torchaudio

        if not hasattr(torchaudio, "list_audio_backends"):
            torchaudio.list_audio_backends = lambda: ["soundfile"]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from speechbrain.inference.speaker import EncoderClassifier
            from speechbrain.utils.fetching import LocalStrategy

            encoder = EncoderClassifier.from_hparams(
                source=model_dir,
                savedir=model_dir,
                overrides={"pretrained_path": model_dir},
                local_strategy=LocalStrategy.NO_LINK,
                run_opts={"device": "cpu"},
            )
        matrix = _encode_speaker_signals(
            encoder,
            prototype_signals + candidate_signals,
        )
    except Exception as exc:
        print(f"   [声纹保守补漏] ECAPA 不可用，本次跳过临时标签认领：{exc}")
        return 0
    finally:
        gc.collect()
    prototypes = matrix[: len(prototype_signals)]
    rescued = 0
    rejected = 0
    for row, vector in zip(candidate_rows, matrix[len(prototype_signals) :]):
        scores = np.asarray(vector @ prototypes.T, dtype=np.float32)
        ranking = np.argsort(scores)[::-1]
        best_index = int(ranking[0])
        second_score = float(scores[int(ranking[1])])
        best_score = float(scores[best_index])
        margin = best_score - second_score
        if best_score < TRANSIENT_HOST_MIN_SIMILARITY or margin < TRANSIENT_HOST_MIN_MARGIN:
            rejected += 1
            continue
        original_speaker = str(row.get("speaker") or "S00")
        row["speaker"] = usable_hosts[best_index]
        row["speaker_rescued_from"] = original_speaker
        row["speaker_rescue_score"] = round(best_score, 3)
        row["speaker_rescue_margin"] = round(margin, 3)
        rescued += 1
    if rescued or rejected:
        print(
            f"   [声纹保守补漏] 找回 {rescued} 个主播短句；"
            f"拒绝 {rejected} 个不够确定的临时标签。"
        )
    return rescued


def _drop_redundant_cover_segments(segments, legacy):
    """去掉“一个长段又覆盖同说话人多个短段”的分块边界重复。"""
    ordered = sorted(segments, key=lambda item: (float(item["start"]), float(item["end"])))
    dropped = set()
    for cover_index, cover in enumerate(ordered):
        cover_text = legacy.content_only(cover.get("text", ""))
        cover_start = float(cover["start"])
        cover_end = float(cover["end"])
        cover_duration = max(0.01, cover_end - cover_start)
        if len(cover_text) < 4:
            continue
        pieces = []
        for piece_index, piece in enumerate(ordered):
            if piece_index == cover_index or piece_index in dropped:
                continue
            if str(piece.get("speaker") or "S00") != str(cover.get("speaker") or "S00"):
                continue
            piece_start = float(piece["start"])
            piece_end = float(piece["end"])
            piece_duration = max(0.01, piece_end - piece_start)
            if piece_start < cover_start - 0.12 or piece_end > cover_end + 0.12:
                continue
            if piece_duration >= cover_duration * 0.90:
                continue
            if _time_overlap(cover_start, cover_end, piece_start, piece_end) / piece_duration < 0.85:
                continue
            piece_text = legacy.content_only(piece.get("text", ""))
            if piece_text:
                pieces.append((piece_start, piece_end, piece_text))
        if len(pieces) < 2:
            continue
        pieces.sort(key=lambda item: (item[0], item[1]))
        piece_text = "".join(item[2] for item in pieces)
        if not (0.62 <= len(piece_text) / max(1, len(cover_text)) <= 1.45):
            continue
        covered = 0.0
        interval_start = None
        interval_end = None
        for start, end, _ in pieces:
            if interval_start is None:
                interval_start, interval_end = start, end
            elif start <= interval_end:
                interval_end = max(interval_end, end)
            else:
                covered += interval_end - interval_start
                interval_start, interval_end = start, end
        if interval_start is not None:
            covered += interval_end - interval_start
        similarity = legacy.asr_consensus_similarity(cover_text, piece_text)
        if covered / cover_duration < 0.52 or similarity < 0.76:
            continue
        dropped.add(cover_index)
        print(
            f"   [分块去重] {cover_start:.2f}-{cover_end:.2f}s {cover.get('speaker', 'S00')} "
            f"长段与 {len(pieces)} 个短段重复，保留短段精细边界。"
        )
    return [item for index, item in enumerate(ordered) if index not in dropped]


def _merge_moss_chunks(payload, audio_seconds, legacy, shared_audio=None):
    chunks = payload.get("chunks") or [payload]
    chunk_embeddings = _compute_chunk_speaker_embeddings(
        chunks, shared_audio, audio_seconds, legacy
    )
    merged = []
    previous_full = []
    known_speakers = set()
    next_speaker_id = 1
    global_embeddings = {}
    chunk_summaries = []
    for chunk_index, chunk in enumerate(chunks):
        offset = float(chunk.get("offset", 0.0))
        duration = float(chunk.get("duration", 0.0))
        current_full = []
        for raw in chunk.get("segments", []):
            text = legacy.clean_subtitle_text(raw.get("text", ""))
            if not legacy.content_only(text):
                continue
            start = max(0.0, offset + float(raw["start"]))
            end = min(audio_seconds, max(start + 0.01, offset + float(raw["end"])))
            current_full.append(
                {
                    "start": start,
                    "end": end,
                    "speaker": str(raw.get("speaker") or "S00").strip("[] ") or "S00",
                    "text": text,
                }
            )
        local_embeddings = {
            local: vector
            for (embedding_chunk_index, local), vector in chunk_embeddings.items()
            if embedding_chunk_index == chunk_index
        }
        mapping, next_speaker_id = _map_chunk_speakers(
            current_full,
            previous_full,
            known_speakers,
            next_speaker_id,
            legacy,
            local_embeddings=local_embeddings,
            global_embeddings=global_embeddings,
        )
        voice_scores = {}
        for local, global_speaker in mapping.items():
            vector = local_embeddings.get(local)
            if vector is None:
                continue
            previous_embedding = global_embeddings.get(global_speaker)
            if previous_embedding is not None:
                voice_scores[local] = round(float(np.dot(vector, previous_embedding)), 3)
                blended = previous_embedding * 0.35 + vector * 0.65
                global_embeddings[global_speaker] = blended / max(1e-8, np.linalg.norm(blended))
            else:
                voice_scores[local] = 1.0
                global_embeddings[global_speaker] = vector
        for item in current_full:
            item["speaker"] = mapping[item["speaker"]]
        known_speakers.update(mapping.values())

        owned_start = offset if chunk_index == 0 else offset + MOSS_CHUNK_OVERLAP_SECONDS / 2.0
        chunk_end = min(audio_seconds, offset + duration)
        owned_end = (
            chunk_end
            if chunk_index == len(chunks) - 1
            else chunk_end - MOSS_CHUNK_OVERLAP_SECONDS / 2.0
        )
        for item in current_full:
            center = (item["start"] + item["end"]) / 2.0
            if owned_start <= center < owned_end or (
                chunk_index == len(chunks) - 1 and center <= owned_end
            ):
                merged.append(item)
        previous_full = current_full
        chunk_summaries.append(
            {
                "chunk_id": chunk.get("chunk_id", chunk_index + 1),
                "offset": offset,
                "duration": duration,
                "generated_tokens": int(chunk.get("generated_tokens", 0)),
                "speaker_map": mapping,
                "speaker_voice_scores": voice_scores,
            }
        )

    merged.sort(key=lambda item: (item["start"], item["end"]))
    deduplicated = []
    for item in merged:
        if deduplicated:
            previous = deduplicated[-1]
            overlap = _time_overlap(item["start"], item["end"], previous["start"], previous["end"])
            smaller = max(0.01, min(item["end"] - item["start"], previous["end"] - previous["start"]))
            if (
                item["speaker"] == previous["speaker"]
                and overlap / smaller >= 0.65
                and legacy.asr_consensus_similarity(item["text"], previous["text"]) >= 0.78
            ):
                if len(legacy.content_only(item["text"])) > len(legacy.content_only(previous["text"])):
                    deduplicated[-1] = item
                continue
        deduplicated.append(item)
    payload["segments"] = _drop_redundant_cover_segments(deduplicated, legacy)
    payload["chunk_summaries"] = chunk_summaries
    payload.pop("chunks", None)
    return payload


def transcribe_moss_global(media_path, shared_audio, legacy, cache_context):
    # MOSS 转写必须在主进程预检 CUDA：子进程内报错只会显示为“MOSS 子进程失败”，
    # 无法给出明确原因。
    try:
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError(
                "本机未检测到 NVIDIA CUDA GPU，无法运行 MOSS 转写——"
                "生成字幕需要 CUDA 显卡（MOSS/FireRed/Qwen 均为 GPU 模型）。"
            )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"MOSS CUDA 预检失败：{exc}") from exc
    paths = _script_paths(legacy)
    with tempfile.TemporaryDirectory(prefix="moss_bridge_") as temp_dir:
        output_path = os.path.join(temp_dir, "moss.json")
        jobs = _chunk_moss_audio(shared_audio, temp_dir, legacy)
        title = os.path.splitext(os.path.basename(media_path))[0]
        checkpoint_dir = os.path.join(cache_context["cache_dir"], "moss_chunks")
        run_signature = legacy.stable_digest(
            {
                "media": cache_context["identity"],
                **_moss_stage_signature(paths),
            }
        )
        if jobs:
            for job in jobs:
                job["checkpoint_dir"] = checkpoint_dir
                job["run_signature"] = run_signature
            print(
                f"   MOSS 长音频分块：{len(jobs)} 块，每块最多 {MOSS_CHUNK_SECONDS:.0f}s，"
                f"重叠 {MOSS_CHUNK_OVERLAP_SECONDS:.0f}s。"
            )
            payload = _run_moss_manifest_jobs(
                jobs,
                temp_dir,
                paths,
                legacy,
                title,
            )
        else:
            command = [
                paths["moss_python"],
                paths["moss_worker"],
                "--audio",
                media_path,
                "--output",
                output_path,
                "--model",
                MOSS_MODEL,
                "--title",
                title,
                "--checkpoint-dir",
                checkpoint_dir,
                "--run-signature",
                run_signature,
            ]
            returncode, output_lines = _run_streaming_worker(
                command, MOSS_TIMEOUT_SECONDS
            )
            payload = _read_moss_worker_payload(
                output_path,
                returncode,
                output_lines,
                "MOSS 子进程",
            )
    payload = _merge_moss_chunks(
        payload,
        len(shared_audio) / legacy.AUDIO_SAMPLE_RATE,
        legacy,
        shared_audio=shared_audio,
    )
    segments = payload.get("segments", [])
    segments.sort(key=lambda item: (item["start"], item["end"]))
    if not segments:
        raise RuntimeError("MOSS 没有返回可用的说话人转写段。")
    payload["segments"] = segments
    print(
        f"   [完成] MOSS：{len(segments)} 个全局说话人段，"
        f"{len({item['speaker'] for item in segments})} 个标签，覆盖到 {max(item['end'] for item in segments):.2f} 秒。"
    )
    return payload


def _moss_stage_signature(paths):
    return {
        "model": MOSS_MODEL,
        "worker": _path_signature(paths["moss_worker"]),
        "chunk_seconds": MOSS_CHUNK_SECONDS,
        "chunk_overlap": MOSS_CHUNK_OVERLAP_SECONDS,
    }


def precompute_moss_batch_cache(media_paths, legacy):
    """多文件时让 MOSS 只加载一次；其余模型仍按文件释放，避免叠加显存。"""
    if len(media_paths) < 2:
        return
    paths = _script_paths(legacy)
    signature = _moss_stage_signature(paths)
    pending = []
    for media_path in media_paths:
        cache_context = legacy.media_cache_context(media_path)
        if legacy.cached_stage_is_valid("moss", cache_context, signature):
            continue
        pending.append((media_path, cache_context))
    if len(pending) < 2:
        return

    print(f"\n[批量加速] {len(pending)} 个未缓存文件共用一次 MOSS 模型加载。")
    with tempfile.TemporaryDirectory(prefix="moss_batch_") as temp_dir:
        all_jobs = []
        groups = {}
        for group_index, (media_path, cache_context) in enumerate(pending, 1):
            group_id = f"media_{group_index:03d}"
            shared_audio = legacy.load_shared_audio(media_path, cache_context)
            duration = len(shared_audio) / legacy.AUDIO_SAMPLE_RATE
            group_dir = os.path.join(temp_dir, group_id)
            os.makedirs(group_dir, exist_ok=True)
            jobs = _chunk_moss_audio(shared_audio, group_dir, legacy)
            if not jobs:
                # 按用户要求，短于约210秒的素材继续直接交给 MOSS 读取原媒体。
                jobs = [
                    {
                        "chunk_id": 1,
                        "audio": media_path,
                        "offset": 0.0,
                        "duration": duration,
                        "global_end": duration,
                    }
                ]
            run_signature = legacy.stable_digest(
                {
                    "media": cache_context["identity"],
                    **signature,
                }
            )
            checkpoint_dir = os.path.join(cache_context["cache_dir"], "moss_chunks")
            for job in jobs:
                job.update(
                    {
                        "group_id": group_id,
                        "checkpoint_dir": checkpoint_dir,
                        "run_signature": run_signature,
                    }
                )
                all_jobs.append(job)
            groups[group_id] = {
                "media_path": media_path,
                "cache_context": cache_context,
                "shared_audio": shared_audio,
                "audio_seconds": duration,
            }

        chunks = _run_moss_manifest_jobs(
            all_jobs,
            temp_dir,
            paths,
            legacy,
            "batch",
        ).get("chunks", [])

        for group_id, info in groups.items():
            group_chunks = [
                item for item in chunks if str(item.get("group_id", "default")) == group_id
            ]
            if not group_chunks:
                raise RuntimeError(f"MOSS 批量结果缺少 {os.path.basename(info['media_path'])}。")
            payload = _merge_moss_chunks(
                {"chunks": group_chunks},
                info["audio_seconds"],
                legacy,
                shared_audio=info["shared_audio"],
            )
            if not payload.get("segments"):
                raise RuntimeError(f"MOSS 批量结果为空：{os.path.basename(info['media_path'])}。")
            legacy.store_cached_stage_value(
                "moss",
                info["cache_context"],
                payload,
                extra_signature=signature,
            )
            print(f"   [批量缓存完成] {os.path.basename(info['media_path'])}")


def detect_firered_vad(audio, legacy):
    paths = _script_paths(legacy)
    if not os.path.isdir(paths["firered_vad"]):
        raise RuntimeError("FireRedVAD 模型目录不存在。")
    if legacy.FIRERED_SOURCE_DIR not in sys.path:
        sys.path.insert(0, legacy.FIRERED_SOURCE_DIR)
    from twobyteasr.model_integrity import verify_model_files

    verify_model_files("firered_vad", os.path.dirname(paths["firered_vad"]))
    from fireredasr2s.fireredvad import FireRedVad, FireRedVadConfig

    model = None
    try:
        config = FireRedVadConfig(
            use_gpu=False,
            smooth_window_size=5,
            speech_threshold=0.30,
            min_speech_frame=8,
            max_speech_frame=2000,
            min_silence_frame=12,
            merge_silence_frame=3,
            extend_speech_frame=8,
            chunk_max_frame=30000,
        )
        model = FireRedVad.from_pretrained(paths["firered_vad"], config)
        with tempfile.TemporaryDirectory(prefix="firered_vad_") as temp_dir:
            wav_path = os.path.join(temp_dir, "audio.wav")
            legacy.write_pcm16_wav(wav_path, audio)
            result, _ = model.detect(wav_path)
        regions = [
            {"start": max(0.0, float(start)), "end": max(float(start), float(end))}
            for start, end in result.get("timestamps", [])
            if float(end) > float(start)
        ]
        if not regions:
            raise RuntimeError("FireRedVAD 没有检测到语音。")
        print(f"   [完成] FireRedVAD：{len(regions)} 个人声区间。")
        return regions
    finally:
        if model is not None:
            del model
        gc.collect()


def _time_overlap(left_start, left_end, right_start, right_end):
    return max(0.0, min(left_end, right_end) - max(left_start, right_start))


def _distributed_words(text, start, end, confidence, legacy):
    chars = list(legacy.content_only(text))
    if not chars:
        return []
    duration = max(0.01, end - start)
    return [
        legacy.WordUnit(
            start + duration * index / len(chars),
            start + duration * (index + 1) / len(chars),
            char,
            confidence,
        )
        for index, char in enumerate(chars)
    ]



def _load_host_encoder(legacy):
    paths = _script_paths(legacy)
    model_dir = paths["speaker_embedding"]
    if not os.path.isfile(os.path.join(model_dir, "embedding_model.ckpt")):
        raise RuntimeError("缺少 ECAPA 声纹模型")
    import warnings

    import torchaudio

    if not hasattr(torchaudio, "list_audio_backends"):
        torchaudio.list_audio_backends = lambda: ["soundfile"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from speechbrain.inference.speaker import EncoderClassifier
        from speechbrain.utils.fetching import LocalStrategy

        encoder = EncoderClassifier.from_hparams(
            source=model_dir,
            savedir=model_dir,
            overrides={"pretrained_path": model_dir},
            local_strategy=LocalStrategy.NO_LINK,
            run_opts={"device": "cpu"},
        )
    return encoder


def apply_registered_host_voiceprints(
    moss_segments,
    host_speakers,
    shared_audio,
    legacy,
    candidate_speakers=None,
    runtime_context=None,
):
    """Map every credible MOSS label onto enrolled hosts before final filtering."""
    fallback_hosts = list(host_speakers)
    candidate_speakers = list(candidate_speakers or host_speakers)
    if shared_audio is None or not host_speakers:
        return host_speakers, moss_segments
    load_registry = getattr(legacy, "load_host_voiceprint_registry", None)
    if load_registry is None:
        return host_speakers, moss_segments
    registry = load_registry()
    enrolled = list(registry.get("hosts") or [])
    if len(enrolled) < 1:
        print("   [主播声纹] 未找到已注册原型，继续用 MOSS 自动标签。")
        return host_speakers, moss_segments

    import numpy as np

    audio = np.asarray(shared_audio, dtype=np.float32)
    sample_rate = int(getattr(legacy, "AUDIO_SAMPLE_RATE", 16000))
    max_seconds = float(SPEAKER_EMBEDDING_MAX_AUDIO_SECONDS)

    def speaker_signal(speaker):
        rows = [
            item
            for item in moss_segments
            if str(item.get("speaker") or "S00") == speaker
        ]
        if not rows:
            return None
        rows.sort(key=lambda item: float(item["end"]) - float(item["start"]), reverse=True)
        chunks = []
        total = 0.0
        for row in rows:
            start = max(0.0, float(row["start"]))
            end = max(start + 0.05, float(row["end"]))
            a = int(start * sample_rate)
            b = min(len(audio), int(end * sample_rate))
            if b - a < int(0.35 * sample_rate):
                continue
            piece = audio[a:b]
            chunks.append(piece)
            total += (b - a) / sample_rate
            if total >= max_seconds:
                break
        if not chunks:
            return None
        signal = np.concatenate(chunks)
        if len(signal) > int(max_seconds * sample_rate):
            signal = signal[: int(max_seconds * sample_rate)]
        return signal

    signals = []
    live_hosts = []
    for speaker in candidate_speakers:
        segment_count = sum(
            str(item.get("speaker") or "S00") == speaker
            for item in moss_segments
        )
        if segment_count < REGISTERED_HOST_MIN_SEGMENTS:
            continue
        signal = speaker_signal(speaker)
        if signal is None:
            continue
        signals.append(signal)
        live_hosts.append(speaker)
    if not signals:
        print("   [主播声纹] 当前素材无法提取稳定主播片段，跳过注册匹配。")
        return host_speakers, moss_segments

    try:
        encoder = _load_host_encoder(legacy)
        live_matrix = _encode_speaker_signals(encoder, signals)
    except Exception as exc:
        print(f"   [主播声纹] ECAPA 不可用，跳过注册匹配：{exc}")
        return host_speakers, moss_segments
    finally:
        gc.collect()

    proto = np.asarray([item["embedding"] for item in enrolled], dtype=np.float32)
    norms = np.linalg.norm(proto, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-8)
    proto = proto / norms

    assignment = {}
    rejected = {}
    for live_index, speaker in enumerate(live_hosts):
        scores = np.asarray(live_matrix[live_index] @ proto.T, dtype=np.float32)
        ranking = np.argsort(scores)[::-1]
        proto_index = int(ranking[0])
        score = float(scores[proto_index])
        second_score = float(scores[int(ranking[1])]) if len(ranking) > 1 else -1.0
        margin = score - second_score if len(ranking) > 1 else 1.0
        if score < REGISTERED_HOST_MIN_SIMILARITY or margin < REGISTERED_HOST_MIN_MARGIN:
            rejected[speaker] = {
                "score": round(score, 3),
                "margin": round(margin, 3),
            }
            continue
        host = enrolled[proto_index]
        label = str(host.get("label") or "").strip() or f"S{len(assignment)+1:02d}"
        assignment[speaker] = {
            "label": label,
            "name": str(host.get("name") or host.get("id") or label),
            "score": round(score, 3),
            "margin": round(margin, 3),
        }
    if not assignment:
        print("   [主播声纹] 注册原型未命中足够相似度，保留 MOSS 标签。")
        return host_speakers, moss_segments

    # A confident enrolled match can rename a raw MOSS label onto a label that is
    # already used by another, lower-confidence speaker (for example raw S02 is
    # confidently 主播A/S01 while raw S01 is the second, stable host).  Keeping
    # the rejected raw label unchanged would then merge both people into S01 and
    # silently remove the second speaker track.  Preserve every speaker already
    # selected by the host filter, but leave low-confidence fallbacks anonymous.
    label_order = []
    for host in enrolled:
        label = str(host.get("label") or "").strip()
        if label and label not in label_order:
            label_order.append(label)
    used_labels = {info["label"] for info in assignment.values()}
    requested = int(
        (
            runtime_context.expected_speakers
            if runtime_context is not None
            else getattr(legacy, "RUNTIME_EXPECTED_SPEAKERS", 0)
        )
        or 0
    )
    # 自动模式必须保留主播筛选阶段已经确认的未注册主播。过去这里按
    # “已注册声纹数”截断，注册两人后第三位未注册主播会再次被静默丢掉。
    target_count = requested or min(
        MOSS_AUTO_MAX_HOST_SPEAKERS,
        len(fallback_hosts),
    )
    fallback_assignment = {}
    for speaker in fallback_hosts:
        if speaker in assignment or len(used_labels) >= target_count:
            continue
        available = next((label for label in label_order if label not in used_labels), "")
        if not available:
            available = speaker if speaker not in used_labels else ""
        if not available:
            continue
        fallback_assignment[speaker] = {
            "label": available,
            "score": rejected.get(speaker, {}).get("score"),
            "margin": rejected.get(speaker, {}).get("margin"),
        }
        used_labels.add(available)

    for item in moss_segments:
        speaker = str(item.get("speaker") or "S00")
        mapped = assignment.get(speaker) or fallback_assignment.get(speaker)
        if not mapped:
            continue
        item["speaker_raw"] = speaker
        item["speaker"] = mapped["label"]
        if mapped.get("name"):
            item["speaker_host_name"] = mapped["name"]
            item["speaker_host_score"] = mapped["score"]
        else:
            item["speaker_voiceprint_fallback"] = True

    new_hosts = []
    seen = set()
    for label in label_order:
        if any(
            v["label"] == label
            for v in (*assignment.values(), *fallback_assignment.values())
        ) and label not in seen:
            new_hosts.append(label)
            seen.add(label)
    if len(new_hosts) < target_count:
        for speaker in fallback_hosts:
            label = (
                assignment.get(speaker, {}).get("label")
                or fallback_assignment.get(speaker, {}).get("label")
                or speaker
            )
            if label not in seen:
                new_hosts.append(label)
                seen.add(label)
            if len(new_hosts) >= target_count:
                break
    detail = "，".join(
        f"{info['label']}={info['name']}({info['score']:.3f},余量{info['margin']:.3f}<-{src})"
        for src, info in assignment.items()
    )
    print(f"   [主播声纹] 注册匹配：{detail}")
    if fallback_assignment:
        fallback_detail = "，".join(
            f"{source}->{info['label']}"
            for source, info in fallback_assignment.items()
        )
        print(
            "   [主播声纹] 低置信稳定主播仅保留分轨、不实名："
            f"{fallback_detail}"
        )
    legacy.record_run_event(
        "host_voiceprint_mapping",
        assignments=assignment,
        rejected=rejected,
        fallback_assignments=fallback_assignment,
        host_labels=new_hosts,
    )
    return new_hosts or host_speakers, moss_segments


def select_host_speakers(
    moss_segments,
    audio_seconds,
    legacy,
    runtime_context=None,
):
    speakers = sorted({str(item.get("speaker") or "S00") for item in moss_segments})
    requested = int(
        (
            runtime_context.expected_speakers
            if runtime_context is not None
            else getattr(legacy, "RUNTIME_EXPECTED_SPEAKERS", 0)
        )
        or 0
    )
    max_hosts = requested or MOSS_AUTO_MAX_HOST_SPEAKERS
    if not requested and len(speakers) <= 2:
        # 1/2 人素材保留原来的快速路径。达到三位时即使是短素材也按
        # 发言量排序并受自动人数上限约束，避免短片中的一次性角色声
        # 绕过筛选，同时让稳定的第三主播正常进入分轨。
        return speakers

    bin_seconds = 60.0
    stats = {}
    for speaker in speakers:
        rows = [item for item in moss_segments if str(item.get("speaker") or "S00") == speaker]
        first = min(float(item["start"]) for item in rows)
        last = max(float(item["end"]) for item in rows)
        active_bins = {
            int(float(item["start"]) // bin_seconds)
            for item in rows
        }
        stats[speaker] = {
            "count": len(rows),
            "span_ratio": max(0.0, last - first) / max(1.0, audio_seconds),
            "bins": len(active_bins),
            "chars": sum(len(legacy.content_only(item.get("text", ""))) for item in rows),
        }
    max_bins = max(item["bins"] for item in stats.values())
    max_count = max(item["count"] for item in stats.values())
    eligible = [
        speaker
        for speaker, item in stats.items()
        if item["span_ratio"] >= MOSS_HOST_MIN_SPAN_RATIO
        and item["bins"] >= max(2, math.ceil(max_bins * MOSS_HOST_MIN_ACTIVE_BIN_RATIO))
        and item["count"] >= max(3, math.ceil(max_count * 0.45))
    ]
    ranked = sorted(
        # 用户明确指定人数时，从全部 MOSS 标签中选足人数；自动模式才
        # 使用持续度门槛过滤节目/角色声。
        speakers if requested else (eligible or speakers),
        key=lambda speaker: (
            stats[speaker]["bins"],
            stats[speaker]["span_ratio"],
            stats[speaker]["count"],
            stats[speaker]["chars"],
        ),
        reverse=True,
    )
    selected = ranked[:max_hosts]
    detail = "，".join(
        f"{speaker}(跨{stats[speaker]['bins']}分钟窗/{stats[speaker]['span_ratio']:.0%})"
        for speaker in selected
    )
    source = "用户指定人数" if requested else "自动筛选"
    print(f"   [主播筛选] {source}，保留 {detail}；其余标签作为节目/角色声不写入成片字幕。")
    if requested and len(selected) < requested:
        legacy.add_review_item(
            0.0,
            "主播人数不足",
            f"预计 {requested} 位主播，但 MOSS 只形成 {len(selected)} 个可用主播标签",
            priority=3,
        )
        print(
            f"   [警告] 预计 {requested} 位主播，但只找到 {len(selected)} 位；"
            "不会复制或伪造第二条轨道。"
        )
    return selected


def build_moss_host_primary_segments(
    moss_payload,
    firered_tokens,
    speech_regions,
    audio_seconds,
    legacy,
    shared_audio=None,
    runtime_context=None,
):
    """MOSS 主播文本和时间作为骨架；FireRed 只提供独立文字证据，不再接管时间。"""
    # 旧缓存也可能来自尚未做覆盖式去重的分块版本，因此主稿入口再做一次幂等清理。
    moss_segments = _drop_redundant_cover_segments(
        list(moss_payload.get("segments", [])), legacy
    )
    moss_payload["segments"] = moss_segments
    host_speakers = select_host_speakers(
        moss_segments,
        audio_seconds,
        legacy,
        runtime_context=runtime_context,
    )
    all_speakers = sorted(
        {str(item.get("speaker") or "S00") for item in moss_segments}
    )
    host_speakers, moss_segments = apply_registered_host_voiceprints(
        moss_segments,
        host_speakers,
        shared_audio,
        legacy,
        candidate_speakers=all_speakers,
        runtime_context=runtime_context,
    )
    moss_payload["segments"] = moss_segments
    moss_payload["host_speakers"] = host_speakers
    _rescue_transient_host_segments(
        moss_segments,
        host_speakers,
        shared_audio,
        legacy,
    )
    filtered_labels = {}
    for item in moss_segments:
        speaker = str(item.get("speaker") or "S00")
        if speaker in host_speakers:
            continue
        summary = filtered_labels.setdefault(speaker, {"segments": 0, "seconds": 0.0})
        summary["segments"] += 1
        summary["seconds"] += max(0.0, float(item["end"]) - float(item["start"]))
    for summary in filtered_labels.values():
        summary["seconds"] = round(summary["seconds"], 3)
    legacy.record_run_event(
        "host_filter_summary",
        host_labels=list(host_speakers),
        filtered_labels=filtered_labels,
    )
    tokens = []
    for token in firered_tokens or []:
        text = legacy.clean_subtitle_text(token.get("text", ""))
        if not legacy.content_only(text):
            continue
        tokens.append(
            {
                "text": text,
                "start": float(token["start"]),
                "end": float(token["end"]),
                "confidence": float(token.get("confidence", 0.75)),
            }
        )
    result = []
    dropped_no_speech = 0
    for index, moss in enumerate(moss_segments):
        speaker = str(moss.get("speaker") or "S00")
        if speaker not in host_speakers:
            continue
        start = max(0.0, float(moss["start"]))
        end = max(start + 0.01, float(moss["end"]))
        moss_text = legacy.clean_subtitle_text(moss.get("text", ""))
        if not legacy.content_only(moss_text):
            continue
        speech_overlap = sum(
            _time_overlap(start, end, float(region["start"]), float(region["end"]))
            for region in speech_regions
        )
        if speech_overlap < min(0.12, (end - start) * 0.25):
            dropped_no_speech += 1
            continue

        nearby_tokens = [
            token
            for token in tokens
            if token["end"] >= start - MOSS_SPEAKER_PAD_SECONDS
            and token["start"] <= end + MOSS_SPEAKER_PAD_SECONDS
        ]
        raw_firered = legacy.clean_subtitle_text(
            "".join(token["text"] for token in nearby_tokens)
        )
        firered_candidate, firered_similarity = legacy.best_alternate_window(
            moss_text, raw_firered
        )
        if firered_similarity < 0.42:
            firered_candidate = ""
        confidence = 0.78 if firered_similarity >= 0.78 else (0.64 if firered_similarity >= 0.55 else 0.50)
        overlap_conflict = any(
            other_index != index
            and str(other.get("speaker") or "S00") != speaker
            and _time_overlap(start, end, float(other["start"]), float(other["end"]))
            >= MOSS_OVERLAP_CONFLICT_SECONDS
            for other_index, other in enumerate(moss_segments)
        )
        rescued_from = str(moss.get("speaker_rescued_from") or "")
        segment = legacy.SpeechSegment(
            segment_id=0,
            start=start,
            end=max(end, start + legacy.MIN_SUBTITLE_SECONDS),
            text=moss_text,
            confidence=confidence,
            words=_distributed_words(moss_text, start, end, confidence, legacy),
            speaker=speaker,
            moss_text=moss_text,
            moss_context=moss_text,
            alternate_text=firered_candidate,
            alternate_context=raw_firered,
            overlapping_speaker_conflict=overlap_conflict,
            timing_locked=overlap_conflict,
            firered_text=firered_candidate,
            primary_source="moss-host-rescued" if rescued_from else "moss-host",
            reference_consensus=firered_similarity,
        )
        if overlap_conflict:
            legacy.add_review_item(
                start,
                "说话人重叠",
                "主播与节目/角色声重叠，保留 MOSS 主播稿并冻结跨说话人替换",
                moss_text,
                priority=3,
            )
        if rescued_from:
            legacy.add_review_item(
                start,
                "临时说话人找回",
                f"MOSS {rescued_from} 仅短暂出现；ECAPA 以 "
                f"{float(moss.get('speaker_rescue_score', 0.0)):.3f} 分、"
                f"{float(moss.get('speaker_rescue_margin', 0.0)):.3f} 差值认领为 {speaker}",
                moss_text,
                priority=2,
            )
        result.append(segment)

    result.sort(key=lambda segment: (segment.start, segment.end))
    for segment_id, segment in enumerate(result, 1):
        segment.segment_id = segment_id
    if not result:
        raise RuntimeError("MOSS 没有筛出可用的主播字幕。")
    print(
        f"   [完成] MOSS 主播主稿：{len(result)} 段；"
        f"未再补入 {sum(1 for token in tokens if not any(segment.start - 0.2 <= (token['start'] + token['end']) / 2.0 <= segment.end + 0.2 for segment in result))} 个段外 FireRed 字词。"
    )
    if dropped_no_speech:
        print(f"   [VAD拒绝] {dropped_no_speech} 个 MOSS 段缺少实际人声覆盖。")
    return result


def attach_qwen_review_evidence(segments, qwen_chunks, legacy):
    """保留 Qwen 原始时间窗，并允许它与 MOSS 形成独立共识。"""
    accepted = 0
    for segment in segments:
        contexts = []
        for chunk in qwen_chunks or []:
            if (
                float(chunk["end"]) < segment.start - legacy.QWEN_ASR_TEXT_ALIGNMENT_PAD_SECONDS
                or float(chunk["start"]) > segment.end + legacy.QWEN_ASR_TEXT_ALIGNMENT_PAD_SECONDS
            ):
                continue
            text = legacy.clean_subtitle_text(chunk.get("text", ""))
            if legacy.content_only(text):
                contexts.append(text)
        raw_context = legacy.clean_subtitle_text(" ".join(contexts))
        segment.qwen_asr_context = raw_context
        if not raw_context:
            continue

        primary_candidate, primary_score = legacy.best_alternate_window(
            segment.text, raw_context
        )
        moss_candidate, moss_score = legacy.best_alternate_window(
            segment.moss_text, raw_context
        )
        moss_supported = (
            moss_candidate
            and moss_score >= 0.72
            and legacy.asr_consensus_similarity(segment.moss_text, moss_candidate) >= 0.72
        )
        # 若 Qwen 的原始窗完整支持 MOSS（尤其补回 FireRed 漏掉的句首/句尾），
        # 优先保留这份独立候选；不能总裁成最像 FireRed 的等长文本。
        if moss_supported and (
            moss_score >= primary_score + 0.02
            or len(legacy.content_only(moss_candidate))
            > len(legacy.content_only(primary_candidate))
        ):
            segment.qwen_asr_text = moss_candidate
            accepted += 1
        elif primary_candidate and primary_score >= legacy.QWEN_ASR_ALTERNATE_MIN_SIMILARITY:
            segment.qwen_asr_text = primary_candidate
            accepted += 1
        elif moss_supported:
            segment.qwen_asr_text = moss_candidate
            accepted += 1
    print(f"   [完成] Qwen3-ASR 复核：{accepted}/{len(segments)} 段获得独立文字证据。")
    return segments


def add_qwen_skeleton_gap_review_items(segments, qwen_chunks, moss_payload, legacy):
    """Flag text supported by Qwen but excluded from the host-only MOSS skeleton."""
    host_speakers = set(moss_payload.get("host_speakers") or [])
    if not host_speakers or not qwen_chunks:
        return 0
    candidates = []
    for item in moss_payload.get("segments") or []:
        speaker = str(item.get("speaker") or "S00")
        if speaker in host_speakers:
            continue
        start = max(0.0, float(item.get("start", 0.0)))
        end = max(start, float(item.get("end", start)))
        duration = end - start
        text = legacy.clean_subtitle_text(item.get("text", ""))
        if duration < 0.45 or len(legacy.content_only(text)) < 3:
            continue
        host_overlap = sum(
            _time_overlap(start, end, segment.start, segment.end)
            for segment in segments
        )
        if host_overlap / max(0.01, duration) >= 0.20:
            continue
        qwen_context = legacy.clean_subtitle_text(
            " ".join(
                legacy.clean_subtitle_text(chunk.get("text", ""))
                for chunk in qwen_chunks
                if float(chunk.get("end", 0.0)) >= start - 0.30
                and float(chunk.get("start", 0.0)) <= end + 0.30
            )
        )
        if not legacy.content_only(qwen_context):
            continue
        qwen_candidate, similarity = legacy.best_alternate_window(text, qwen_context)
        if not qwen_candidate or similarity < 0.64:
            continue
        candidates.append((similarity, start, end, speaker, text))

    # Keep the review track useful on noisy program audio: retain at most the
    # strongest twelve gaps, then restore timeline order for editors.
    candidates.sort(key=lambda row: (-row[0], row[1]))
    selected = sorted(candidates[:12], key=lambda row: row[1])
    for similarity, start, _end, speaker, text in selected:
        legacy.add_review_item(
            start,
            "Qwen骨架缺口",
            f"MOSS 将该段归为节目/角色声 {speaker}，Qwen 文字支持 {similarity:.0%}；不自动写入主播轨",
            text,
            priority=2,
        )
    legacy.record_run_event(
        "qwen_skeleton_gap_review",
        candidate_count=len(candidates),
        emitted_count=len(selected),
    )
    if selected:
        print(f"   [Qwen骨架缺口] {len(selected)} 段写入独立复核轨，不混入主播字幕。")
    return len(selected)


def reconcile_firered_moss_qwen(segments, legacy):
    # Two independent local ASR models often agree on a one- or two-character
    # correction inside an otherwise nearly identical sentence.  Apply those
    # shared spans before the broader arbitration scores are calculated.
    segments = legacy.apply_reference_consensus_corrections(segments)
    promoted = 0
    for segment in segments:
        primary = legacy.clean_subtitle_text(legacy.simplify_chinese(segment.text))
        moss = legacy.clean_subtitle_text(
            legacy.simplify_chinese(segment.moss_text or segment.alternate_text)
        )
        firered = legacy.clean_subtitle_text(
            legacy.simplify_chinese(segment.firered_text or segment.alternate_text)
        )
        qwen = legacy.clean_subtitle_text(legacy.simplify_chinese(segment.qwen_asr_text))
        if not primary:
            continue
        first_reference = firered if segment.primary_source.startswith("moss-host") else moss
        if first_reference and qwen:
            consensus = legacy.asr_consensus_similarity(first_reference, qwen)
            segment.reference_consensus = consensus
            first_support = legacy.asr_consensus_similarity(primary, first_reference)
            qwen_support = legacy.asr_consensus_similarity(primary, qwen)
            primary_support = max(
                first_support,
                qwen_support,
            )
            if (
                len(legacy.content_only(primary)) >= 4
                and consensus >= 0.76
                and primary_support < 0.62
            ):
                legacy.add_review_item(
                    segment.start,
                    "多模型文本冲突",
                    "FireRed/Qwen3 互相支持，但与 MOSS 主播稿明显不同；保留主播稿并等待受限校对",
                    segment.text,
                    priority=3,
                )
            if (
                not segment.overlapping_speaker_conflict
                and consensus >= legacy.ASR_CONSENSUS_MIN_SIMILARITY
                and (segment.confidence < 0.60 or primary_support < 0.60)
            ):
                candidate = qwen
                if legacy.consensus_candidate_is_safe(primary, candidate, segment.confidence):
                    segment.text = candidate
                    segment.primary_source = (
                        "moss-host+refs"
                        if segment.primary_source.startswith("moss-host")
                        else "moss+qwen3-consensus"
                    )
                    promoted += 1
        supports = [value for value in (first_reference, qwen) if value]
        if supports:
            best_support = max(legacy.asr_consensus_similarity(primary, value) for value in supports)
            if segment.confidence < 0.62 or best_support < 0.58:
                legacy.add_review_item(
                    segment.start,
                    "多模型争议",
                    f"主稿证据分 {segment.confidence:.2f}，最佳外部支持 {best_support:.0%}",
                    segment.text,
                    priority=2,
                )
    print(f"   [完成] 本地仲裁：{promoted}/{len(segments)} 段由两套独立参考安全接管。")
    return segments


def _disputed_segments(segments, legacy):
    disputed = []
    for segment in segments:
        moss = segment.moss_text or segment.alternate_text
        firered = segment.firered_text or segment.alternate_text
        qwen = segment.qwen_asr_text
        primary = segment.text
        first_reference = firered if segment.primary_source.startswith("moss-host") else moss
        external_consensus = (
            legacy.asr_consensus_similarity(first_reference, qwen)
            if first_reference and qwen
            else 0.0
        )
        primary_support = max(
            [legacy.asr_consensus_similarity(primary, value) for value in (first_reference, qwen) if value]
            or [0.0]
        )
        if (
            not segment.overlapping_speaker_conflict
            and (
                segment.confidence < 0.55
                or (external_consensus >= 0.80 and primary_support < 0.68)
            )
        ):
            severity = (
                max(0.0, 0.62 - float(segment.confidence)) * 2.0
                + max(0.0, external_consensus - primary_support)
            )
            disputed.append((severity, segment))
    if len(disputed) <= 24:
        return [segment for _, segment in sorted(disputed, reverse=True, key=lambda item: item[0])]

    # 不再只复核视频开头的前24条：按全片六个时间窗抽高风险项，再用全局高风险补齐。
    end_time = max(segment.end for _, segment in disputed)
    selected = []
    selected_ids = set()
    for bucket in range(6):
        left = end_time * bucket / 6.0
        right = end_time * (bucket + 1) / 6.0
        rows = sorted(
            (item for item in disputed if left <= item[1].start < right),
            reverse=True,
            key=lambda item: item[0],
        )[:4]
        for _, segment in rows:
            selected.append(segment)
            selected_ids.add(segment.segment_id)
    for _, segment in sorted(disputed, reverse=True, key=lambda item: item[0]):
        if len(selected) >= 24:
            break
        if segment.segment_id not in selected_ids:
            selected.append(segment)
            selected_ids.add(segment.segment_id)
    return selected[:24]


def safe_review_disputes_with_firered_llm(segments, shared_audio, legacy):
    """FireRed-LLM 是争议复核增强；失败不应让整批主识别报废。"""
    try:
        return review_disputes_with_firered_llm(segments, shared_audio, legacy)
    except Exception as exc:
        legacy.add_review_item(
            0.0,
            "FireRed-LLM跳过",
            f"可选复核失败，已保留 MOSS/FireRed/Qwen 主链结果：{exc}",
            priority=2,
        )
        print(f"   [警告] FireRedASR2-LLM 可选复核失败，继续主流程：{exc}")
        return segments


def review_disputes_with_firered_llm(segments, shared_audio, legacy):
    disputes = _disputed_segments(segments, legacy)
    if not disputes:
        print("   FireRedASR2-LLM：没有满足门槛的争议片段，跳过。")
        return segments
    endpoint = os.environ.get("FIRERED_LLM_ENDPOINT", "").strip().rstrip("/")
    if endpoint:
        from twobyteasr.llm_config import validate_transport_url

        validate_transport_url(endpoint, "FireRed-LLM 服务")
    paths = _script_paths(legacy)
    local_ready = all(
        os.path.exists(path)
        for path in (
            os.path.join(paths["firered_llm"], "model.pth.tar"),
            os.path.join(paths["firered_llm"], "asr_encoder.pth.tar"),
            os.path.join(paths["firered_llm"], "Qwen2-7B-Instruct", "config.json"),
            paths["firered_llm_worker"],
        )
    )
    if local_ready:
        try:
            import torch

            local_ready = torch.cuda.is_available() and torch.cuda.get_device_properties(0).total_memory / (1024 ** 3) >= FIRERED_LLM_MIN_GPU_GB
        except Exception:
            local_ready = False
    if not endpoint and not local_ready:
        print(
            f"   FireRedASR2-LLM：发现 {len(disputes)} 个争议片段，但本机显存/模型条件不足，"
            "保留给云端模型受限校对并列入复核清单。"
        )
        return segments

    with tempfile.TemporaryDirectory(prefix="firered_llm_") as temp_dir:
        jobs = []
        for index, segment in enumerate(disputes, 1):
            start = max(0.0, segment.start - 0.40)
            end = min(len(shared_audio) / legacy.AUDIO_SAMPLE_RATE, segment.end + 0.40)
            left = int(round(start * legacy.AUDIO_SAMPLE_RATE))
            right = int(round(end * legacy.AUDIO_SAMPLE_RATE))
            wav_path = os.path.join(temp_dir, f"dispute_{index:03d}.wav")
            legacy.write_pcm16_wav(wav_path, shared_audio[left:right])
            jobs.append({"segment_id": segment.segment_id, "path": wav_path, "start": start, "end": end})

        results = {}
        if endpoint:
            import requests

            for job in jobs:
                with open(job["path"], "rb") as audio_file:
                    response = requests.post(
                        endpoint,
                        data={"model": os.environ.get("FIRERED_LLM_MODEL", "FireRedASR2-LLM"), "response_format": "json"},
                        files={"file": (os.path.basename(job["path"]), audio_file, "audio/wav")},
                        timeout=600,
                    )
                response.raise_for_status()
                payload = response.json()
                results[job["segment_id"]] = payload.get("text", "")
        else:
            manifest_path = os.path.join(temp_dir, "manifest.json")
            output_path = os.path.join(temp_dir, "results.json")
            with open(manifest_path, "w", encoding="utf-8") as file:
                json.dump({"jobs": jobs}, file, ensure_ascii=False)
            completed = subprocess.run(
                [sys.executable, paths["firered_llm_worker"], "--manifest", manifest_path, "--output", output_path, "--model-dir", paths["firered_llm"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3600,
                check=False,
                **hidden_subprocess_kwargs(),
            )
            if completed.returncode != 0:
                raise RuntimeError("FireRedASR2-LLM 子进程失败：" + completed.stderr[-1600:])
            with open(output_path, "r", encoding="utf-8") as file:
                for item in json.load(file).get("results", []):
                    results[int(item["segment_id"])] = item.get("text", "")

    attached = 0
    by_id = {segment.segment_id: segment for segment in segments}
    for segment_id, text in results.items():
        segment = by_id.get(int(segment_id))
        if segment is None:
            continue
        cleaned = legacy.clean_subtitle_text(text)
        if not legacy.content_only(cleaned):
            continue
        segment.firered_llm_text = cleaned
        segment.firered_llm_context = cleaned
        attached += 1
    print(f"   [完成] FireRedASR2-LLM：{attached}/{len(disputes)} 个争议片段获得额外证据。")
    return segments


def _cuda_total_memory_gb():
    try:
        import torch

        if not torch.cuda.is_available():
            return 0.0
        return float(torch.cuda.get_device_properties(0).total_memory) / (1024 ** 3)
    except Exception:
        return 0.0


def process_media(
    media_path,
    file_index,
    file_total,
    legacy,
    runtime_context=None,
):
    runtime_context = runtime_context or get_runtime_context()
    runtime_context.reset_for_media()
    legacy.reset_review_items()
    started = time.perf_counter()
    base_name = os.path.splitext(os.path.basename(media_path))[0]
    txt_path, srt_path = legacy.output_paths_for_media(media_path)
    timeline_fps = legacy.detect_timeline_fps(media_path)
    cache_context = legacy.media_cache_context(media_path)
    legacy.begin_media_report(media_path, cache_context)
    paths = _script_paths(legacy)
    stage_total = 11
    stage_index = 0

    print("\n" + "=" * 72)
    print(f"[文件 {file_index}/{file_total}] {os.path.basename(media_path)}")
    print(f"   缓存目录：{cache_context['cache_dir']}")

    stage_index += 1
    shared_audio = legacy.run_timed_stage(
        stage_index, stage_total, "统一 16k 音频采样时钟", "CPU+磁盘缓存", lambda: legacy.load_shared_audio(media_path, cache_context)
    )
    audio_seconds = len(shared_audio) / legacy.AUDIO_SAMPLE_RATE

    moss_signature = _moss_stage_signature(paths)

    def run_moss_stage():
        return legacy.run_timed_stage(
            2,
            stage_total,
            "MOSS 全局说话人与粗时间转写",
            "独立 Python 3.12 + GPU",
            lambda: legacy.run_cached_stage(
                "moss",
                cache_context,
                lambda: transcribe_moss_global(media_path, shared_audio, legacy, cache_context),
                should_cache=lambda value: bool(value.get("segments")),
                extra_signature=moss_signature,
            ),
        )

    def run_vad_stage():
        return legacy.run_timed_stage(
            3,
            stage_total,
            "FireRedVAD 人声安全检查",
            "CPU",
            lambda: legacy.run_cached_stage(
                "firered_vad",
                cache_context,
                lambda: detect_firered_vad(shared_audio, legacy),
                should_cache=bool,
                extra_signature=_path_signature(paths["firered_vad"]),
            ),
        )

    if legacy.PARALLEL_CPU_VAD:
        print("   [并行加速] FireRedVAD 与 MOSS 同时运行。")
        legacy.record_run_event("local_stages_parallel", stages=["moss", "firered_vad"])
        parallel_results = run_parallel_stages(
            legacy,
            {"moss": run_moss_stage, "vad": run_vad_stage},
            thread_name_prefix="moss-vad",
        )
        moss_payload = parallel_results["moss"]
        speech_regions = parallel_results["vad"]
    else:
        moss_payload = run_moss_stage()
        speech_regions = run_vad_stage()
    stage_index = 3

    moss_last_end = max(float(item["end"]) for item in moss_payload["segments"])
    vad_last_end = max(float(item["end"]) for item in speech_regions)
    if vad_last_end - moss_last_end > 0.50:
        legacy.add_review_item(
            moss_last_end,
            "MOSS提前结束",
            f"MOSS 到 {moss_last_end:.2f}s，FireRedVAD 人声到 {vad_last_end:.2f}s；尾段不自动补入节目声",
            priority=3,
        )

    def run_firered_stage():
        return legacy.run_timed_stage(
            4,
            stage_total,
            "FireRedASR2-AED 独立文字证据",
            "GPU",
            lambda: legacy.run_cached_stage(
                "firered",
                cache_context,
                lambda: legacy.transcribe_firered_reference(shared_audio, audio_seconds),
                should_cache=bool,
            ),
        )

    def run_qwen_stage():
        return legacy.run_timed_stage(
            6,
            stage_total,
            "Qwen3-ASR 局部复核",
            "GPU",
            lambda: legacy.run_cached_stage(
                "qwen",
                cache_context,
                lambda: legacy.transcribe_qwen_reference(media_path, speech_regions, shared_audio),
                should_cache=bool,
                extra_signature=speech_regions,
            ),
        )

    total_vram_gb = _cuda_total_memory_gb()
    parallel_gpu_asr = bool(
        legacy.PARALLEL_GPU_ASR
        and legacy.USE_FIRERED_BOUNDARY_REFINEMENT
        and legacy.USE_QWEN_ASR_REFERENCE
        and total_vram_gb >= legacy.PARALLEL_GPU_ASR_MIN_VRAM_GB
    )
    if parallel_gpu_asr:
        print(
            f"   [并行加速] FireRed-AED 与 Qwen3-ASR 同时运行"
            f"（显存 {total_vram_gb:.1f} GB）。"
        )
        legacy.record_run_event(
            "gpu_asr_parallel",
            total_vram_gb=round(total_vram_gb, 2),
            min_vram_gb=legacy.PARALLEL_GPU_ASR_MIN_VRAM_GB,
        )
        parallel_results = run_parallel_stages(
            legacy,
            {"firered": run_firered_stage, "qwen": run_qwen_stage},
            thread_name_prefix="gpu-asr",
        )
        firered_tokens = parallel_results["firered"]
        qwen_chunks = parallel_results["qwen"]
        # Both recognizers deliberately return [] on CUDA/OOM failure. Retry only
        # the failed side after its sibling has released VRAM, preserving correctness.
        if not firered_tokens:
            print("   [显存回退] FireRed 并行结果为空，释放另一模型后串行重试。")
            legacy.record_run_event("gpu_asr_parallel_fallback", stage="firered")
            firered_tokens = run_firered_stage()
        if not qwen_chunks:
            print("   [显存回退] Qwen3 并行结果为空，释放另一模型后串行重试。")
            legacy.record_run_event("gpu_asr_parallel_fallback", stage="qwen")
            qwen_chunks = run_qwen_stage()
    else:
        if legacy.PARALLEL_GPU_ASR:
            legacy.record_run_event(
                "gpu_asr_parallel_skipped",
                total_vram_gb=round(total_vram_gb, 2),
                min_vram_gb=legacy.PARALLEL_GPU_ASR_MIN_VRAM_GB,
            )
        firered_tokens = run_firered_stage()
        qwen_chunks = None

    primary_dependency = {"moss": moss_payload["segments"], "vad": speech_regions, "firered": firered_tokens}
    stage_index = 5
    segments = legacy.run_timed_stage(
        stage_index,
        stage_total,
        "筛选 MOSS 主播并建立主稿",
        "CPU",
        lambda: legacy.run_cached_stage(
            "firered_primary",
            cache_context,
            lambda: build_moss_host_primary_segments(
                moss_payload,
                firered_tokens,
                speech_regions,
                audio_seconds,
                legacy,
                shared_audio=shared_audio,
                runtime_context=runtime_context,
            ),
            encoder=legacy.serialize_segments,
            decoder=legacy.deserialize_segments,
            should_cache=bool,
            extra_signature=primary_dependency,
        ),
    )

    if qwen_chunks is None:
        qwen_chunks = run_qwen_stage()
    stage_index = 6
    segments = attach_qwen_review_evidence(segments, qwen_chunks, legacy)
    add_qwen_skeleton_gap_review_items(
        segments,
        qwen_chunks,
        moss_payload,
        legacy,
    )
    segments = reconcile_firered_moss_qwen(segments, legacy)

    stage_index += 1
    segments = legacy.run_timed_stage(
        stage_index,
        stage_total,
        "FireRedASR2-LLM 争议片段复核",
        "可选远程/高显存 GPU",
        lambda: legacy.run_cached_stage(
            "firered_llm",
            cache_context,
            lambda: safe_review_disputes_with_firered_llm(segments, shared_audio, legacy),
            encoder=legacy.serialize_segments,
            decoder=legacy.deserialize_segments,
            should_cache=lambda rows: any(segment.firered_llm_text for segment in rows),
            extra_signature={
                "segments": legacy.serialize_segments(segments),
                "endpoint": os.environ.get("FIRERED_LLM_ENDPOINT", ""),
                "model": _path_signature(paths["firered_llm"]),
                "worker": _path_signature(paths["firered_llm_worker"]),
                "min_gpu_gb": FIRERED_LLM_MIN_GPU_GB,
            },
        ),
    )

    stage_index += 1
    segments = legacy.run_timed_stage(
        stage_index,
        stage_total,
        "云端模型受限校对",
        "OpenAI 兼容 API+本地安全裁决",
        lambda: legacy.run_cached_stage(
            "polished",
            cache_context,
            lambda: legacy.polish_subtitles(segments, base_name, cache_context),
            encoder=legacy.serialize_segments,
            decoder=legacy.deserialize_segments,
            extra_signature=legacy.serialize_segments(segments),
        ),
    )
    # 即使命中旧缓存，仍在本地执行术语与成片规则；后续全文断句会依据
    # 规整后的文字和说话人插话边界重新计算缓存签名。
    segments = legacy.apply_editorial_segment_rules(segments)

    stage_index += 1
    cues = legacy.run_timed_stage(
        stage_index,
        stage_total,
        "云端模型全文智能断句",
        "OpenAI 兼容 API+说话人插话保护",
        lambda: legacy.run_cached_stage(
            "grouped",
            cache_context,
            lambda: legacy.add_safe_punctuation(
                legacy.group_subtitles(
                    segments,
                    firered_tokens=firered_tokens,
                    speech_regions=speech_regions,
                    protect_all_source_boundaries=False,
                    cache_context=cache_context,
                )
            ),
            encoder=legacy.serialize_cues,
            decoder=legacy.deserialize_cues,
            extra_signature={
                "segments": legacy.serialize_segments(segments),
                "firered_tokens": firered_tokens,
                "speech_regions": speech_regions,
            },
        ),
    )

    stage_index += 1
    cues = legacy.run_timed_stage(
        stage_index,
        stage_total,
        "锁定 MOSS 主播最终时间轴",
        "CPU+帧量化",
        lambda: legacy.run_cached_stage(
            "final_timing",
            cache_context,
            lambda: finalize_cues(
                cues,
                segments,
                firered_tokens,
                speech_regions,
                audio_seconds,
                timeline_fps,
                legacy,
            ),
            encoder=legacy.serialize_cues,
            decoder=legacy.deserialize_cues,
            extra_signature={
                "cues": legacy.serialize_cues(cues),
                "mode": "moss-outer-strict-vad-onset-firered-inner-tail200-gap500-editorial-v5",
            },
        ),
    )

    stage_index += 1
    return complete_media_run(
        cues=cues,
        segments=segments,
        file_index=file_index,
        file_total=file_total,
        started=started,
        audio_seconds=audio_seconds,
        txt_path=txt_path,
        srt_path=srt_path,
        stage_index=stage_index,
        stage_total=stage_total,
        legacy=legacy,
        runtime_context=runtime_context,
    )


def main(legacy):
    print("MOSS + FireRedVAD + FireRedASR2-AED + Qwen3 字幕生成器")
    print(f"[运行配置] {legacy.RUNTIME_SETTINGS_PATH}")
    print(
        "[模型] "
        f"Qwen3-ASR={legacy.QWEN_ASR_MODEL} | "
        f"校对={legacy.LLM_MODEL} | 断句={legacy.GROUP_LLM_MODEL}"
    )
    for warning in legacy.RUNTIME_SETTINGS_WARNINGS:
        print(f"[配置警告] {warning}")
    try:
        startup_self_test = legacy.run_startup_self_test()
    except Exception as exc:
        print(f"\n[启动自测失败] {exc}")
        legacy.pause_exit(1)
    print(
        f"[启动自测通过] {startup_self_test['id']}："
        f"{startup_self_test['checks']} 项关键护栏正常"
    )
    try:
        from twobyteasr.ui import run_desktop_app
    except ImportError as exc:
        print(f"\n[界面依赖缺失] {exc}")
        print("请运行 setup_environment.bat 安装 PySide6 与 Qt 图标库。")
        legacy.pause_exit(1)
    exit_code = run_desktop_app(legacy, sys.modules[__name__], startup_self_test)
    legacy.pause_exit(exit_code)
