"""Compatibility facade and shared runtime configuration for 2ByteASR.

Stage implementations live in ``twobyteasr`` modules.  This file keeps the historical
public API used by the launcher, tests, and pipeline while configuration remains in
one place during the incremental migration.
"""

import hashlib
import ipaddress
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import tkinter as tk
import urllib.parse
import uuid
import warnings
import wave
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
from difflib import SequenceMatcher
from statistics import median
from tkinter import filedialog, messagebox, ttk


from twobyteasr import reporting as task_reporting
from twobyteasr.llm_config import (
    endpoint_from_settings,
    read_secret_value,
    save_api_keys,
    secrets_path,
    validate_endpoint,
)
from twobyteasr.models import SpeechSegment, SubtitleCue, WordUnit
from twobyteasr.processes import hidden_subprocess_kwargs
from twobyteasr.runtime import get_runtime_context
from twobyteasr.settings import load_runtime_settings, save_runtime_settings


warnings.filterwarnings(
    "ignore",
    message=r"urllib3 .*doesn.*match a supported version!",
)


# ==========================================
# 配置区
# ==========================================
PIPELINE_BUILD_ID = "2026.08.05-v7.14-strict-length-number-style"
STARTUP_SELF_TEST_ID = "startup-self-test-v6.9"
RUNTIME_SETTINGS, RUNTIME_SETTINGS_PATH, RUNTIME_SETTINGS_WARNINGS = load_runtime_settings()






QWEN_ASR_MODEL = RUNTIME_SETTINGS["models"]["qwen_asr_model"]


LLM_MODEL = RUNTIME_SETTINGS["models"]["polish_model"]
POLISH_LLM_BASE_URL_DEFAULT = RUNTIME_SETTINGS["models"]["polish_base_url"]

# 断句/断句校验可使用独立云端模型；校对仍用上面的 LLM_MODEL。
GROUP_LLM_MODEL = RUNTIME_SETTINGS["models"]["group_model"]
GROUP_LLM_BASE_URL_DEFAULT = RUNTIME_SETTINGS["models"]["group_base_url"]


AUDIO_SAMPLE_RATE = 16000


SHOW_SPEAKER_LABELS_IN_SRT = RUNTIME_SETTINGS["switches"]["show_speaker_labels_in_srt"]


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_secret_value(*names):
    """Read a secret from process env first, then Windows DPAPI storage."""
    value, _ = read_secret_value(*names)
    return value


def require_runtime_secrets(require_dashscope=True, require_hf=False):
    missing = []
    if require_dashscope and not get_dashscope_api_key():
        missing.append("DASHSCOPE_API_KEY")
    if require_hf and not HF_TOKEN:
        missing.append("HF_TOKEN")
    if missing:
        local_secrets_path = secrets_path()
        raise RuntimeError(
            "缺少密钥："
            + ", ".join(missing)
            + "\n请任选一种方式配置后重开终端再运行：\n"
            + "1) 用户/系统环境变量 DASHSCOPE_API_KEY、HF_TOKEN\n"
            + f"2) 在程序的 AI 模型与密钥页面保存（加密文件：{local_secrets_path}）\n"
            + "PowerShell 当前会话示例：\n"
            + "  $env:DASHSCOPE_API_KEY = \"<your-dashscope-key>\"\n"
            + "  $env:HF_TOKEN = \"<your-hf-token>\""
        )


DASHSCOPE_API_KEY = _load_secret_value("DASHSCOPE_API_KEY", "2BYTEASR_DASHSCOPE_API_KEY")
HF_TOKEN = _load_secret_value("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN", "2BYTEASR_HF_TOKEN")


GLOSSARY_PATH = os.path.join(SCRIPT_DIR, "glossary.txt")


GAME_PROFILES_PATH = os.path.join(SCRIPT_DIR, "game_profiles.json")


GAME_LEXICON_MAX_PROMPT_TERMS = 120


PROFILE_HISTORY_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", SCRIPT_DIR),
    "2ByteASR",
    "content_profiles.json",
)


LEARNED_TERMS_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", SCRIPT_DIR),
    "2ByteASR",
    "learned_game_terms.json",
)

HOST_VOICEPRINT_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", SCRIPT_DIR),
    "2ByteASR",
    "host_voiceprints",
)

HOST_VOICEPRINT_REGISTRY_PATH = os.path.join(HOST_VOICEPRINT_DIR, "registry.json")


RUN_LOG_ROOT = os.path.join(
    os.environ.get("LOCALAPPDATA", SCRIPT_DIR),
    "2ByteASR",
    "logs",
)


FIRERED_SOURCE_DIR = os.path.join(SCRIPT_DIR, "third_party", "FireRedASR2S")


FIRERED_MODEL_DIR = os.path.join(SCRIPT_DIR, "models", "FireRedASR2-AED")


# 每次启动都默认通用模式，防止上一个游戏的词表污染下一期素材。
# 只有用户在运行时窗口里明确填写游戏并勾选术语增强，才会联网找词或套用游戏规则。
_DEFAULT_RUNTIME_CONTEXT = get_runtime_context()
_DEFAULT_RUNTIME_CONTEXT.output_review_track = bool(
    RUNTIME_SETTINGS["switches"]["output_review_track"]
)
_DEFAULT_RUNTIME_CONTEXT.force_refresh_polish_cache = bool(
    RUNTIME_SETTINGS["cache"]["force_refresh_polish"]
)
_DEFAULT_RUNTIME_CONTEXT.force_refresh_group_cache = bool(
    RUNTIME_SETTINGS["cache"]["force_refresh_group"]
)

RUNTIME_GAME_NAME = _DEFAULT_RUNTIME_CONTEXT.game_name


RUNTIME_ENABLE_DOMAIN_TERMS = _DEFAULT_RUNTIME_CONTEXT.enable_domain_terms


RUNTIME_DISCOVERED_TERMS = _DEFAULT_RUNTIME_CONTEXT.discovered_terms


RUNTIME_OUTPUT_REVIEW_TRACK = _DEFAULT_RUNTIME_CONTEXT.output_review_track


RUNTIME_FORCE_REFRESH_API_CACHE = _DEFAULT_RUNTIME_CONTEXT.force_refresh_api_cache


# 校对和断句分别刷新，避免只想重跑其中一步时把两轮 DashScope 都作废。
RUNTIME_FORCE_REFRESH_POLISH_CACHE = _DEFAULT_RUNTIME_CONTEXT.force_refresh_polish_cache


RUNTIME_FORCE_REFRESH_GROUP_CACHE = _DEFAULT_RUNTIME_CONTEXT.force_refresh_group_cache


def _supplement_tool_path():
    """winget 等安装的 FFmpeg/ffprobe 可能不在当前进程 PATH（新装环境常见），
    把常见安装位置补充进 PATH，避免“缺少 ffmpeg/ffprobe”误报。"""
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "FFmpeg", "bin"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages"),
        os.path.join(os.environ.get("ProgramFiles", ""), "FFmpeg", "bin"),
        r"C:\ffmpeg\bin",
    ]
    extra = [c for c in candidates if c and os.path.isdir(c)]
    for base in candidates:
        if not base or not os.path.isdir(base):
            continue
        if os.path.basename(base) == "Packages":
            # winget portable 包实际解压在 WinGet\Packages\<包名>\...，递归定位 ffmpeg.exe
            for root, dirs, files in os.walk(base):
                if "ffmpeg.exe" in files:
                    extra.append(root)
                    dirs[:] = []
    if extra:
        os.environ["PATH"] = os.pathsep.join(
            [*dict.fromkeys(extra), os.environ.get("PATH", "")]
        )


_supplement_tool_path()


PARALLEL_CLOUD_BATCHES = RUNTIME_SETTINGS["performance"]["parallel_cloud_batches"]


CLOUD_BATCH_WORKERS = max(1, min(8, int(RUNTIME_SETTINGS["performance"]["cloud_batch_workers"])))


PARALLEL_CPU_VAD = RUNTIME_SETTINGS["performance"]["parallel_cpu_vad"]


MOSS_PARALLEL_WORKERS = max(
    1, min(2, int(RUNTIME_SETTINGS["performance"]["moss_parallel_workers"]))
)


MOSS_PARALLEL_MIN_VRAM_GB = float(
    RUNTIME_SETTINGS["performance"]["moss_parallel_min_vram_gb"]
)


PARALLEL_GPU_ASR = RUNTIME_SETTINGS["performance"]["parallel_gpu_asr"]


PARALLEL_GPU_ASR_MIN_VRAM_GB = float(
    RUNTIME_SETTINGS["performance"]["parallel_gpu_asr_min_vram_gb"]
)


RUNTIME_EXPECTED_SPEAKERS = _DEFAULT_RUNTIME_CONTEXT.expected_speakers


RUNTIME_CANCELLATION_TOKEN = _DEFAULT_RUNTIME_CONTEXT.cancellation_token


RUN_EVENT_LOG_PATH = _DEFAULT_RUNTIME_CONTEXT.event_log_path


BUILTIN_GAME_PROFILES = ("洛克王国：世界", "绝区零")


# 纯音频无法得知剪辑时间轴帧率，用 60 fps 作为兜底；直接选视频时自动探测。
TIMELINE_FPS = 60.0


USE_FIRERED_BOUNDARY_REFINEMENT = RUNTIME_SETTINGS["switches"]["enable_firered_boundary_refinement"]


FIRERED_CHUNK_SECONDS = 38.0


FIRERED_CHUNK_STEP_SECONDS = 36.0


FIRERED_NORMAL_TOKEN_SECONDS = 0.80


FIRERED_LONG_TOKEN_TAIL_SECONDS = 0.24


FIRERED_TEXT_ALIGNMENT_PAD_SECONDS = 0.35


# FireRed 的病态长 token 只可作为邻近文字证据；有效字头已经落到 MOSS
# 段外时不能再把该 token 的尾点夹回段尾，否则会制造 0.4-2 秒假尾巴。
FIRERED_EFFECTIVE_TOKEN_OUTSIDE_TOLERANCE_SECONDS = 0.08


# Qwen3-ASR 只提供复核文字证据；主时间骨架由 FireRed-AED/FireRedVAD 负责。
USE_QWEN_ASR_REFERENCE = RUNTIME_SETTINGS["switches"]["enable_qwen_asr_reference"]


