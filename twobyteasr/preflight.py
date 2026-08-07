"""Fast, dependency-free startup checks used by sdewa.bat."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version as package_version
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = PROJECT_ROOT / "dependencies.lock.json"


@dataclass(frozen=True)
class PreflightIssue:
    code: str
    message: str
    recovery: str
    fatal: bool = True


@dataclass
class PreflightReport:
    issues: list[PreflightIssue] = field(default_factory=list)
    checks: int = 0

    @property
    def ok(self) -> bool:
        return not any(issue.fatal for issue in self.issues)


def load_dependency_lock(project_root: Path = PROJECT_ROOT) -> dict:
    path = project_root / "dependencies.lock.json"
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schema_version") != 1:
        raise ValueError("dependencies.lock.json schema_version 必须为 1")
    if not isinstance(payload.get("sources"), dict) or not isinstance(payload.get("models"), dict):
        raise ValueError("dependencies.lock.json 缺少 sources 或 models")
    return payload


def _required_paths(root: Path, spec: dict) -> Iterable[Path]:
    base = root / Path(str(spec["path"]))
    for relative in spec.get("required_files", []):
        yield base / Path(str(relative))


def run_preflight(
    project_root: Path = PROJECT_ROOT,
    *,
    python_version: tuple[int, int] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> PreflightReport:
    report = PreflightReport()
    try:
        lock = load_dependency_lock(project_root)
        report.checks += 1
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        report.issues.append(
            PreflightIssue("invalid_lock", f"依赖版本清单不可用：{exc}", "请重新获取完整项目源码。")
        )
        return report

    actual_python = python_version or (sys.version_info.major, sys.version_info.minor)
    expected_python = tuple(int(part) for part in str(lock["python"]["main"]).split(".")[:2])
    report.checks += 1
    if actual_python != expected_python:
        report.issues.append(
            PreflightIssue(
                "wrong_python",
                f"主流程需要 Python {expected_python[0]}.{expected_python[1]}，当前为 {actual_python[0]}.{actual_python[1]}。",
                "请运行 setup_environment.bat 重建固定环境。",
            )
        )

    for command in ("ffmpeg", "ffprobe", "nvidia-smi"):
        report.checks += 1
        if which(command) is None:
            recovery = (
                "请安装 FFmpeg 并把 ffmpeg/ffprobe 加入 PATH。"
                if command != "nvidia-smi"
                else "请安装或更新 NVIDIA 显卡驱动。"
            )
            report.issues.append(PreflightIssue(f"missing_{command}", f"找不到 {command}。", recovery))

    for package_name in ("PySide6", "QtAwesome", "kaldiio", "kaldi-native-fbank"):
        report.checks += 1
        try:
            package_version(package_name)
        except PackageNotFoundError:
            report.issues.append(
                PreflightIssue(
                    f"missing_package_{package_name.lower()}",
                    f"主环境缺少运行依赖：{package_name}。",
                    "请运行 setup_environment.bat 更新固定主环境。",
                )
            )

    source_markers = {
        "moss": "pyproject.toml",
        "firered": "fireredasr2s/__init__.py",
    }
    for name, marker in source_markers.items():
        report.checks += 1
        spec = lock["sources"].get(name, {})
        source_path = project_root / Path(str(spec.get("path", ""))) / Path(marker)
        if not source_path.is_file():
            report.issues.append(
                PreflightIssue(
                    f"missing_source_{name}",
                    f"缺少第三方源码：{name}。",
                    "请运行 setup_environment.bat。",
                )
            )

    moss_python = project_root / ".venv-moss" / "Scripts" / "python.exe"
    report.checks += 1
    if not moss_python.is_file():
        report.issues.append(
            PreflightIssue("missing_moss_env", "缺少 MOSS Python 环境。", "请运行 setup_environment.bat。")
        )

    for name, spec in lock["models"].items():
        report.checks += 1
        missing = [str(path.relative_to(project_root)) for path in _required_paths(project_root, spec) if not path.is_file()]
        if missing:
            report.issues.append(
                PreflightIssue(
                    f"missing_model_{name}",
                    f"模型 {spec.get('repository', name)} 缺少关键文件：{', '.join(missing)}",
                    "请运行 download_models.bat；已完成的文件会复用。",
                )
            )
    return report


def main() -> int:
    report = run_preflight()
    if report.ok:
        print(f"[启动预检通过] {report.checks} 项环境与模型检查正常。")
        return 0
    print("[启动预检失败]")
    for issue in report.issues:
        level = "错误" if issue.fatal else "警告"
        print(f"- [{level}] {issue.message}")
        print(f"  处理：{issue.recovery}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
