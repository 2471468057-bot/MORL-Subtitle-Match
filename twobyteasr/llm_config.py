"""Non-secret endpoint settings and local-only LLM credential storage."""

from __future__ import annotations

import ctypes
import json
import os
import tempfile
from ctypes import wintypes
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit


PROVIDER_PRESETS = {
    "bailian": {
        "label": "阿里云百炼",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "openai_compatible": {
        "label": "OpenAI 兼容",
        "base_url": "https://api.openai.com/v1",
    },
    "custom": {
        "label": "自定义服务",
        "base_url": "",
    },
}

STAGE_SECRET_NAMES = {
    "polish": ("POLISH_LLM_API_KEY", "DASHSCOPE_API_KEY", "2BYTEASR_DASHSCOPE_API_KEY"),
    "group": ("GROUP_LLM_API_KEY", "DASHSCOPE_API_KEY", "2BYTEASR_DASHSCOPE_API_KEY"),
}


def secrets_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return base / "2ByteASR" / "secrets.dat"


def legacy_secrets_path() -> Path:
    return secrets_path().with_name("secrets.json")


def old_project_secrets_path() -> Path:
    """项目改名前（QwenASR 目录）保存的 DPAPI 密钥文件，用于一次性迁移。"""
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return base / "QwenASR" / "secrets.dat"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    return (
        _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))),
        buffer,
    )


def _dpapi(operation: str, data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("本机密钥存储只支持 Windows DPAPI。")
    source, source_buffer = _blob(data)
    destination = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    flags = 0x1  # CRYPTPROTECT_UI_FORBIDDEN
    if operation == "protect":
        ok = crypt32.CryptProtectData(
            ctypes.byref(source),
            "2ByteASR local secrets",
            None,
            None,
            None,
            flags,
            ctypes.byref(destination),
        )
    else:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(source),
            None,
            None,
            None,
            None,
            flags,
            ctypes.byref(destination),
        )
    del source_buffer
    if not ok:
        raise OSError(ctypes.get_last_error(), "Windows DPAPI operation failed")
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree(destination.pbData)


def _decode_payload(data: bytes) -> dict:
    payload = json.loads(data.decode("utf-8"))
    return payload if isinstance(payload, dict) else {"schema": 2}


def _write_encrypted_secrets(payload: dict) -> Path:
    path = secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        protected = _dpapi("protect", plaintext)
        with os.fdopen(handle, "wb") as stream:
            stream.write(protected)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        try:
            legacy_secrets_path().unlink()
        except OSError:
            pass
    except BaseException:
        try:
            os.close(handle)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return path


def _read_secrets() -> dict:
    try:
        path = secrets_path()
        if path.is_file():
            return _decode_payload(_dpapi("unprotect", path.read_bytes()))
        old_path = old_project_secrets_path()
        if old_path.is_file():
            # 项目改名（QwenASR -> 2ByteASR）后的密钥迁移；DPAPI 为当前用户级加密，可直接复制。
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(old_path.read_bytes())
            payload = _decode_payload(_dpapi("unprotect", path.read_bytes()))
            try:
                old_path.unlink()
            except OSError:
                pass
            return payload
        payload = json.loads(legacy_secrets_path().read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload["schema"] = 2
            _write_encrypted_secrets(payload)
    except (OSError, ValueError, TypeError):
        return {"schema": 2}
    return payload if isinstance(payload, dict) else {"schema": 2}


def read_secret_value(*names: str) -> tuple[str, str]:
    for name in names:
        value = str(os.environ.get(name, "") or "").strip()
        if value:
            return value, f"环境变量 {name}"
    payload = _read_secrets()
    for name in names:
        value = str(payload.get(name, "") or "").strip()
        if value:
            return value, f"Windows DPAPI / {name}"
    return "", "未配置"


def resolve_api_key(stage: str) -> tuple[str, str]:
    return read_secret_value(*STAGE_SECRET_NAMES[stage])


def save_api_keys(*, polish_key: str = "", group_key: str = "", share_key: bool = False) -> Path:
    """Save only values explicitly entered by the user; blank fields preserve current keys."""
    payload = _read_secrets()
    payload["schema"] = 2
    polish_key = str(polish_key or "").strip()
    group_key = str(group_key or "").strip()
    if polish_key:
        payload["POLISH_LLM_API_KEY"] = polish_key
    if share_key and polish_key:
        payload["GROUP_LLM_API_KEY"] = polish_key
    elif group_key:
        payload["GROUP_LLM_API_KEY"] = group_key

    return _write_encrypted_secrets(payload)


def normalize_base_url(value: str) -> str:
    base = str(value or "").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    return base


def endpoint_from_settings(settings: dict, stage: str) -> dict:
    models = settings.get("models", {})
    unified_model = bool(
        settings.get("switches", {}).get("unified_glm_processing", False)
    )
    # 统一模式下，字幕校对与全文断句都使用统一模型栏的模型、地址和密钥。
    # 关闭开关后仍保留原先两套端点的自由配置能力。
    prefix = "group" if stage == "polish" and unified_model else (
        "polish" if stage == "polish" else "group"
    )
    credential_stage = "group" if stage == "polish" and unified_model else stage
    provider = str(models.get(f"{prefix}_provider", "bailian") or "bailian")
    base_url = normalize_base_url(models.get(f"{prefix}_base_url", ""))
    model = str(models.get(f"{prefix}_model", "") or "").strip()
    api_key, key_source = resolve_api_key(credential_stage)
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "url": f"{base_url}/chat/completions" if base_url else "",
        "api_key": api_key,
        "key_source": key_source,
    }


def validate_endpoint(endpoint: dict, label: str = "大模型") -> None:
    if not str(endpoint.get("model", "")).strip():
        raise RuntimeError(f"{label}缺少模型名称。请在 AI 模型与密钥中完成配置。")
    base_url = str(endpoint.get("base_url", ""))
    validate_transport_url(base_url, label)
    if not str(endpoint.get("api_key", "")).strip():
        raise RuntimeError(f"{label}缺少 API 密钥。请展开 AI 模型与密钥后填写。")


def validate_transport_url(value: str, label: str = "服务") -> None:
    """Require encrypted transport except for an explicit local loopback service."""
    base_url = str(value or "").strip()
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise RuntimeError(f"{label}的 API 地址无效。请填写 OpenAI 兼容的 HTTPS 地址。")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError(f"{label}的 API 地址不能包含账号、密码、查询参数或片段。")
    if parsed.scheme == "http" and not _is_loopback_host(parsed.hostname):
        raise RuntimeError(f"{label}只允许 HTTPS；HTTP 仅可用于本机回环地址。")


def _is_loopback_host(hostname: str | None) -> bool:
    host = str(hostname or "").strip().strip("[]").lower()
    if host == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False