QWEN_ASR_CHUNK_SECONDS = 25.0


QWEN_ASR_AUDIO_PAD_SECONDS = 0.20


QWEN_ASR_BATCH_SIZE = max(
    1, min(12, int(RUNTIME_SETTINGS["performance"]["qwen_asr_batch_size"]))
)


QWEN_ASR_MAX_NEW_TOKENS = 160


QWEN_ASR_TEXT_ALIGNMENT_PAD_SECONDS = 0.50


QWEN_ASR_ALTERNATE_MIN_SIMILARITY = 0.38


# 这是内容类型提示，不是热词表，也不会触发本地强制替换。
CONTENT_DOMAIN_HINT = (
    "中文二次元游戏/二游实况与展会视频，可能出现游戏名、角色名、技能、机制、"
    "地图、厂商、展台以及玩家口头梗。陌生词可能是专名，不要擅自普通词化。"
)


# 成片固定规则：前者必须从最终字幕删除；后者统一为剪辑者确认过的真实写法。
SUBTITLE_SUPPRESSED_PHRASES = (
    "我操", "卧槽", "我艹", "卧艹", "我草", "卧草", "窝草", "沃草", "握草",
)





def get_dashscope_api_key():
    """Always resolve the latest key (environment wins over DPAPI storage)."""
    return _load_secret_value(
        "DASHSCOPE_API_KEY",
        "2BYTEASR_DASHSCOPE_API_KEY",
        "GROUP_LLM_API_KEY",
    )


def polish_llm_settings():
    """Return the current OpenAI-compatible endpoint used by subtitle correction."""
    return endpoint_from_settings(RUNTIME_SETTINGS, "polish")


def describe_secret_source(value_name="DASHSCOPE_API_KEY"):
    """Return a safe debug string for which source provided the API key."""
    for name in ("DASHSCOPE_API_KEY", "2BYTEASR_DASHSCOPE_API_KEY", "GROUP_LLM_API_KEY"):
        raw = str(os.environ.get(name, "") or "").strip()
        if raw:
            return f"env:{name}", raw
    names = ("DASHSCOPE_API_KEY", "2BYTEASR_DASHSCOPE_API_KEY", "GROUP_LLM_API_KEY")
    raw, source = read_secret_value(*names)
    if raw:
        name = source.rsplit("/", 1)[-1].strip()
        return f"dpapi:{name}", raw
    return "missing", ""


def mask_api_key(key):
    key = str(key or "")
    if not key:
        return "<empty>"
    if len(key) <= 12:
        return key[:3] + "..."
    return f"{key[:8]}...{key[-4:]} (len={len(key)})"


def group_llm_settings():
    """Return the current OpenAI-compatible endpoint used by full-text grouping."""
    return endpoint_from_settings(RUNTIME_SETTINGS, "group")


def configure_runtime_llms(
    models,
    *,
    polish_key="",
    group_key="",
    share_key=False,
    unified_glm_processing=None,
):
    """Apply UI-selected model settings and persist only explicitly entered keys."""
    global RUNTIME_SETTINGS, RUNTIME_SETTINGS_WARNINGS, LLM_MODEL, POLISH_LLM_BASE_URL_DEFAULT
    global GROUP_LLM_MODEL, GROUP_LLM_BASE_URL_DEFAULT, DASHSCOPE_API_KEY

    updated = json.loads(json.dumps(RUNTIME_SETTINGS, ensure_ascii=False))
    for key in (
        "polish_provider",
        "polish_model",
        "polish_base_url",
        "group_provider",
        "group_model",
        "group_base_url",
    ):
        value = str(models.get(key, "") or "").strip()
        if value:
            updated["models"][key] = value
    if unified_glm_processing is not None:
        updated["switches"]["unified_glm_processing"] = bool(
            unified_glm_processing
        )
    RUNTIME_SETTINGS, _, warnings = save_runtime_settings(updated, SCRIPT_DIR)
    RUNTIME_SETTINGS_WARNINGS = list(warnings)
    if polish_key or group_key:
        save_api_keys(
            polish_key=polish_key,
            group_key=group_key,
            share_key=bool(share_key),
        )
    LLM_MODEL = RUNTIME_SETTINGS["models"]["polish_model"]
    POLISH_LLM_BASE_URL_DEFAULT = RUNTIME_SETTINGS["models"]["polish_base_url"]
    GROUP_LLM_MODEL = RUNTIME_SETTINGS["models"]["group_model"]
    GROUP_LLM_BASE_URL_DEFAULT = RUNTIME_SETTINGS["models"]["group_base_url"]
    DASHSCOPE_API_KEY = get_dashscope_api_key()
    return warnings



def post_chat_completion(
    messages,
    *,
    model,
    api_key,
    url,
    max_tokens,
    temperature=0.0,
    timeout=None,
    enable_thinking=False,
    response_format=None,
):
    import requests

    if not api_key:
        raise RuntimeError(
            "断句模型缺少 API Key。请配置 DASHSCOPE_API_KEY（百炼，与校对共用）；"
            "也可在程序的 AI 模型与密钥页面中保存"
        )
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # 部分模型默认可能开思考模式：content 为空、reasoning_content 占满 max_tokens。
    # 断句只要稳定 JSON，必须显式关闭思考。
    if str(model).lower().startswith("glm"):
        body["enable_thinking"] = bool(enable_thinking)
    elif enable_thinking is not None:
        body["enable_thinking"] = bool(enable_thinking)
    if response_format is not None:
        body["response_format"] = response_format
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=timeout if timeout is not None else (10, API_TIMEOUT_SECONDS),
    )
    response.raise_for_status()
    payload = response.json()
    try:
        message = payload["choices"][0]["message"]
    except Exception as exc:
        raise RuntimeError(f"聊天补全返回无法解析：{payload!r}") from exc
    content = extract_chat_message_text(message)
    if not str(content or "").strip():
        raise RuntimeError(
            "模型没有返回可用正文（content 为空）。"
            f" message_keys={list(message.keys()) if isinstance(message, dict) else type(message)}"
        )
    return content


def extract_chat_message_text(message):
    """兼容普通 content 与部分模型思考模式的 reasoning_content。"""
    if message is None:
        return ""
    if isinstance(message, str):
        return message
    if not isinstance(message, dict):
        return str(message)
    for key in ("content", "reasoning_content", "reasoning"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list):
            parts = []
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content") or ""
                    if text:
                        parts.append(str(text))
            joined = "".join(parts).strip()
            if joined:
                return joined
    return ""



def boundaries_to_segmented_text(source_text, boundary_offsets):
    text = clean_subtitle_text(source_text)
    total = display_length(text)
    ordered = sorted({int(x) for x in boundary_offsets if int(x) > 0})
    if not ordered or ordered[-1] != total:
        # repair last
        ordered = [offset for offset in ordered if 0 < offset < total] + [total]
    start = 0
    parts = []
    for offset in ordered:
        parts.append(text[start:offset])
        start = offset
    if any(part == "" for part in parts):
        raise ValueError("空分段")
    return "|".join(parts)



def validate_grouping_boundaries_with_llm(
    segment_batch,
    boundary_offsets,
    firered_tokens=(),
):
    """第二轮云端校验：只允许移动竖线，禁止增删改任何原字。"""
    source_text = "".join(clean_subtitle_text(segment.text) for segment in segment_batch)
    total_length = display_length(source_text)
    if total_length <= 1 or len(boundary_offsets) <= 1:
        return list(boundary_offsets)

    try:
        segmented_text = boundaries_to_segmented_text(source_text, boundary_offsets)
    except Exception:
        return list(boundary_offsets)

    settings = group_llm_settings()
    prompt = f"""你是中文口语视频字幕的断句校验器，不是润色器、不是校对器。

绝对约束：
1. 只能移动竖线“|”的位置；不能修改、增删、替换、重排 source_text 的任何字符。
2. 返回的 segmented_text 去掉全部“|”后，必须与 source_text 逐字完全一致。
3. 若竖线切开了完整词/短语（例如“估|计”“眼|皮”“接|受”“能|力”“为什|么”“商|城”“其实我的|…”“我的眼|皮”），必须把竖线挪到该结构之前或之后，使左右都是可独立听懂的口语成分。
4. pause 气口很重要；但若 pause 落在完整词或未完成成分内部，不能保留错误切开。
5. 目标中位数约 {PREFERRED_MAX_SUBTITLE_CHARS} 字，常规不超过 {MAX_SUBTITLE_CHARS} 字；完整短语可到 {COMPLETE_PHRASE_SOFT_MAX_CHARS} 字。不要为了变短而过切，也不要留下短残尾。
6. 只修明显坏切：词中切开、上条停在“的/一个/这个”且下条是短中心语（如“300万的｜启动资金啊”“进入一个｜珊瑚场啊”）、1-3 字残句。合格则原样返回；单字条并入邻句或消竖线。
7. 已合格则原样返回。
8. 只返回 JSON：{{"segmented_text":"第一条|第二条","boundaries":[8,17,{total_length}]}}。boundaries 严格递增且最后一项等于 {total_length}。"""

    request_body = {
        "source_text": source_text,
        "total_length": total_length,
        "segmented_text": segmented_text,
        "boundaries": list(boundary_offsets),
    }
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(request_body, ensure_ascii=False)},
    ]
    try:
        content = post_chat_completion(
            messages,
            model=settings["model"],
            api_key=settings["api_key"],
            url=settings["url"],
            max_tokens=min(4096, max(512, total_length * 2)),
            temperature=0.0,
            timeout=(10, GROUPING_API_TIMEOUT_SECONDS),
            enable_thinking=False,
            response_format={"type": "json_object"},
        )
        returned = parse_qwen_object(content)
        new_segmented = returned.get("segmented_text")
        if isinstance(new_segmented, str) and new_segmented.strip():
            parts = [clean_subtitle_text(part) for part in new_segmented.split("|")]
            if (
                parts
                and all(parts)
                and content_exact("".join(parts)) == content_exact(source_text)
            ):
                rebuilt = []
                running = 0
                for part in parts:
                    running += display_length(part)
                    rebuilt.append(running)
                if rebuilt and rebuilt[-1] == total_length:
                    if rebuilt != list(boundary_offsets):
                        print(
                            f"   [断句校验/{settings['model']}] 仅移动竖线，"
                            f"边界 {len(boundary_offsets)} -> {len(rebuilt)}。"
                        )
                    return rebuilt
        new_boundaries = returned.get("boundaries")
        if isinstance(new_boundaries, list) and new_boundaries:
            normalized = [int(value) for value in new_boundaries]
            if normalized[-1] == total_length:
                # verify via local slice conservation
                try:
                    texts_from_boundary_offsets(
                        segment_batch, normalized, firered_tokens
                    )
                    return normalized
                except Exception:
                    pass
    except Exception as exc:
        print(f"   [警告] 断句校验未采纳，沿用首轮边界：{exc}")
        record_run_event("grouping_validate_skip", error=redact_runtime_secrets(exc))
    return list(boundary_offsets)



