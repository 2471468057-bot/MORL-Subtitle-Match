"""Loading and validation for the user-editable, non-secret runtime settings."""

import copy
import json
import os
import tempfile
from pathlib import Path


SETTINGS_FILENAME = "2byteasr_settings.json"

DEFAULT_SETTINGS = {
    "schema_version": 1,
    "models": {
        "qwen_asr_model": "Qwen/Qwen3-ASR-1.7B",
        "polish_provider": "bailian",
        "polish_model": "qwen3.7-flash-2026-07-15",
        "polish_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "group_provider": "bailian",
        "group_model": "qwen3.7-flash-2026-07-15",
        "group_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "switches": {
        "enable_qwen_asr_reference": True,
        "enable_firered_boundary_refinement": True,
        "show_speaker_labels_in_srt": False,
        "output_review_track": False,
        "unified_glm_processing": True,
    },
    "cache": {
        "force_refresh_polish": False,
        "force_refresh_group": False,
    },
    "performance": {
        "parallel_cloud_batches": True,
        "cloud_batch_workers": 4,
        "parallel_cpu_vad": True,
        "moss_parallel_workers": 2,
        "moss_parallel_min_vram_gb": 14,
        "qwen_asr_batch_size": 8,
        "parallel_gpu_asr": True,
        "parallel_gpu_asr_min_vram_gb": 14,
    },
}


def project_settings_path(project_root=None):
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[1]
    return root / SETTINGS_FILENAME


def _merge_known_settings(defaults, payload):
    result = copy.deepcopy(defaults)
    if not isinstance(payload, dict):
        return result, ["settings file root must be a JSON object"]
    warnings = []
    for section, values in defaults.items():
        if section == "schema_version":
            continue
        supplied = payload.get(section, {})
        if not isinstance(supplied, dict):
            warnings.append(f"{section} must be a JSON object; defaults were used")
            continue
        for key, default in values.items():
            value = supplied.get(key, default)
            if isinstance(default, bool):
                if isinstance(value, bool):
                    result[section][key] = value
                else:
                    warnings.append(f"{section}.{key} must be true or false; default was used")
            elif isinstance(default, str):
                if isinstance(value, str) and value.strip():
                    result[section][key] = value.strip()
                else:
                    warnings.append(f"{section}.{key} must be a non-empty string; default was used")
            elif isinstance(default, int):
                if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                    result[section][key] = value
                else:
                    warnings.append(f"{section}.{key} must be a positive integer; default was used")
    return result, warnings


def load_runtime_settings(project_root=None):
    """Return validated settings, source path and non-fatal validation warnings."""
    path = project_settings_path(project_root)
    if not path.is_file():
        return copy.deepcopy(DEFAULT_SETTINGS), str(path), ["settings file was not found; defaults were used"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return copy.deepcopy(DEFAULT_SETTINGS), str(path), [f"settings file could not be read: {exc}"]
    settings, warnings = _merge_known_settings(DEFAULT_SETTINGS, payload)
    if not isinstance(payload, dict):
        return settings, str(path), warnings
    if payload.get("schema_version", 1) != 1:
        warnings.append("unsupported schema_version; known settings were loaded")
    return settings, str(path), warnings


def save_runtime_settings(settings, project_root=None):
    """Persist validated non-secret settings with an atomic replace."""
    validated, warnings = _merge_known_settings(DEFAULT_SETTINGS, settings)
    validated["schema_version"] = 1
    path = project_settings_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(validated, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return validated, str(path), warnings
