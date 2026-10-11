# SPDX-License-Identifier: GPL-3.0-only
"""Build the public release commit from a frozen build snapshot.

The commit's parent is the curated public line (``origin/main``), never the
private development history.  Only program-source paths are updated from the
snapshot that was actually built; README, product docs, images and other
curated files of the public line are left as they are.  Large prebuilt inputs
(wheels, tools, renderer/node_modules) stay in the Source attachment, not Git.

    python -B scripts/release_public_tree.py --stage tmp/release-065/build-r1/source \
        --base origin/main --branch release/v0.6.5 --message "2ByteASR 0.6.5 [skip ci]"

Nothing is pushed.  The working tree and index are not touched (a temporary
index is used).  A scan report lists every added/changed blob checked for
credentials, private keys, personal paths and media.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPED_PREFIXES = ("twobyteasr/", "scripts/", "packaging/", "installer/", "launcher/", "lexicons/",
                   "licenses/", ".github/workflows/", "docs/releases/", "renderer/", "tests/")
ROOT_FILES = {"LICENSE", "THIRD_PARTY_NOTICES.md", "PROJECT_LICENSE.md", "SOURCE_DELIVERY.md",
              "BUILD_FROM_SOURCE.md", "CHANGELOG.md", "CONTRIBUTING.md", "UPDATING.md", "RELEASING.md",
              "2byteasr_version.json", "dependencies.lock.json", "game_profiles.json", "glossary.txt",
              "requirements-main.txt"}
EXCLUDED_PREFIXES = ("renderer/node_modules/", "renderer/public/", "wheels/", "tools/", "tests/data/")
MEDIA_SUFFIXES = {".wav", ".mp3", ".mp4", ".flv", ".mov", ".mkv", ".m4a", ".aac", ".log", ".2byteproj",
                  ".2byteasr", ".safetensors", ".ckpt", ".pt", ".pth", ".exe", ".dll", ".pyd", ".zip", ".whl"}
PATTERNS = {
    "credential": re.compile(rb"\b(?:sk-[A-Za-z0-9_-]{32,}|hf_[A-Za-z0-9]{30,}|gh[pousr]_[A-Za-z0-9]{32,}"
                             rb"|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|xox[abp]-[A-Za-z0-9-]{20,})"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
    "signing_key_record": re.compile(rb'"dpapi"\s*:\s*"[A-Za-z0-9+/=]{40,}'),
    "developer_home": re.compile(rb"(?i)[a-z]:[\\/]+users[\\/]+12[\\/]"),
    "email": re.compile(rb"[A-Za-z0-9._%+-]+@(?:gmail|qq|163|126|outlook|hotmail|foxmail)\.com"),
}


# Findings a person has looked at; anything else blocks the commit.
REVIEWED = {
    ("tests/test_export_target_audit.py", "developer_home"):
        "synthetic test path containing the local Windows account name; no personal data",
}


def git(*args, env=None, input_bytes=None) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, env=env, input=input_bytes, capture_output=True, check=True)
    return result.stdout.decode("utf-8", errors="replace").strip()


def in_scope(rel: str) -> bool:
    if rel.startswith(EXCLUDED_PREFIXES) or Path(rel).suffix.lower() in MEDIA_SUFFIXES:
        return False
    if "/" not in rel:
        return rel in ROOT_FILES or (rel.endswith(".py") and not rel.startswith("tmp_"))
    if rel.startswith("tests/") and not (rel.endswith(".py") or rel.startswith("tests/fixtures/")):
        return False
    return rel.startswith(SCOPED_PREFIXES)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--extra", nargs="*", default=[], help="Repository files to add after the build (docs/releases)")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    stage = args.stage.resolve()
    base = git("rev-parse", args.base)
    if git("branch", "--list", args.branch):
        raise SystemExit(f"Local branch {args.branch} exists; choose a new name")
    base_files = set(git("ls-tree", "-r", "--name-only", base).splitlines())
    stage_files = {p.relative_to(stage).as_posix(): p for p in stage.rglob("*")
                   if p.is_file() and ".git" not in p.relative_to(stage).parts and "__pycache__" not in p.parts}
    for extra in args.extra:
        stage_files[Path(extra).as_posix()] = ROOT / extra
    with tempfile.TemporaryDirectory() as folder:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(folder) / "index"))
        git("read-tree", base, env=env)
        changed, added, removed, findings, reviewed = [], [], [], [], []
        for rel, source in sorted(stage_files.items()):
            if not in_scope(rel):
                continue
            blob = git("hash-object", "-w", f"--path={rel}", str(source))
            current = git("ls-files", "-s", "--", rel, env=env)
            if current and current.split()[1] == blob:
                continue
            data = source.read_bytes()
            for name, pattern in PATTERNS.items():
                if pattern.search(data):
                    item = {"path": rel, "category": name}
                    reason = REVIEWED.get((rel, name)) or (
                        "third-party author address inside an upstream licence/notice"
                        if name == "email" and rel.startswith("licenses/") else None)
                    (reviewed if reason else findings).append({**item, "reviewed": reason} if reason else item)
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{rel}", env=env)
            (changed if current else added).append(rel)
        for rel in sorted(base_files):
            if in_scope(rel) and rel not in stage_files and not (ROOT / rel).exists():
                git("update-index", "--force-remove", "--", rel, env=env)
                removed.append(rel)
        tree = git("write-tree", env=env)
    report = {"base": base, "tree": tree, "added": added, "changed": changed, "removed": removed,
              "findings": findings, "reviewed_findings": reviewed, "scope": {"prefixes": SCOPED_PREFIXES, "root_files": sorted(ROOT_FILES),
                                              "excluded": EXCLUDED_PREFIXES}}
    if findings:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
        raise SystemExit(f"Scan findings in {len(findings)} files; see {args.report}. No commit created.")
    commit = git("commit-tree", tree, "-p", base, "-m", args.message)
    git("branch", args.branch, commit)
    report["commit"] = commit
    report["branch"] = args.branch
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items() if k != "scope"}))


if __name__ == "__main__":
    main()
