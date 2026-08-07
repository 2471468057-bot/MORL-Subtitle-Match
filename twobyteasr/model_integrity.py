"""Integrity checks for pinned local models that load code or pickle data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class ModelIntegrityError(RuntimeError):
    """Raised before an untrusted or changed model artifact can be loaded."""


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_dependency_lock(root: Path | None = None) -> dict:
    root = Path(root) if root is not None else project_root()
    with (root / "dependencies.lock.json").open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if payload.get("schema_version") != 1:
        raise ModelIntegrityError("不支持的依赖锁文件版本。")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_files(
    model_name: str,
    model_root: str | Path | None = None,
    *,
    root: Path | None = None,
) -> Path:
    """Verify all security-sensitive files listed for a pinned model."""
    root = Path(root) if root is not None else project_root()
    lock = load_dependency_lock(root)
    try:
        spec = lock["models"][model_name]
    except KeyError as exc:
        raise ModelIntegrityError(f"依赖锁中没有模型：{model_name}") from exc
    target = Path(model_root) if model_root is not None else root / spec["path"]
    target = target.resolve()
    expected_root = root.resolve()
    try:
        target.relative_to(expected_root)
    except ValueError as exc:
        raise ModelIntegrityError(f"拒绝校验项目目录外的模型：{target}") from exc

    for relative, expected in spec.get("sha256", {}).items():
        candidate = (target / relative).resolve()
        try:
            candidate.relative_to(target)
        except ValueError as exc:
            raise ModelIntegrityError(f"模型锁包含非法路径：{relative}") from exc
        if not candidate.is_file():
            raise ModelIntegrityError(f"模型关键文件缺失：{candidate}")
        actual = sha256_file(candidate)
        if actual.lower() != str(expected).lower():
            raise ModelIntegrityError(
                f"模型文件校验失败，已拒绝加载：{candidate.name}。"
                "请删除对应模型目录后重新运行 download_models.bat。"
            )
    return target


def locked_model(model_name: str, *, root: Path | None = None) -> dict:
    return dict(load_dependency_lock(root)["models"][model_name])
