"""Optional FireRedASR2-LLM worker for disputed clips on a high-memory GPU."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-dir", required=True)
    return parser.parse_args()


def atomic_write(path, payload):
    output = Path(path)
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def main():
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    source_dir = script_dir / "third_party" / "FireRedASR2S"
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))

    from fireredasr2s.fireredasr2 import FireRedAsr2, FireRedAsr2Config

    with open(args.manifest, "r", encoding="utf-8") as file:
        jobs = json.load(file).get("jobs", [])
    config = FireRedAsr2Config(
        use_gpu=True,
        use_half=True,
        beam_size=1,
        decode_min_len=0,
        repetition_penalty=3.0,
        llm_length_penalty=1.0,
        temperature=1.0,
    )
    model = FireRedAsr2.from_pretrained("llm", args.model_dir, config)
    results = []
    for index, job in enumerate(jobs, 1):
        segment_id = int(job["segment_id"])
        value = model.transcribe([f"dispute_{segment_id}"], [job["path"]])
        text = value[0].get("text", "") if value else ""
        results.append({"segment_id": segment_id, "text": text})
        print(f"完成争议片段 {index}/{len(jobs)}", flush=True)
    atomic_write(args.output, {"results": results})


if __name__ == "__main__":
    main()
