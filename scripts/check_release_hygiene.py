"""Offline checks for files intended to be published to GitHub."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git",
    ".mimosa",
    ".venv-main",
    ".venv-moss",
    ".pytest_cache",
    "__pycache__",
    "archive",
    "backups",
    "models",
    "MOSS-Transcribe-Diarize",
    "FireRedASR2S",
    "outputs",
    "output",
    "tmp",
    "artifacts",
    "dist",
    "reports",
    "review_tracks",
}
FORBIDDEN_PREFIXES = (
    ".mimosa/",
    "archive/",
    "backups/",
    "models/",
    "outputs/",
    "reports/",
    "review_tracks/",
    "output/",
    "tmp/",
    "artifacts/",
    "dist/",
    "third_party/MOSS-Transcribe-Diarize/",
    "third_party/FireRedASR2S/",
)
FORBIDDEN_SUFFIXES = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".avi",
    ".mp3",
    ".wav",
    ".m4a",
    ".flac",
    ".aac",
    ".safetensors",
    ".ckpt",
    ".pth",
    ".exe",
}
TEXT_SUFFIXES = {".py", ".md", ".json", ".txt", ".yml", ".yaml", ".bat", ".ps1", ".source"}
TEXT_NAMES = {".gitignore", ".gitattributes"}
GENERATED_BINARY_NAMES = {"2ByteASR.exe", "ShortcutIdentity.exe"}
FORBIDDEN_SECRET_NAMES = {"secrets.json", "secrets.dat"}
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"\bhf_[A-Za-z0-9]{24,}\b"),
)
PRIVATE_PATH_PATTERNS = (
    re.compile(r"\b[A-Za-z]:\\Users\\[^\\\s]+\\", re.IGNORECASE),
)


def public_files() -> list[Path]:
    try:
        output = subprocess.check_output(
            [
                "git",
                "-c",
                f"safe.directory={ROOT.as_posix()}",
                "-C",
                str(ROOT),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            stderr=subprocess.DEVNULL,
        )
        if output:
            return [ROOT / item.decode("utf-8") for item in output.split(b"\0") if item]
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        pass
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.name not in GENERATED_BINARY_NAMES
        and not any(part in EXCLUDED_DIRS for part in path.relative_to(ROOT).parts)
    ]


def main() -> int:
    errors: list[str] = []
    files = public_files()
    if not (ROOT / "LICENSE").is_file():
        errors.append("缺少 LICENSE")
    if not (ROOT / "THIRD_PARTY_NOTICES.md").is_file():
        errors.append("缺少 THIRD_PARTY_NOTICES.md")

    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if path.name.lower() in FORBIDDEN_SECRET_NAMES:
            errors.append(f"不应发布的密钥文件：{relative}")
        if relative.startswith(FORBIDDEN_PREFIXES):
            errors.append(f"不应发布的路径：{relative}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"不应发布的大文件类型：{relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            errors.append(f"不是有效 UTF-8：{relative}")
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"疑似真实密钥：{relative}")
                break
        for pattern in PRIVATE_PATH_PATTERNS:
            if pattern.search(text):
                errors.append(f"疑似本机用户绝对路径：{relative}")
                break

    if errors:
        print("[发布检查失败]")
        for error in sorted(set(errors)):
            print(f"- {error}")
        return 1
    print(f"[发布检查通过] 已检查 {len(files)} 个公开候选文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
