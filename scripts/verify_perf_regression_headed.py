"""Rerunnable performance regression case on a private desktop (source or frozen EXE).

Usage:
    python scripts/verify_perf_regression_headed.py --project P.2byteproj --seek-cache SEEKDIR \
        --output tmp/<new dir> [--exe dist/2ByteASR/2ByteASR.exe] [--profile-from WARM_PROFILE] \
        [--phases idle,drag-repeat,...] [--profile-actions multi-press]

The project is copied (the original is only read and its SHA is checked), the
seek cache is hard-linked, all user data goes to an isolated profile. Results:
<output>/perf.json (twobyteasr.perf_regression_audit) plus process logs.
Compare runs with scripts/summarize_perf_regression.py.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--seek-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--profile-from", type=Path, help="copy a warmed isolated profile")
    parser.add_argument("--phases", default="")
    parser.add_argument("--profile-actions", default="")
    parser.add_argument("--drag-repeats", default="5")
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / "tmp") or out.exists():
        raise SystemExit("Fresh repository tmp output required")
    out.mkdir(parents=True)
    data = args.project.read_bytes()
    (out / "project.2byteproj").write_bytes(data)
    for source in args.seek_cache.resolve().rglob("*"):
        if not source.is_file() or source.suffix == ".lock":
            continue
        target = out / "seek" / source.relative_to(args.seek_cache.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() in {".mkv", ".mp4"}:
            os.link(source, target)
        else:
            shutil.copy2(source, target)
    if args.profile_from:
        shutil.copytree(args.profile_from, out / "profile")
    env = os.environ.copy()
    env.update(TWOBYTEASR_TEST_ROOT=str(out / "profile"), TWOBYTEASR_STARTUP_TRACE=str(out / "startup.jsonl"),
               TWOBYTEASR_SKIP_FIRST_RUN_WIZARD="1", TWOBYTEASR_STARTUP_OPEN_STUDIO="1",
               TWOBYTEASR_STARTUP_SIZE="1600x950", TWOBYTEASR_STARTUP_PROJECT=str(out / "project.2byteproj"),
               TWOBYTEASR_SEEK_CACHE_ROOT=str(out / "seek"), TWOBYTEASR_ACCEPTANCE_SCENARIO="perf-regression",
               TWOBYTEASR_ACCEPTANCE_DIR=str(out), PERF_DRAG_REPEATS=args.drag_repeats,
               PERF_TIMEOUT_S=str(max(60, args.timeout - 60)), QT_QPA_PLATFORM="windows", PYTHONUTF8="1")
    if args.phases:
        env["PERF_PHASES"] = args.phases
    if args.profile_actions:
        env["PERF_PROFILE_ACTIONS"] = args.profile_actions
    for key in ("QT_SCALE_FACTOR", "QT_ENABLE_HIGHDPI_SCALING", "QT_FONT_DPI"):
        env.pop(key, None)
    from isolated_windows_desktop import run_on_desktop
    command = [str(args.exe.resolve())] if args.exe else [sys.executable, "-B", str(ROOT / "quick_start.py")]
    code = run_on_desktop(command, cwd=ROOT, env=env, output=out / "process", timeout=args.timeout)
    path = out / "perf.json"
    result = json.loads(path.read_text("utf8")) if path.is_file() else {}
    result.update(exit_code=code, original_unchanged=args.project.read_bytes() == data,
                  original_sha256=hashlib.sha256(data).hexdigest(), runner_exe=str(args.exe or "source"))
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf8")
    print(json.dumps({k: result.get(k) for k in ("exit_code", "finished", "gui_shutdown", "errors",
                                                 "original_unchanged", "cue_count")}, ensure_ascii=False)[:2000])
    return 0 if code == 0 and result.get("finished") and result.get("original_unchanged") else 1


if __name__ == "__main__":
    raise SystemExit(main())
