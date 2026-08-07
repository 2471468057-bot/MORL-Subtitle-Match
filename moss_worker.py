"""Run MOSS-Transcribe-Diarize in its isolated Transformers 5 environment."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import time
from pathlib import Path


DEFAULT_PROMPT = (
    "请将音频转写为文本，每一段需以起始时间戳和说话人编号"
    "（[S01]、[S02]、[S03]…）开头，正文为对应的语音内容，"
    "并在段末标注结束时间戳，以清晰标明该段语音范围。"
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio")
    parser.add_argument("--manifest")
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--checkpoint-dir", default="")
    parser.add_argument("--run-signature", default="")
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


def resolve_model(requested):
    local_model = Path(__file__).resolve().parent / "models" / "MOSS-Transcribe-Diarize"
    if (local_model / "config.json").is_file():
        return str(local_model)
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
    if not args.audio and not args.manifest:
        raise ValueError("--audio 与 --manifest 至少提供一个。")
    # Transformers 的 trust_remote_code 默认写入用户级 ~/.cache；在 Windows
    # 受限目录或便携式工作流中可能没有权限，改用本次任务旁的临时缓存。
    module_cache = Path(args.output).resolve().parent / ".hf_modules_cache"
    module_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_MODULES_CACHE", str(module_cache))
    import torch
    from transformers import AutoModelForCausalLM, AutoProcessor

    from moss_transcribe_diarize import parse_transcript
    from moss_transcribe_diarize.inference_utils import (
        build_transcription_messages,
        generate_transcription,
        resolve_device,
    )

    device = resolve_device("auto")
    if device.type != "cuda":
        raise RuntimeError("MOSS 当前工作流要求 CUDA GPU。")
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model_source = resolve_model(args.model)
    from twobyteasr.model_integrity import verify_model_files

    verify_model_files("moss", model_source)
    prompt = DEFAULT_PROMPT

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    model_load_started = time.perf_counter()
    print(f"加载 MOSS：{model_source}", flush=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_source,
        trust_remote_code=True,
        dtype="auto",
    ).to(dtype=dtype).to(device).eval()
    processor = AutoProcessor.from_pretrained(model_source, trust_remote_code=True)
    model_load_seconds = time.perf_counter() - model_load_started
    print(f"MOSS 模型加载完成：{model_load_seconds:.1f} 秒。", flush=True)
    if args.manifest:
        with open(args.manifest, "r", encoding="utf-8") as file:
            jobs = json.load(file).get("jobs", [])
    else:
        jobs = [{"chunk_id": 1, "audio": args.audio, "offset": 0.0}]
    if not jobs:
        raise ValueError("MOSS manifest 中没有任务。")

    chunk_results = []
    chunk_timings = []
    for job_index, job in enumerate(jobs, 1):
        cached = load_chunk_checkpoint(
            args.checkpoint_dir,
            args.run_signature,
            job,
            job_index,
        )
        if cached is not None:
            cached["group_id"] = str(job.get("group_id", cached.get("group_id", "default")))
            cached["checkpoint_dir"] = str(job.get("checkpoint_dir", cached.get("checkpoint_dir", "")))
            cached["run_signature"] = str(job.get("run_signature", cached.get("run_signature", "")))
            chunk_results.append(cached)
            print(
                f"[块 {job_index}/{len(jobs)}] 命中断点缓存："
                f"{len(cached['segments'])} 段。",
                flush=True,
            )
            continue
        audio_path = str(job["audio"])
        duration = float(job.get("duration") or media_duration(audio_path))
        max_new_tokens = max(2048, min(8192, int(math.ceil(duration * 12.0))))
        print(
            f"[块 {job_index}/{len(jobs)}] {float(job.get('offset', 0.0)):.1f}s 起，"
            f"音频 {duration:.1f}s，最多 {max_new_tokens} tokens",
            flush=True,
        )
        chunk_started = time.perf_counter()
        last_report = {"tokens": 0}

        def report_tokens(count):
            if count - last_report["tokens"] >= 100:
                last_report["tokens"] = count
                print(f"[块 {job_index}/{len(jobs)}] 已生成 {count} tokens", flush=True)

        messages = build_transcription_messages(audio_path, prompt=prompt)
        result = generate_transcription(
            model,
            processor,
            messages,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            device=device,
            dtype=dtype,
            token_callback=report_tokens,
        )
        generated_tokens = int(result.get("generated_tokens", 0))
        if generated_tokens >= int(max_new_tokens * 0.96) and max_new_tokens < 8192:
            retry_tokens = min(8192, int(math.ceil(max_new_tokens * 1.5)))
            print(
                f"[块 {job_index}/{len(jobs)}] 输出接近 token 上限，"
                f"提高到 {retry_tokens} 后重试一次。",
                flush=True,
            )
            last_report["tokens"] = 0
            result = generate_transcription(
                model,
                processor,
                messages,
                max_new_tokens=retry_tokens,
                do_sample=False,
                device=device,
                dtype=dtype,
                token_callback=report_tokens,
            )
            max_new_tokens = retry_tokens
        segments = []
        for segment in parse_transcript(result["text"]):
            start = max(0.0, float(segment.start))
            end = max(start + 0.01, float(segment.end))
            text = str(segment.text).strip()
            if not text:
                continue
            segments.append(
                {
                    "start": start,
                    "end": end,
                    "speaker": str(segment.speaker).strip("[] ") or "S00",
                    "text": text,
                }
            )
        segments.sort(key=lambda item: (item["start"], item["end"]))
        if not segments:
            raise RuntimeError(f"MOSS 第 {job_index} 块无法解析为说话人时间段。")
        chunk_result = {
            "chunk_id": int(job.get("chunk_id", job_index)),
            "group_id": str(job.get("group_id", "default")),
            "offset": float(job.get("offset", 0.0)),
            "duration": duration,
            "max_new_tokens": max_new_tokens,
            "prompt_tokens": int(result.get("prompt_len", 0)),
            "generated_tokens": int(result.get("generated_tokens", 0)),
            "raw_text": result["text"],
            "segments": segments,
            "checkpoint_dir": str(job.get("checkpoint_dir", "")),
            "run_signature": str(job.get("run_signature", "")),
        }
        chunk_results.append(chunk_result)
        save_chunk_checkpoint(
            args.checkpoint_dir,
            args.run_signature,
            chunk_result,
        )
        chunk_elapsed = time.perf_counter() - chunk_started
        chunk_timings.append(
            {
                "chunk_id": int(job.get("chunk_id", job_index)),
                "audio_seconds": round(duration, 3),
                "elapsed_seconds": round(chunk_elapsed, 3),
            }
        )
        print(
            f"[块 {job_index}/{len(jobs)} 完成] {len(segments)} 段，"
            f"{len({item['speaker'] for item in segments})} 位说话人，"
            f"生成 {int(result.get('generated_tokens', 0))} tokens，"
            f"耗时 {chunk_elapsed:.1f} 秒",
            flush=True,
        )
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    payload = {
        "model": model_source,
        "title": args.title,
        "chunks": chunk_results,
        "generated_tokens": sum(item["generated_tokens"] for item in chunk_results),
        "performance": {
            "model_load_seconds": round(model_load_seconds, 3),
            "chunk_timings": chunk_timings,
            "peak_allocated_gb": round(torch.cuda.max_memory_allocated() / 1024**3, 3),
            "peak_reserved_gb": round(torch.cuda.max_memory_reserved() / 1024**3, 3),
        },
    }
    if len(chunk_results) == 1:
        payload.update(chunk_results[0])
    atomic_write_json(args.output, payload)
    print(
        f"全部完成：{len(chunk_results)} 块；峰值显存保留 "
        f"{payload['performance']['peak_reserved_gb']:.2f} GB。",
        flush=True,
    )


if __name__ == "__main__":
    main()