def runtime_game_identity(game_name):
    """忽略中英文冒号和常见分隔符，识别同一个游戏名称。"""
    cleaned = clean_subtitle_text(game_name)
    return re.sub(r"[\s:：·._/\\-]+", "", cleaned).lower()


def canonicalize_runtime_game_name(game_name):
    cleaned = clean_subtitle_text(game_name)
    identity = runtime_game_identity(cleaned)
    if identity == "洛克王国世界":
        return "洛克王国：世界"
    if identity == "绝区零":
        return "绝区零"
    return cleaned


def load_game_profiles():
    try:
        with open(GAME_PROFILES_PATH, "r", encoding="utf-8-sig") as file:
            payload = json.load(file)
        profiles = payload.get("profiles", {})
        return profiles if isinstance(profiles, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def active_game_profile():
    identity = runtime_game_identity(RUNTIME_GAME_NAME)
    for name, profile in load_game_profiles().items():
        if runtime_game_identity(profile.get("identity", name)) == identity:
            return profile
    return {}


def active_profile_term_items():
    items = active_game_profile().get("terms", [])
    return [item for item in items if isinstance(item, dict) and item.get("canonical")]


def active_profile_terms():
    return list(
        dict.fromkeys(
            clean_subtitle_text(item["canonical"])
            for item in active_profile_term_items()
            if clean_subtitle_text(item["canonical"])
        )
    )


def active_profile_alias_rules():
    """把专名别名分成安全全文替换和需要独立 ASR 支持的短词。"""
    rules = []
    for item in active_profile_term_items():
        target = clean_subtitle_text(item.get("canonical", ""))
        explicit_mode = str(item.get("replacement_mode", "")).strip().lower()
        for source in item.get("aliases", []):
            source = clean_subtitle_text(source)
            if not source or not target or source == target:
                continue
            if explicit_mode in ("global", "contextual"):
                mode = explicit_mode
            else:
                # 三字以上错词通常足够独特；二字日常词（落地、封印、码头等）
                # 必须得到另一套 ASR 的正确专名支持，防止 PVP 词表污染普通对话。
                mode = "global" if display_length(source) >= 3 else "contextual"
            rules.append(
                {
                    "source": source,
                    "target": target,
                    "mode": mode,
                    "category": str(item.get("category", "game_term")),
                }
            )
    return rules


def active_blocked_mapping_pairs():
    result = set()
    for item in active_game_profile().get("blocked_mappings", []):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        source = content_only(item[0])
        target = content_only(item[1])
        if source and target:
            result.add((source, target))
    return result


def active_profile_lexicon_paths():
    """只加载配置明确列出的脚本目录内词库，拒绝越界路径。"""
    paths = []
    script_root = os.path.abspath(SCRIPT_DIR)
    for relative in active_game_profile().get("lexicons", []):
        if not isinstance(relative, str) or not relative.strip():
            continue
        candidate = os.path.abspath(os.path.join(SCRIPT_DIR, relative))
        try:
            if os.path.commonpath((script_root, candidate)) != script_root:
                continue
        except ValueError:
            continue
        if os.path.isfile(candidate):
            paths.append(candidate)
    return list(dict.fromkeys(paths))


def load_active_game_lexicon_names():
    """读取完整本地图鉴；它只产生弱候选，不直接触发文字替换。"""
    expected_identity = runtime_game_identity(RUNTIME_GAME_NAME)
    names = []
    loaded = []
    for path in active_profile_lexicon_paths():
        try:
            with open(path, "r", encoding="utf-8-sig") as file:
                payload = json.load(file)
            if runtime_game_identity(payload.get("game", "")) != expected_identity:
                continue
            entries = payload.get("entries", [])
            current = [
                clean_subtitle_text(item.get("name", ""))
                for item in entries
                if isinstance(item, dict) and clean_subtitle_text(item.get("name", ""))
            ]
            names.extend(current)
            loaded.append(
                (
                    payload.get("category", os.path.basename(path)),
                    len(entries),
                    len(set(current)),
                )
            )
        except (OSError, ValueError, TypeError):
            continue
    return list(dict.fromkeys(names)), loaded


def active_game_lexicon_signature():
    return {
        os.path.relpath(path, SCRIPT_DIR).replace("\\", "/"): file_digest(path)
        for path in active_profile_lexicon_paths()
    }


def load_learned_term_payload():
    try:
        with open(LEARNED_TERMS_PATH, "r", encoding="utf-8-sig") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else {"schema": 1, "games": {}}
    except (OSError, ValueError, TypeError):
        return {"schema": 1, "games": {}}


def learned_mappings_for_game(game_name=None):
    game_name = canonicalize_runtime_game_name(game_name or RUNTIME_GAME_NAME)
    identity = runtime_game_identity(game_name)
    entry = load_learned_term_payload().get("games", {}).get(identity, {})
    mappings = entry.get("mappings", []) if isinstance(entry, dict) else []
    return [
        item
        for item in mappings
        if isinstance(item, dict) and item.get("from") and item.get("to")
    ]


def add_learned_mapping(game_name, source, target):
    """手动新增一条已学习映射；from==to 表示确认专名正确写法。返回是否新增。"""
    game_name = canonicalize_runtime_game_name(game_name)
    identity = runtime_game_identity(game_name)
    source = content_only(source)
    target = content_only(target)
    if not source or not target:
        return False
    payload = load_learned_term_payload()
    payload["schema"] = 1
    entry = payload.setdefault("games", {}).setdefault(
        identity, {"game": game_name, "mappings": []}
    )
    mappings = entry.setdefault("mappings", [])
    for item in mappings:
        if item.get("from") == source and item.get("to") == target:
            return False
    mappings.append(
        {
            "from": source,
            "to": target,
            "reason": "手动添加",
            "sources": ["user_manual"],
            "verification": "user_manual",
            "confirmed": True,
            "updated": time.strftime("%Y-%m-%d"),
        }
    )
    try:
        os.makedirs(os.path.dirname(LEARNED_TERMS_PATH), exist_ok=True)
        atomic_write_json(LEARNED_TERMS_PATH, payload)
    except OSError:
        return False
    return True


def persist_learned_mappings(game_name, mappings):
    if not game_name or not mappings:
        return
    payload = load_learned_term_payload()
    payload["schema"] = 1
    games = payload.setdefault("games", {})
    identity = runtime_game_identity(game_name)
    entry = games.setdefault(identity, {"game": game_name, "mappings": []})
    existing = {
        (content_only(item.get("from", "")), content_only(item.get("to", ""))): item
        for item in entry.get("mappings", [])
        if isinstance(item, dict)
    }
    blocked = (
        active_blocked_mapping_pairs()
        if runtime_game_identity(game_name) == runtime_game_identity(RUNTIME_GAME_NAME)
        else set()
    )
    for mapping in mappings:
        key = (content_only(mapping.get("from", "")), content_only(mapping.get("to", "")))
        if not all(key) or key in blocked:
            continue
        existing[key] = {
            "from": clean_subtitle_text(mapping["from"]),
            "to": clean_subtitle_text(mapping["to"]),
            "reason": clean_subtitle_text(mapping.get("reason", "联网术语核验"))[:160],
            "sources": list(mapping.get("sources", ()))[:5],
            "verification": mapping.get("verification", "web_source"),
            "confirmed": bool(mapping.get("confirmed", False)),
            "updated": time.strftime("%Y-%m-%d"),
        }
    entry["mappings"] = sorted(existing.values(), key=lambda item: (item["to"], item["from"]))
    try:
        os.makedirs(os.path.dirname(LEARNED_TERMS_PATH), exist_ok=True)
        atomic_write_json(LEARNED_TERMS_PATH, payload)
    except OSError as exc:
        # 本批已核验映射仍可使用；只是不带到下一批，不能因此重跑联网 API。
        print(f"   [警告] 已学习术语未能持久保存：{exc}")


def delete_learned_mappings(game_name, mapping_keys):
    """删除用户在管理窗口中明确选中的学习映射。"""
    identity = runtime_game_identity(canonicalize_runtime_game_name(game_name))
    payload = load_learned_term_payload()
    games = payload.get("games", {})
    entry = games.get(identity)
    if not isinstance(entry, dict):
        return 0
    keys = {
        (content_only(source), content_only(target))
        for source, target in mapping_keys
    }
    before = list(entry.get("mappings", []))
    entry["mappings"] = [
        item
        for item in before
        if (
            content_only(item.get("from", "")),
            content_only(item.get("to", "")),
        )
        not in keys
    ]
    removed = len(before) - len(entry["mappings"])
    if removed:
        os.makedirs(os.path.dirname(LEARNED_TERMS_PATH), exist_ok=True)
        atomic_write_json(LEARNED_TERMS_PATH, payload)
    return removed


def prepared_learned_mappings(segments, game_name=None):
    """把已核验学习词转换成本次稿件可安全应用的映射。"""
    result = []
    blocked = active_blocked_mapping_pairs()
    for item in learned_mappings_for_game(game_name):
        source = content_only(item.get("from", ""))
        target = content_only(item.get("to", ""))
        if not source or not target or source == target or (source, target) in blocked:
            continue
        occurrence_ids = [
            segment.segment_id
            for segment in segments
            if source in content_only(segment.text)
        ]
        if not occurrence_ids:
            continue
        confirmed = bool(item.get("confirmed", False))
        result.append(
            {
                "from": source,
                "to": target,
                "source_ids": occurrence_ids,
                # 用户确认词或本批重复出现时全文统一；单次联网学习词只改命中段。
                "apply_all": confirmed or len(occurrence_ids) >= 2,
                "reason": item.get("reason", "已学习术语"),
                "sources": list(item.get("sources", ())),
                "verification": item.get("verification", "learned"),
                "confirmed": confirmed,
            }
        )
        RUNTIME_DISCOVERED_TERMS.add(target)
    return result


def active_canonical_replacements():
    if not RUNTIME_ENABLE_DOMAIN_TERMS:
        return ()
    pairs = [
        (item["source"], item["target"])
        for item in active_profile_alias_rules()
        if item["mode"] == "global"
    ]
    return tuple(dict.fromkeys(pairs))


def active_contextual_alias_map():
    return {
        item["source"]: item["target"]
        for item in active_profile_alias_rules()
        if item["mode"] == "contextual"
    }


def apply_active_canonical_replacements(text):
    for source, target in active_canonical_replacements():
        if source == "爆米花":
            text = re.sub(r"爆米花(?!爆破)", target, text)
        else:
            text = text.replace(source, target)
    if active_canonical_replacements():
        # PVP 口语中的“挂寄生”常被写成“刮寄生”；只在明确技能搭配里修正，
        # 不把普通动词“刮”一概替换。
        text = re.sub(r"刮(?=(?:个|一层|两层|三层|几层)?寄生)", "挂", text)
    return text


def runtime_content_profile_signature():
    return {
        "game": clean_subtitle_text(RUNTIME_GAME_NAME),
        "domain_terms": bool(RUNTIME_ENABLE_DOMAIN_TERMS),
        "expected_speakers": int(RUNTIME_EXPECTED_SPEAKERS),
    }


def runtime_settings_snapshot():
    """Non-secret effective settings, suitable for a per-media task report."""
    polish_settings = polish_llm_settings()
    group_settings = group_llm_settings()
    return {
        "config_file": RUNTIME_SETTINGS_PATH,
        "config_warnings": list(RUNTIME_SETTINGS_WARNINGS),
        "models": {
            "qwen_asr_model": QWEN_ASR_MODEL,
            "polish_provider": polish_settings["provider"],
            "polish_model": polish_settings["model"],
            "polish_base_url": polish_settings["base_url"],
            "group_provider": group_settings["provider"],
            "group_model": group_settings["model"],
            "group_base_url": group_settings["base_url"],
        },
        "switches": {
            "enable_qwen_asr_reference": bool(USE_QWEN_ASR_REFERENCE),
            "enable_firered_boundary_refinement": bool(USE_FIRERED_BOUNDARY_REFINEMENT),
            "show_speaker_labels_in_srt": bool(SHOW_SPEAKER_LABELS_IN_SRT),
            "output_review_track": bool(RUNTIME_OUTPUT_REVIEW_TRACK),
        },
        "cache": {
            "force_refresh_polish": bool(RUNTIME_FORCE_REFRESH_POLISH_CACHE),
            "force_refresh_group": bool(RUNTIME_FORCE_REFRESH_GROUP_CACHE),
        },
        "performance": {
            "parallel_cloud_batches": bool(PARALLEL_CLOUD_BATCHES),
            "cloud_batch_workers": int(CLOUD_BATCH_WORKERS),
            "parallel_cpu_vad": bool(PARALLEL_CPU_VAD),
            "moss_parallel_workers": int(MOSS_PARALLEL_WORKERS),
            "moss_parallel_min_vram_gb": float(MOSS_PARALLEL_MIN_VRAM_GB),
            "qwen_asr_batch_size": int(QWEN_ASR_BATCH_SIZE),
            "parallel_gpu_asr": bool(PARALLEL_GPU_ASR),
            "parallel_gpu_asr_min_vram_gb": float(PARALLEL_GPU_ASR_MIN_VRAM_GB),
        },
        "content_profile": runtime_content_profile_signature(),
    }


def begin_media_report(media_path, cache_context):
    task_reporting.begin_media_report(
        media_path,
        cache_context,
        runtime_settings_snapshot(),
    )


def finish_media_report(status, **result):
    return task_reporting.finish_media_report(status, **result)


# 字幕风格来自人工校正样本：以约 8 字的完整语义块为目标。
HARD_GAP_SECONDS = 1.2


INTERNAL_HARD_GAP_SECONDS = 3.0


# 约 0.8 秒已经是剪辑上清晰可感知的停顿。只要边界不落在词中、也不是
# 明显未完成成分，就保留 MOSS 的原始段界，避免把停顿后的两字回应重新吞回前句。
PROTECTED_SOURCE_GAP_SECONDS = 0.75


TWO_CHARACTER_MERGE_MAX_GAP_SECONDS = 0.75


PROTECTED_SOURCE_SHORT_CHARS = 3


# 单字语气词只在近乎连读时并入相邻字幕；更远的语气词由成片规则省略，
# 不能为了消灭单字轨而让上一句横跨整段空白。
SINGLE_CHARACTER_MERGE_MAX_GAP_SECONDS = 0.35


MAX_SUBTITLE_SECONDS = 5.0


# 人工样本的自然中位数约 10 字。长度只用于舒适度排序，不能为了凑 8 字
# 把“终末地的单肩包”“捶背的毛绒锤”或完整主谓宾机械腰斩。
PREFERRED_MAX_SUBTITLE_CHARS = 10


MAX_SUBTITLE_CHARS = 16


# 人工修订样本最长 14-15 字；最终成片不再为“完整短语”放宽到 17-20 字。
# 达到 16 字附近且包含两个语义动作时，应优先在自然气口拆分。
COMPLETE_PHRASE_SOFT_MAX_CHARS = 16


MAX_RAW_SEGMENT_CHARS = 24


REAL_PAUSE_HINT_SECONDS = 0.18


# 只修正“字幕句首明确落在 VAD 静音区”的保守场景。小于 180ms 可能只是
# 起音检测误差，大于 650ms 更可能是漏句或说话人归属问题，只提示复核。
VAD_ONSET_SNAP_MIN_LEAD_SECONDS = 0.18


VAD_ONSET_SNAP_MAX_LEAD_SECONDS = 0.65


VAD_ONSET_CONTAINMENT_PAD_SECONDS = 0.03


MIN_SUBTITLE_SECONDS = 0.35


PHONETIC_MAX_DISTANCE = 0.70


# 人声起音只用来修正相邻字幕交界，不参与文字识别。
BOUNDARY_VAD_THRESHOLD = 0.50


BOUNDARY_VAD_MIN_SPEECH_MS = 80


BOUNDARY_VAD_MIN_SILENCE_MS = 160


BOUNDARY_VAD_MIN_GAP_SECONDS = 0.15


BOUNDARY_VAD_LOOKBACK_SECONDS = 0.30


BOUNDARY_VAD_SHORT_GAP_ONSET_LEAD_SECONDS = 0.07


MAX_CUE_HOLD_GAP_SECONDS = 0.20


MAX_HELD_SUBTITLE_SECONDS = 4.00


# 与下一条之间有足够空白的独立字幕，在识别尾音后多保留 200ms，避免突兀消失。
ISOLATED_CUE_TAIL_SECONDS = 0.20


# 默认尾帧仍只增加 200ms；如果所有轨道在相邻字幕间仍剩不足 500ms 的空白，
# 再让当前可见字幕保持到下一条开始，避免剪映画面出现短促闪轴。
SHORT_DISPLAY_GAP_BRIDGE_SECONDS = 0.50


EDITORIAL_OMITTABLE_SINGLE_CHARACTERS = frozenset(
    (
        "嗯", "啊", "哦", "呃", "哎", "诶", "唉", "呀", "哈",
        "喔", "恩", "噢", "唔", "欸", "吶", "呵", "嘿", "嘻", "哼", "欸",
    )
)


INTERNAL_BOUNDARY_MAX_SHIFT_SECONDS = 0.45


INTERNAL_BOUNDARY_MIN_VAD_SILENCE_RATIO = 0.45


# FireRed is allowed to correct the position of characters inside a MOSS segment,
# but must not pull an entire segment far outside MOSS's speaker boundary.
FIRERED_TIMELINE_MAX_START_SHIFT_SECONDS = 0.45


FIRERED_TIMELINE_MAX_END_SHIFT_SECONDS = 0.65


# 中间结果写入 LocalAppData，不在素材目录额外生成文件。
CACHE_ROOT = os.path.join(
    os.environ.get("LOCALAPPDATA", SCRIPT_DIR),
    "2ByteASR",
    "cache",
)


CACHE_SCHEMA_VERSION = 1


CACHE_MAX_AGE_DAYS = 14


CACHE_STAGE_VERSIONS = {
    "audio": 1,
    "qwen": 3,
    "firered": 3,
    "polished": 28,
    "grouped": 55,
    "moss": 4,
    "firered_vad": 1,
    "firered_primary": 7,
    "firered_llm": 2,
    "final_timing": 10,
}


# API 阶段只依赖各自逻辑版本，不再散列整个 6800 行模块。以后修改时间轴、
# 输出或日志不会无故让全文校对和全文断句缓存失效。
POLISH_LOGIC_VERSION = "polish-v29-local-reference-consensus-and-title-profiles"
GROUP_LOGIC_VERSION = "group-v56-natural-local-fallback-20-char-phrases"
TIMING_LOGIC_VERSION = "timing-v9-natural-phrase-limits"


# 复核清单只打印在运行窗口，不增加第三个输出文件。
REVIEW_MAX_ITEMS = 24


REVIEW_LOW_CONFIDENCE = 0.45


REVIEW_FAST_CHARS_PER_SECOND = 9.0


REVIEW_TIMING_DIFFERENCE_SECONDS = 0.30


TARGET_RAW_SEGMENT_CHARS = 8


MIN_BALANCED_SEGMENT_CHARS = 4


API_BATCH_MAX_CHARS = 5000


API_BATCH_MAX_CUES = 20


# 字幕校对比全文断句包含更多文字修改与安全审计，单个大批次容易成为
# 云端长尾。32 条左右的短素材拆成 3 个批次，可让现有 3 路并发真正生效；
# 断句仍保留 20 条上限，避免无意义地增加云端请求数。
POLISH_BATCH_MAX_CUES = 16


API_RETRIES = 3


# 全文断句只提供边界建议，失败时已有逐字守恒的本地分段兜底。云端模型在
# temperature=0 下重复提交同一批次通常仍会撞上相同安全护栏，过去最多
# 白等 90 秒；一次未通过即本地回退，不影响已完成的校对正文。
GROUPING_API_RETRIES = 1


# 正常云端断句批次约 20～30 秒；超过 45 秒后继续等待的收益很低，
# 直接使用本地安全分段可避免一个云端长尾卡住整条队列两分钟。
GROUPING_API_TIMEOUT_SECONDS = 45


# 首轮云端模型已收到全文、气口和强制边界，随后还有完整的本地词法/语义护栏。
# 再请求一次云端校验会把每个断句批次的延迟近乎翻倍，且仍需本地裁决；
# 默认关闭，保留函数供诊断或未来配置化使用。
SECOND_PASS_GROUP_VALIDATION = False


API_TIMEOUT_SECONDS = 120


RUN_REVIEW_ITEMS = _DEFAULT_RUNTIME_CONTEXT.review_items


_REVIEW_ITEM_LOCAL = threading.local()


def _active_review_items():
    return getattr(_REVIEW_ITEM_LOCAL, "items", get_runtime_context().review_items)


def extend_review_items(items):
    _active_review_items().extend(items or [])


@contextmanager
def capture_review_items():
    """Isolate review messages produced by one concurrent stage or API batch."""
    previous = getattr(_REVIEW_ITEM_LOCAL, "items", None)
    captured = []
    _REVIEW_ITEM_LOCAL.items = captured
    try:
        yield captured
    finally:
        if previous is None:
            try:
                del _REVIEW_ITEM_LOCAL.items
            except AttributeError:
                pass
        else:
            _REVIEW_ITEM_LOCAL.items = previous


def reset_review_items():
    runtime_items = get_runtime_context().review_items
    runtime_items.clear()
    if RUN_REVIEW_ITEMS is not runtime_items:
        RUN_REVIEW_ITEMS.clear()
    local_items = getattr(_REVIEW_ITEM_LOCAL, "items", None)
    if local_items is not None:
        local_items.clear()


def add_review_item(timestamp, category, detail, text="", priority=1):
    _active_review_items().append(
        {
            "timestamp": max(0.0, float(timestamp)),
            "category": str(category),
            "detail": str(detail),
            "text": clean_subtitle_text(text) if text else "",
            "priority": int(priority),
        }
    )


def serialize_segments(segments):
    return [asdict(segment) for segment in segments]


def deserialize_segments(items):
    result = []
    for item in items or []:
        words = [WordUnit(**word) for word in item.get("words", [])]
        result.append(
            SpeechSegment(
                segment_id=int(item["segment_id"]),
                start=float(item["start"]),
                end=float(item["end"]),
                text=str(item["text"]),
                confidence=float(item.get("confidence", 0.0)),
                words=words,
                speaker=str(item.get("speaker", "S00")),
                moss_text=str(item.get("moss_text", "")),
                moss_context=str(item.get("moss_context", "")),
                firered_llm_text=str(item.get("firered_llm_text", "")),
                firered_llm_context=str(item.get("firered_llm_context", "")),
                alternate_text=str(item.get("alternate_text", "")),
                alternate_context=str(item.get("alternate_context", "")),
                qwen_asr_text=str(item.get("qwen_asr_text", "")),
                qwen_asr_context=str(item.get("qwen_asr_context", "")),
                overlapping_speaker_conflict=bool(
                    item.get("overlapping_speaker_conflict", False)
                ),
                timing_locked=bool(item.get("timing_locked", False)),
                firered_text=str(item.get("firered_text", "")),
                primary_source=str(item.get("primary_source", "moss-host")),
                reference_consensus=float(item.get("reference_consensus", 0.0)),
            )
        )
    return result


def serialize_cues(cues):
    return [asdict(cue) for cue in cues]


def deserialize_cues(items):
    return [
        SubtitleCue(
            cue_id=int(item["cue_id"]),
            start=float(item["start"]),
            end=float(item["end"]),
            text=str(item["text"]),
            timing_locked=bool(item.get("timing_locked", False)),
            speaker=str(item.get("speaker", "S00")),
        )
        for item in (items or [])
    ]


from twobyteasr.cache import *  # noqa: F401,F403

def pause_exit(code=0):
    raise SystemExit(code)


def choose_media_files():
    root = tk.Tk()
    root.attributes("-topmost", True)
    root.withdraw()
    paths = filedialog.askopenfilenames(
        title="请选择一个或多个原视频/音频文件",
        filetypes=[
            (
                "视频/音频",
                "*.mp4 *.mov *.mkv *.webm *.mp3 *.wav *.m4a *.flac *.aac",
            )
        ],
    )
    root.destroy()
    if not paths:
        pause_exit(0)
    return list(paths)


def load_runtime_game_history():
    try:
        with open(PROFILE_HISTORY_PATH, "r", encoding="utf-8") as file:
            payload = json.load(file)
        values = payload.get("recent_games", [])
        if not isinstance(values, list):
            return []
        result = []
        seen = set()
        for value in values:
            canonical = canonicalize_runtime_game_name(value)
            identity = runtime_game_identity(canonical)
            if canonical and identity and identity not in seen:
                result.append(canonical)
                seen.add(identity)
        return result[:12]
    except (OSError, ValueError, TypeError):
        return []


def save_runtime_game_history(game_name):
    game_name = canonicalize_runtime_game_name(game_name)
    if not game_name:
        return
    recent = [game_name]
    current_identity = runtime_game_identity(game_name)
    recent.extend(
        value
        for value in load_runtime_game_history()
        if runtime_game_identity(value) != current_identity
    )
    try:
        os.makedirs(os.path.dirname(PROFILE_HISTORY_PATH), exist_ok=True)
        atomic_write_json(PROFILE_HISTORY_PATH, {"recent_games": recent[:12]})
    except OSError as exc:
        print(f"   [警告] 内容历史未保存，不影响本批识别：{exc}")


def choose_runtime_content_profile(media_paths):
    """每批任务只问一次内容背景；默认通用模式，不沿用上次游戏。"""
    global RUNTIME_GAME_NAME, RUNTIME_ENABLE_DOMAIN_TERMS, RUNTIME_DISCOVERED_TERMS
    global RUNTIME_OUTPUT_REVIEW_TRACK, RUNTIME_FORCE_REFRESH_API_CACHE
    global RUNTIME_FORCE_REFRESH_POLISH_CACHE, RUNTIME_FORCE_REFRESH_GROUP_CACHE
    global RUNTIME_EXPECTED_SPEAKERS

    result = {"confirmed": False}
    root = tk.Tk()
    root.title("本批字幕内容设置")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=18)
    frame.grid(row=0, column=0, sticky="nsew")
    ttk.Label(
        frame,
        text="游戏 / 内容名称（可直接输入，也可选择；留空就是通用模式）",
    ).grid(row=0, column=0, columnspan=2, sticky="w")

    history = load_runtime_game_history()
    choices = []
    seen_choices = set()
    for value in (*history, *BUILTIN_GAME_PROFILES):
        canonical = canonicalize_runtime_game_name(value)
        identity = runtime_game_identity(canonical)
        if canonical and identity not in seen_choices:
            choices.append(canonical)
            seen_choices.add(identity)
    game_var = tk.StringVar(value="")
    game_box = ttk.Combobox(
        frame,
        textvariable=game_var,
        values=choices,
        width=48,
        state="normal",
    )
    game_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(7, 12))

    terms_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        frame,
        text="游戏术语增强（本地图鉴候选 + 联网复核，PVP时勾选）",
        variable=terms_var,
    ).grid(row=2, column=0, columnspan=2, sticky="w")

    review_track_var = tk.BooleanVar(value=RUNTIME_SETTINGS["switches"]["output_review_track"])
    ttk.Checkbutton(
        frame,
        text="输出疑似吞字幕复核轨（默认关闭，不影响主播分轨）",
        variable=review_track_var,
    ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(5, 0))

    refresh_polish_cache_var = tk.BooleanVar(value=RUNTIME_SETTINGS["cache"]["force_refresh_polish"])
    ttk.Checkbutton(
        frame,
        text="强制刷新 DashScope 校对缓存",
        variable=refresh_polish_cache_var,
    ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(5, 0))

    refresh_group_cache_var = tk.BooleanVar(value=RUNTIME_SETTINGS["cache"]["force_refresh_group"])
    ttk.Checkbutton(
        frame,
        text="强制刷新 DashScope 断句缓存",
        variable=refresh_group_cache_var,
    ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(5, 0))

    ttk.Label(frame, text="预计主播人数：").grid(row=6, column=0, sticky="w", pady=(7, 0))
    expected_speakers_var = tk.StringVar(value="自动")
    ttk.Combobox(
        frame,
        textvariable=expected_speakers_var,
        values=("自动", "1", "2", "3", "4", "5", "6"),
        width=8,
        state="readonly",
    ).grid(row=6, column=1, sticky="w", pady=(7, 0))

    def manage_learned_terms():
        game_name = canonicalize_runtime_game_name(game_var.get())
        if not game_name:
            messagebox.showinfo("已学习术语", "请先输入或选择游戏名称。", parent=root)
            return
        mappings = learned_mappings_for_game(game_name)
        dialog = tk.Toplevel(root)
        dialog.title(f"已学习术语｜{game_name}")
        dialog.attributes("-topmost", True)
        dialog.transient(root)
        dialog.grab_set()
        container = ttk.Frame(dialog, padding=12)
        container.grid(row=0, column=0, sticky="nsew")
        listbox = tk.Listbox(container, width=66, height=14, selectmode=tk.EXTENDED)
        listbox.grid(row=0, column=0, columnspan=2, sticky="nsew")
        for item in mappings:
            marker = "已确认" if item.get("confirmed") else "联网核验"
            listbox.insert(tk.END, f"{item.get('from')} → {item.get('to')}  [{marker}]")

        def remove_selected():
            selected = list(listbox.curselection())
            if not selected:
                return
            keys = [(mappings[index]["from"], mappings[index]["to"]) for index in selected]
            removed = delete_learned_mappings(game_name, keys)
            if removed:
                for index in reversed(selected):
                    listbox.delete(index)
                    mappings.pop(index)

        ttk.Button(container, text="删除所选", command=remove_selected).grid(
            row=1, column=0, sticky="e", padx=(0, 8), pady=(10, 0)
        )
        ttk.Button(container, text="关闭", command=dialog.destroy).grid(
            row=1, column=1, sticky="w", pady=(10, 0)
        )

    ttk.Button(frame, text="管理已学习术语…", command=manage_learned_terms).grid(
        row=7, column=0, columnspan=2, sticky="w", pady=(7, 0)
    )

    def auto_enable_terms(*_):
        # 用户只要主动选择或输入了内容名称，就默认打开术语增强；仍可在
        # 输入完成后手动取消勾选。留空始终保持通用模式。
        if clean_subtitle_text(game_var.get()):
            terms_var.set(True)

    game_var.trace_add("write", auto_enable_terms)
    ttk.Label(
        frame,
        text=(
            "留空：不会读取上一个游戏的背景和词表。\n"
            "选择或输入名称：默认勾选术语增强，可手动关闭。\n"
            "勾选后才会联网找官方词汇，并通过近音/多处出现的安全门。"
        ),
        foreground="#555555",
        justify="left",
    ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 14))

    preview = "、".join(os.path.basename(path) for path in media_paths[:3])
    if len(media_paths) > 3:
        preview += f" 等 {len(media_paths)} 个文件"
    ttk.Label(frame, text=f"本批素材：{preview}", wraplength=500).grid(
        row=9, column=0, columnspan=2, sticky="w", pady=(0, 14)
    )

    def confirm():
        global RUNTIME_GAME_NAME, RUNTIME_ENABLE_DOMAIN_TERMS, RUNTIME_DISCOVERED_TERMS
        global RUNTIME_OUTPUT_REVIEW_TRACK, RUNTIME_FORCE_REFRESH_API_CACHE
        global RUNTIME_FORCE_REFRESH_POLISH_CACHE, RUNTIME_FORCE_REFRESH_GROUP_CACHE
        global RUNTIME_EXPECTED_SPEAKERS
        game_name = canonicalize_runtime_game_name(game_var.get())
        enable_terms = bool(game_name and terms_var.get())
        RUNTIME_GAME_NAME = game_name
        RUNTIME_ENABLE_DOMAIN_TERMS = enable_terms
        RUNTIME_DISCOVERED_TERMS = set()
        RUNTIME_OUTPUT_REVIEW_TRACK = bool(review_track_var.get())
        RUNTIME_FORCE_REFRESH_POLISH_CACHE = bool(refresh_polish_cache_var.get())
        RUNTIME_FORCE_REFRESH_GROUP_CACHE = bool(refresh_group_cache_var.get())
        RUNTIME_FORCE_REFRESH_API_CACHE = False
        selected_speaker_count = expected_speakers_var.get()
        RUNTIME_EXPECTED_SPEAKERS = (
            int(selected_speaker_count) if selected_speaker_count.isdigit() else 0
        )
        if game_name:
            save_runtime_game_history(game_name)
        result["confirmed"] = True
        root.destroy()

    def cancel():
        root.destroy()

    ttk.Button(frame, text="开始识别", command=confirm).grid(
        row=10, column=0, sticky="e", padx=(0, 8)
    )
    ttk.Button(frame, text="取消", command=cancel).grid(
        row=10, column=1, sticky="w"
    )
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.update_idletasks()
    x = max(0, (root.winfo_screenwidth() - root.winfo_reqwidth()) // 2)
    y = max(0, (root.winfo_screenheight() - root.winfo_reqheight()) // 3)
    root.geometry(f"+{x}+{y}")
    game_box.focus_set()
    root.mainloop()

    if result["confirmed"]:
        if RUNTIME_GAME_NAME:
            mode = "联网术语增强" if RUNTIME_ENABLE_DOMAIN_TERMS else "仅弱背景"
            print(f"[内容设置] 《{RUNTIME_GAME_NAME}》｜{mode}")
        else:
            print("[内容设置] 通用模式｜不读取旧游戏背景、不启用游戏词表")
    return result["confirmed"]


def detect_timeline_fps(media_path):
    """直接选视频时读取真实帧率；纯音频沿用 60 fps 兜底。"""
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        return TIMELINE_FPS
    command = [
        ffprobe_path,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=avg_frame_rate",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        media_path,
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
            **hidden_subprocess_kwargs(),
        )
        value = result.stdout.strip().splitlines()[0]
        numerator, denominator = value.split("/", 1)
        fps = float(numerator) / float(denominator)
        if 10.0 <= fps <= 240.0:
            print(f"   检测到视频时间轴：{fps:.6g} fps。")
            return fps
    except Exception:
        pass
    print(f"   未检测到视频帧率，按 {TIMELINE_FPS:.6g} fps 对齐。")
    return TIMELINE_FPS


def output_paths_for_media(media_path):
    file_dir = os.path.dirname(media_path)
    base_name = os.path.splitext(os.path.basename(media_path))[0]
    return (
        os.path.join(file_dir, f"{base_name}_剪映文稿.txt"),
        os.path.join(file_dir, f"{base_name}_剪映文稿.srt"),
    )


def filter_overwrite_media(media_paths):
    existing_media = []
    for media_path in media_paths:
        if any(os.path.exists(path) for path in output_paths_for_media(media_path)):
            existing_media.append(media_path)
    if not existing_media:
        return list(media_paths)

    root = tk.Tk()
    root.attributes("-topmost", True)
    root.withdraw()
    preview = [os.path.basename(path) for path in existing_media[:12]]
    if len(existing_media) > len(preview):
        preview.append(f"……另有 {len(existing_media) - len(preview)} 个")
    answer = messagebox.askyesnocancel(
        "覆盖已有字幕",
        f"{len(existing_media)} 个素材已经存在字幕结果：\n\n"
        + "\n".join(preview)
        + "\n\n选择“是”覆盖；选择“否”跳过这些素材；选择“取消”停止运行。",
        parent=root,
        default=messagebox.CANCEL,
    )
    root.destroy()
    if answer is None:
        return []
    if answer:
        return list(media_paths)
    existing_set = set(existing_media)
    return [path for path in media_paths if path not in existing_set]


def format_elapsed(seconds):
    seconds = max(0, int(round(float(seconds))))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}小时{minutes:02d}分{secs:02d}秒"
    if minutes:
        return f"{minutes}分{secs:02d}秒"
    return f"{secs}秒"


def run_timed_stage(index, total, label, resource, runner):
    cancellation_token = (
        get_runtime_context().cancellation_token or RUNTIME_CANCELLATION_TOKEN
    )
    if cancellation_token is not None:
        cancellation_token.raise_if_cancelled()
    print(f"\n[阶段 {index}/{total}] {label}（{resource}）", flush=True)
    started = time.perf_counter()
    record_run_event(
        "stage_started",
        index=index,
        total=total,
        label=label,
        resource=resource,
    )
    try:
        value = runner()
    except BaseException as exc:
        elapsed = time.perf_counter() - started
        cancelled = isinstance(exc, KeyboardInterrupt) or exc.__class__.__name__ == "CancelledError"
        record_run_event(
            "stage_cancelled" if cancelled else "stage_failed",
            index=index,
            label=label,
            elapsed_seconds=round(elapsed, 3),
            error=redact_runtime_secrets(exc),
            traceback=redact_runtime_secrets(traceback.format_exc()),
        )
        raise
    elapsed = time.perf_counter() - started
    record_run_event(
        "stage_completed",
        index=index,
        label=label,
        elapsed_seconds=round(elapsed, 3),
    )
    print(f"[阶段完成] {label}：{format_elapsed(elapsed)}", flush=True)
    return value


def show_completion_message(successes, failures, elapsed):
    lines = [
        f"处理完成：成功 {len(successes)} 个，失败 {len(failures)} 个。",
        f"总耗时：{format_elapsed(elapsed)}。",
    ]
    if failures:
        lines.append("\n失败详情：")
        for path, error in failures[:6]:
            compact_error = " ".join(str(error).split())[:260]
            lines.append(f"- {os.path.basename(path)}\n  {compact_error}")
    root = tk.Tk()
    root.attributes("-topmost", True)
    root.withdraw()
    if failures:
        messagebox.showwarning("字幕队列完成", "\n".join(lines), parent=root)
    else:
        messagebox.showinfo("字幕队列完成", "\n".join(lines), parent=root)
    root.destroy()


def check_runtime():
    from importlib.metadata import PackageNotFoundError, version as package_version
    missing = []
    for package_name in ("qwen-asr", "pypinyin", "requests", "jieba", "PySide6", "QtAwesome"):
        try:
            package_version(package_name)
        except PackageNotFoundError:
            missing.append(package_name)
    if missing:
        raise RuntimeError(
            "缺少运行依赖："
            + ", ".join(missing)
            + "\n请执行：\n"
            'python -m pip install "qwen-asr==0.0.6" '
            '"pypinyin==0.55.0" "requests==2.33.0"'
        )
    for executable in ("ffmpeg", "ffprobe"):
        resolved = shutil.which(executable)
        if resolved is None:
            raise RuntimeError(f"缺少 {executable}，请先加入 PATH。")
        # 可执行性验证：部分环境（winget 安装中断/缺运行库）下 exe 会
        # 0xc0000005 崩溃，运行中才暴露。提前探测并给出明确提示。
        try:
            completed = subprocess.run(
                [resolved, "-version"],
                capture_output=True,
                timeout=20,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )
        except (OSError, subprocess.SubprocessError):
            completed = None
        if completed is None or completed.returncode not in (0, 1):
            raise RuntimeError(
                f"{executable} 无法正常运行（可能已损坏或缺少运行库）。\n"
                "请重新安装 FFmpeg：\n"
                "  winget uninstall Gyan.FFmpeg\n"
                "  winget install Gyan.FFmpeg\n"
                "或从 https://www.gyan.dev/ffmpeg/builds/ 下载完整版解压到 C:\\ffmpeg\\bin"
            )


def build_hf_endpoints():
    """Retained for compatibility; authenticated traffic may only use the official host."""
    return ["https://huggingface.co"]


# 兼容门面：subtitle_core 与 twobyteasr 互为循环导入，本处导入必须位于配置区之后，
# 请勿上移或把函数定义插到这些 import 语句中间。
from twobyteasr.text_rules import *  # noqa: F401,F403
from twobyteasr.asr import *  # noqa: F401,F403


def best_alternate_window(primary, raw_alternate):
    """裁掉时间窗中串入的邻句字，只保留最像当前语音段的一小段。"""
    primary_content = content_only(primary)
    alternate_content = content_only(raw_alternate)
    if not primary_content or not alternate_content:
        return "", 0.0

    target_length = len(primary_content)
    minimum_length = max(1, target_length - 2)
    maximum_length = min(len(alternate_content), target_length + 2)
    best_text = ""
    best_score = 0.0
    for window_length in range(minimum_length, maximum_length + 1):
        for start in range(0, len(alternate_content) - window_length + 1):
            window = alternate_content[start : start + window_length]
            text_similarity = SequenceMatcher(
                None, primary_content, window, autojunk=False
            ).ratio()
            phonetic_similarity = SequenceMatcher(
                None,
                phonetic_text(primary_content),
                phonetic_text(window),
                autojunk=False,
            ).ratio()
            # 除非明显更像，否则优先保留与主识别接近的完整句长。
            length_penalty = abs(window_length - target_length) * 0.060
            score = (
                max(text_similarity, phonetic_similarity) * 0.75
                + min(text_similarity, phonetic_similarity) * 0.25
                - length_penalty
            )
            if score > best_score:
                best_score = score
                best_text = window
    return best_text, best_score


LEGITIMATE_REPEATED_VOCALS = set("哈啊嗯哦嘿呵呜啦哎呀")


def load_glossary():
    if not os.path.exists(GLOSSARY_PATH):
        print("   未找到 glossary.txt，本次不使用专名参考。")
        return []

    with open(GLOSSARY_PATH, "r", encoding="utf-8-sig") as file:
        terms = [
            line.strip()
            for line in file
            if line.strip() and not line.lstrip().startswith("#")
        ]

    if len(terms) > 200:
        print("   [警告] glossary.txt 超过 200 行，本次只读取前 200 行。")
        terms = terms[:200]
    print(f"   已读取 {len(terms)} 个弱参考专名。")
    return terms


def load_content_context(media_title=""):
    """按本次弹窗选择生成背景；不再要求剪辑者逐期修改文本文件。"""
    if not RUNTIME_GAME_NAME:
        context = (
            "普通中文直播、对话或游戏视频。不要沿用任何旧游戏的角色、技能或机制词；"
            "只根据本期声音证据校对普通同音字，无法确认时保留 MOSS 主稿。"
            f"素材标题：{media_title}。"
        )
    elif RUNTIME_ENABLE_DOMAIN_TERMS:
        context = (
            f"当前素材与《{RUNTIME_GAME_NAME}》有关。可联网核对该游戏的官方角色、生物、"
            "技能、机制、队伍和战斗术语；只在读音、上下文和多处证据共同支持时修正，"
            f"无法确认时保留 MOSS 主稿。素材标题：{media_title}。"
        )
    else:
        context = (
            f"当前素材与《{RUNTIME_GAME_NAME}》有关，但游戏名只作为弱背景；"
            "本次未启用联网术语增强，不要主动套用角色、技能或机制词，"
            f"无法确认时保留 MOSS 主稿。素材标题：{media_title}。"
        )
    print(f"   [项目背景] {context}")
    return context


def load_verified_game_terms():
    """从所选游戏的结构化配置读取核验词，不要求剪辑者修改 TXT。"""
    if not RUNTIME_ENABLE_DOMAIN_TERMS:
        print("   [游戏词表] 本次未启用，不读取游戏专名配置。")
        return []
    terms = active_profile_terms()
    if not terms:
        print(
            f"   [游戏词表] 《{RUNTIME_GAME_NAME}》没有本地核验表；"
            "仅使用联网高置信候选与本地安全门。"
        )
        return []
    print(f"   已读取 {len(terms)} 个《{RUNTIME_GAME_NAME}》核验游戏词。")
    return terms


def repair_with_contextual_profile_aliases(segments):
    """短日常词只有在独立 ASR 明确写出目标专名时才替换。"""
    alias_map = active_contextual_alias_map()
    if not alias_map:
        return segments
    changes = []
    for segment in segments:
        references = [
            content_only(value)
            for value in (
                segment.firered_text,
                segment.qwen_asr_text,
                segment.firered_llm_text,
                segment.alternate_text,
            )
            if content_only(value)
        ]
        for source, target in alias_map.items():
            if source not in content_only(segment.text):
                continue
            exact_support = sum(target in value for value in references)
            if exact_support < 1:
                continue
            before = segment.text
            segment.text = clean_subtitle_text(segment.text.replace(source, target))
            if segment.text != before:
                changes.append((source, target))
    if changes:
        sample = "、".join(f"{source}→{target}" for source, target in changes[:12])
        print(f"   [语境术语修正] 独立 ASR 支持 {len(changes)} 处；示例：{sample}。")
    return segments


def repair_with_verified_game_terms(segments, verified_terms):
    """用核验词+读音+独立 ASR 支持修专名；无证据时绝不猜。"""
    changes = []
    contextual_aliases = active_contextual_alias_map()
    terms = sorted(
        {content_only(term) for term in verified_terms if content_only(term)},
        key=len,
        reverse=True,
    )
    for segment in segments:
        for _ in range(3):
            text = content_only(segment.text)
            references = [
                content_only(value)
                for value in (
                    segment.firered_text,
                    segment.qwen_asr_text,
                    segment.firered_llm_text,
                )
                if content_only(value)
            ]
            best = None
            for target in terms:
                target_sound = phonetic_text(target)
                exact_reference_support = (
                    target not in text and any(target in value for value in references)
                )
                for length in range(max(2, len(target) - 1), len(target) + 2):
                    for start in range(0, len(text) - length + 1):
                        source = text[start : start + length]
                        if (
                            source in terms
                            or source == target
                            or source in target
                            or target in source
                        ):
                            continue
                        source_sound = phonetic_text(source)
                        similarity = SequenceMatcher(
                            None,
                            source_sound,
                            target_sound,
                            autojunk=False,
                        ).ratio()
                        independent_support = exact_reference_support and similarity >= 0.76
                        contextual_target = contextual_aliases.get(source) == target
                        near_exact_official = (
                            len(source) == len(target)
                            and similarity >= 0.96
                            and target[-1:] in GLOBAL_DOMAIN_TERM_SUFFIXES
                            and not contextual_target
                        )
                        if not (independent_support or near_exact_official):
                            continue
                        candidate = (
                            int(independent_support),
                            similarity,
                            len(target),
                            -start,
                            start,
                            source,
                            target,
                            "独立ASR+核验词" if independent_support else "严格近音+核验词",
                        )
                        if best is None or candidate[:4] > best[:4]:
                            best = candidate
            if best is None:
                break
            _, similarity, _, _, start, source, target, basis = best
            before = segment.text
            # segment.text 已被 normalize 成紧凑正文，content_only 的位置在这里一致。
            segment.text = clean_subtitle_text(
                text[:start] + target + text[start + len(source) :]
            )
            changes.append(
                (segment.segment_id, source, target, similarity, basis, before, segment.text)
            )
    if changes:
        sample = "、".join(
            f"{source}→{target}"
            for _, source, target, _, _, _, _ in changes[:12]
        )
        print(f"   [核验词修正] 共 {len(changes)} 处；示例：{sample}。")
    return segments


# 兼容门面：同上，保持在配置区之后导入，请勿上移或改顺序。
from twobyteasr.correction import *  # noqa: F401,F403
from twobyteasr.segmentation import *  # noqa: F401,F403
from twobyteasr.timing import *  # noqa: F401,F403
from twobyteasr.output import *  # noqa: F401,F403
from twobyteasr.speakers import (
    host_voiceprint_status_summary,
    load_host_voiceprint_registry,
)

def run_startup_self_test():
    """运行不加载模型、不访问网络的关键字幕护栏自测。"""
    import contextlib
    import io

    checks = []

    def require(condition, label):
        if not condition:
            raise RuntimeError(label)
        checks.append(label)

    saved_review_items = list(RUN_REVIEW_ITEMS)
    try:
        RUN_REVIEW_ITEMS.clear()
        muted_output = io.StringIO()
        with contextlib.redirect_stdout(muted_output):
            require(
                abs(ISOLATED_CUE_TAIL_SECONDS - 0.20) < 1e-9,
                "字幕尾帧必须固定为 200ms",
            )
            require(
                abs(SHORT_DISPLAY_GAP_BRIDGE_SECONDS - 0.50) < 1e-9,
                "全轨短空白衔接阈值必须固定为 500ms",
            )
            require(
                PREFERRED_MAX_SUBTITLE_CHARS
                <= MAX_SUBTITLE_CHARS
                == COMPLETE_PHRASE_SOFT_MAX_CHARS
                <= 16,
                "字幕舒适目标与最终 16 字硬上限必须生效",
            )
            require(
                format_subtitle_display_text("哦耶还没到保底") == "哦耶还没到保底",
                "完整反应词“哦耶”不得被机械空格拆开",
            )
            require(
                format_subtitle_display_text("OK啊") == "OK啊",
                "完整反应词“OK啊”不得被机械空格拆开",
            )
            require(
                format_subtitle_display_text("没事哎") == "没事 哎",
                "句尾补充反应“哎”前必须保留视觉气口",
            )
            require(
                format_subtitle_display_text("没事没事失败乃成功之母")
                == "没事没事 失败乃成功之母",
                "重复反应与后续完整判断之间必须保留视觉气口",
            )

            moderate_particle_pause = [
                SpeechSegment(
                    1, 0.0, 1.0, "哦耶还没到保底我就抽到", 0.9, [], speaker="S01"
                ),
                SpeechSegment(2, 2.351, 3.0, "了哈哈", 0.9, [], speaker="S01"),
            ]
            require(
                11 not in hard_break_character_offsets(moderate_particle_pause),
                "不足 3 秒的停顿不得强制切成“抽到｜了哈哈”",
            )
            particle_batch = [
                SpeechSegment(
                    1,
                    0.0,
                    4.0,
                    "哦耶还没到保底我就抽到了哈哈",
                    0.9,
                    [],
                    speaker="S01",
                )
            ]
            require(
                repair_dependent_particle_boundary_offsets(
                    particle_batch,
                    [11, 12, 14],
                )
                == [7, 14],
                "助词残句必须修成“哦耶还没到保底｜我就抽到了哈哈”",
            )

            midword_batch = [
                SpeechSegment(
                    1,
                    8.41,
                    10.62,
                    "那我们就直接进入一个珊瑚场啊",
                    0.9,
                    [],
                    speaker="S01",
                )
            ]
            midword_offsets = repair_segmenter_word_boundary_offsets(
                midword_batch,
                [7, 14],
            )
            require(
                7 not in set(midword_offsets[:-1]),
                "词边界护栏不得保留 进|入",
            )
            midword_texts = texts_from_boundary_offsets(midword_batch, midword_offsets)
            require(
                all("进" not in text or "进入" in text or not text.endswith("进") for text in midword_texts)
                or midword_texts == ["那我们就直接进入", "一个珊瑚场啊"]
                or midword_texts == ["那我们就直接", "进入一个珊瑚场啊"],
                "进入不得拆成上下两条残词",
            )
            adjacent = repair_mid_word_adjacent_cues(
                [
                    SubtitleCue(1, 8.41, 9.42, "那我们就直接进", speaker="S01"),
                    SubtitleCue(2, 9.42, 10.62, "入一个珊瑚场啊", speaker="S01"),
                    SubtitleCue(3, 39.0, 40.0, "这就是八件藏", speaker="S01"),
                    SubtitleCue(4, 40.0, 41.0, "品的轮廓啊", speaker="S01"),
                ]
            )
            joined = [cue.text for cue in adjacent]
            require(
                not any(text.endswith("进") for text in joined)
                and not any(text.startswith("入") and "进入" not in text for text in joined),
                "相邻字幕兜底必须修好 进|入",
            )
            require(
                not any(text.endswith("藏") for text in joined)
                and not any(text.startswith("品") and "藏品" not in text for text in joined),
                "相邻字幕兜底必须修好 藏|品",
            )
            hang_batch = [
                SpeechSegment(1, 0.0, 2.5, "我们有300万的启动资金啊", 0.9, [], speaker="S01")
            ]
            hang_offsets = repair_hanging_attribute_boundary_offsets(
                hang_batch,
                [8, 13],
            )
            require(
                hang_offsets == [13],
                "300万的｜启动资金啊 必须合并成一句",
            )
            coral_batch = [
                SpeechSegment(
                    1, 8.4, 10.8, "那我们就直接进入一个珊瑚场啊", 0.9, [], speaker="S01"
                )
            ]
            coral_offsets = repair_hanging_attribute_boundary_offsets(
                coral_batch,
                [10, 14],
            )
            coral_texts = texts_from_boundary_offsets(coral_batch, coral_offsets)
            require(
                coral_texts
                in (
                    ["那我们就直接进入一个珊瑚场啊"],
                    ["那我们就直接进入", "一个珊瑚场啊"],
                ),
                "进入一个｜珊瑚场啊 必须整句或切到一个前",
            )
            hang_cues = merge_hanging_attribute_cues(
                [
                    SubtitleCue(1, 0.0, 1.3, "我们有300万的", speaker="S01"),
                    SubtitleCue(2, 1.3, 2.5, "启动资金啊", speaker="S01"),
                    SubtitleCue(3, 8.4, 9.7, "那我们就直接进入一个", speaker="S01"),
                    SubtitleCue(4, 9.7, 10.8, "珊瑚场啊", speaker="S01"),
                ]
            )
            hang_joined = [cue.text for cue in hang_cues]
            require(
                "我们有300万的启动资金啊" in hang_joined,
                "成片轨必须合并 300万的启动资金啊",
            )
            require(
                any("珊瑚场啊" in text and "进入" in text for text in hang_joined)
                or (
                    "那我们就直接进入" in hang_joined
                    and "一个珊瑚场啊" in hang_joined
                ),
                "成片轨必须修好 进入一个｜珊瑚场啊",
            )

            force_units = []
            cursor_t = 0.0
            sample = "那我们就直接进入一个珊瑚场啊"
            for char in content_exact(sample):
                force_units.append(WordUnit(cursor_t, cursor_t + 0.12, char, 1.0))
                cursor_t += 0.12
            forced_local = locally_repair_resegmented_cue(
                sample,
                force_units,
                forced_boundaries={7},
            )
            require(
                [cue.text for cue in forced_local]
                in (
                    ["那我们就直接进入", "一个珊瑚场啊"],
                    ["那我们就直接", "进入一个珊瑚场啊"],
                ),
                "本地修复遇到词中强制点时必须贴到词边界",
            )

            tail_cues = [
                SubtitleCue(1, 0.0, 1.0, "第一句", speaker="S01"),
                SubtitleCue(2, 1.1, 1.5, "第二句", speaker="S01"),
                SubtitleCue(3, 0.0, 1.0, "重叠说话", speaker="S02"),
            ]
            extend_cue_tails_by_speaker(tail_cues, 2.0, TIMELINE_FPS)
            require(
                abs(tail_cues[0].end - 1.1) <= 1.0 / TIMELINE_FPS,
                "同主播下一句必须截断上一句尾帧",
            )
            require(
                abs(tail_cues[2].end - 1.2) <= 1.0 / TIMELINE_FPS,
                "独立字幕尾帧不得超过 200ms",
            )

            bridge_cues = [
                SubtitleCue(1, 0.0, 1.0, "主播一", speaker="S01"),
                SubtitleCue(2, 1.184, 2.0, "主播二", speaker="S02"),
                SubtitleCue(3, 2.6, 3.2, "长空白", speaker="S01"),
            ]
            bridge_short_display_gaps(bridge_cues, 4.0, TIMELINE_FPS)
            require(
                abs(bridge_cues[0].end - bridge_cues[1].start) <= 1.0 / TIMELINE_FPS,
                "跨说话人不足 500ms 的空白必须衔接",
            )
            require(
                abs(bridge_cues[1].end - 2.0) <= 1.0 / TIMELINE_FPS,
                "超过 500ms 的空白必须保留",
            )

            forbidden_samples = {
                "跟我们要调查的事件有线索": "事件",
                "这里有什么跟案发线索有关": "案发",
                "你厨房里边为什么会有": "为什么",
            }
            for sample, term in forbidden_samples.items():
                start = content_exact(sample).find(term)
                forbidden = lexical_forbidden_boundary_offsets(sample)
                require(
                    all(
                        offset in forbidden
                        for offset in range(start + 1, start + len(term))
                    ),
                    f"完整词“{term}”不得从中间断开",
                )

            duplicate_segments = [
                SpeechSegment(
                    1,
                    10.00,
                    14.00,
                    "这个连续签到七天了啊每天都签了",
                    0.9,
                    [],
                    speaker="S01",
                ),
                SpeechSegment(
                    2,
                    10.03,
                    12.10,
                    "这个连续签到七天了啊",
                    0.9,
                    [],
                    speaker="S01",
                ),
            ]
            deduplicated = remove_overlapping_duplicate_segments(duplicate_segments)
            require(
                len(deduplicated) == 1
                and "每天都签了" in deduplicated[0].text,
                "同起点高重叠的完整前缀副本必须删除",
            )
            genuine_repetition = [
                SpeechSegment(1, 20.0, 21.0, "好好好好", 0.9, [], speaker="S01"),
                SpeechSegment(2, 21.5, 22.5, "好好好好", 0.9, [], speaker="S01"),
            ]
            require(
                len(remove_overlapping_duplicate_segments(genuine_repetition)) == 2,
                "没有声学重叠的正常口语重复必须保留",
            )

            onset_cues = [
                SubtitleCue(1, 1.0, 2.0, "句首校准", speaker="S01"),
            ]
            original_start = onset_cues[0].start
            snap_cue_starts_to_vad_onsets(
                onset_cues,
                [{"start": 1.3, "end": 2.0}],
                TIMELINE_FPS,
            )
            require(
                onset_cues[0].start >= original_start,
                "VAD 句首校准绝不能把字幕提前",
            )
            require(
                abs(onset_cues[0].start - 1.3) <= 1.0 / TIMELINE_FPS,
                "静音区字幕必须向后贴到 VAD 起音",
            )

            with tempfile.TemporaryDirectory(prefix="twobyteasr_startup_") as folder:
                txt_path = os.path.join(folder, "sample_剪映文稿.txt")
                srt_path = os.path.join(folder, "sample_剪映文稿.srt")
                output_cues = [
                    SubtitleCue(1, 0.0, 1.0, "主播一", speaker="S01"),
                    SubtitleCue(2, 0.2, 1.2, "主播二", speaker="S02"),
                ]
                result = write_all_outputs_transactional(
                    output_cues,
                    txt_path,
                    srt_path,
                    include_review_track=False,
                )
                speaker_paths = [path for _, path, _ in result["speaker_outputs"]]
                require(
                    os.path.isfile(txt_path) and os.path.isfile(srt_path),
                    "总 TXT/SRT 事务写入必须成功",
                )
                require(
                    len(speaker_paths) == 2 and all(os.path.isfile(path) for path in speaker_paths),
                    "双说话人分轨必须同时生成",
                )
                with open(speaker_paths[0], "r", encoding="utf-8-sig") as first_track:
                    first_text = first_track.read()
                with open(speaker_paths[1], "r", encoding="utf-8-sig") as second_track:
                    second_text = second_track.read()
                require(
                    "主播一" in first_text and "主播二" in second_text,
                    "说话人字幕不得串轨",
                )

            require(
                format_srt_time(1.234) == "00:00:01,234",
                "SRT 毫秒格式必须稳定",
            )
            require(
                callable(_load_secret_value) and callable(require_runtime_secrets),
                "密钥加载器必须可用",
            )
            require(
                "host_voiceprints" in HOST_VOICEPRINT_DIR.replace("\\", "/"),
                "主播声纹目录必须位于 LocalAppData/2ByteASR",
            )
    except Exception as exc:
        raise RuntimeError(f"{STARTUP_SELF_TEST_ID} 未通过：{exc}") from exc
    finally:
        RUN_REVIEW_ITEMS[:] = saved_review_items

    return {
        "id": STARTUP_SELF_TEST_ID,
        "checks": len(checks),
    }
