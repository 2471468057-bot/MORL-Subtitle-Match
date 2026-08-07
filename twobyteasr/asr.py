"""asr stage implementation extracted from subtitle_core."""

import threading

# The core owns runtime configuration; these imports preserve the existing public contract.
from subtitle_core import *  # noqa: F401,F403

__all__ = [
    'load_qwen_asr_model',
    'resolve_qwen_asr_local_source',
    'build_qwen_asr_context',
    'build_qwen_asr_chunks',
    'transcribe_qwen_reference',
    'write_pcm16_wav',
    'transcribe_firered_reference',
    'begin_local_asr_session',
    'end_local_asr_session',
]


_SESSION_LOCK = threading.RLock()
_SESSION_ENABLED = False
_SESSION_QWEN_MODEL = None
# 保护 torch.cuda.is_bf16_supported 的临时替换（FireRed 需要强制 FP16），
# 防止与 Qwen 的 dtype 决策并发读取时出现 patch/恢复次序颠倒的残留状态。
_TORCH_PATCH_LOCK = threading.RLock()


def _cuda_bf16_supported():
    """读取 torch 的 bf16 支持标志，与 FireRed 的临时替换互斥。"""
    import torch

    with _TORCH_PATCH_LOCK:
        return torch.cuda.is_bf16_supported()


def begin_local_asr_session():
    """Keep reusable local models alive until the current media queue finishes."""
    global _SESSION_ENABLED
    with _SESSION_LOCK:
        _SESSION_ENABLED = True


def end_local_asr_session():
    """Release queue-owned models on success, failure, or cancellation."""
    global _SESSION_ENABLED, _SESSION_QWEN_MODEL
    with _SESSION_LOCK:
        model = _SESSION_QWEN_MODEL
        _SESSION_QWEN_MODEL = None
        _SESSION_ENABLED = False
    if model is None:
        return
    del model
    import gc
    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("   [模型会话] 已释放队列复用的 Qwen3-ASR 模型。")


def _reuse_or_remember_qwen_model(model):
    global _SESSION_QWEN_MODEL
    with _SESSION_LOCK:
        if _SESSION_ENABLED:
            _SESSION_QWEN_MODEL = model
    return model


def _session_qwen_model():
    with _SESSION_LOCK:
        if _SESSION_ENABLED and _SESSION_QWEN_MODEL is not None:
            print("   [模型复用] 沿用本批已加载的 Qwen3-ASR。")
            return _SESSION_QWEN_MODEL
    return None


def _qwen_model_is_session_owned(model):
    with _SESSION_LOCK:
        return _SESSION_ENABLED and model is _SESSION_QWEN_MODEL

def load_qwen_asr_model():
    """只加载依赖锁指定且通过完整性校验的本地 Qwen3-ASR。"""
    import torch
    from qwen_asr import Qwen3ASRModel
    from twobyteasr.model_integrity import verify_model_files

    if not torch.cuda.is_available():
        print("   [警告] Qwen3-ASR 1.7B 需要 CUDA，本次跳过第三套文字参考。")
        return None
    reused = _session_qwen_model()
    if reused is not None:
        return reused

    dtype = torch.bfloat16 if _cuda_bf16_supported() else torch.float16
    model_kwargs = {
        "dtype": dtype,
        "device_map": "cuda:0",
        "max_inference_batch_size": QWEN_ASR_BATCH_SIZE,
        "max_new_tokens": QWEN_ASR_MAX_NEW_TOKENS,
    }
    errors = []
    local_source = resolve_qwen_asr_local_source()
    if local_source:
        print(f"   Qwen3-ASR 本地模型：{local_source}")
        try:
            verify_model_files("qwen_asr", local_source)
            return _reuse_or_remember_qwen_model(
                Qwen3ASRModel.from_pretrained(
                    local_source,
                    local_files_only=True,
                    **model_kwargs,
                )
            )
        except Exception as exc:
            errors.append(f"本地目录: {exc}")
            print("   Qwen3-ASR 本地目录不可用或完整性校验失败。")

    if not local_source:
        errors.append("本地模型: 未找到完整的固定版本")
        print("   Qwen3-ASR 本地模型不完整；请重新运行 download_models.bat。")

    print(
        "   [警告] Qwen3-ASR 1.7B 加载失败，本次仍可沿用 FireRed/MOSS：\n"
        + "\n".join(errors)
    )
    return None


def resolve_qwen_asr_local_source():
    """返回完整的项目内模型目录，不选取未固定版本的用户缓存。"""
    env_dir = os.environ.get("2BYTEASR_QWEN3_ASR_DIR", "").strip()
    candidates = []
    if env_dir:
        candidates.append(os.path.expanduser(env_dir))
    candidates.extend(
        [
            os.path.join(SCRIPT_DIR, "models", "Qwen3-ASR-1.7B"),
            os.path.join(SCRIPT_DIR, "models", "Qwen", "Qwen3-ASR-1.7B"),
        ]
    )
    seen = set()
    for candidate in candidates:
        normalized = os.path.normcase(os.path.abspath(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.isfile(os.path.join(candidate, "config.json")):
            return candidate
    return ""


def build_qwen_asr_context(media_path):
    """只给 Qwen3-ASR 内容类型与文件名，不把 glossary 当强制热词。"""
    media_title = os.path.splitext(os.path.basename(media_path))[0]
    return (
        f"这是中文二次元游戏实况，文件名为《{media_title}》。"
        "请忠实转写实际语音，注意角色、技能和机制专名，"
        "不要凭文件名补写未说内容。"
    )


def build_qwen_asr_chunks(audio, speech_regions, sampling_rate=16000):
    """把 VAD 人声区间合并成短块，避免 Qwen 自回归解码整段长音频。"""
    audio_seconds = len(audio) / sampling_rate
    regions = [
        {
            "start": max(0.0, float(item["start"])),
            "end": min(audio_seconds, float(item["end"])),
        }
        for item in speech_regions
        if float(item["end"]) > float(item["start"])
    ]
    if not regions:
        regions = []
        offset = 0.0
        while offset < audio_seconds:
            regions.append(
                {
                    "start": offset,
                    "end": min(audio_seconds, offset + QWEN_ASR_CHUNK_SECONDS),
                }
            )
            offset += QWEN_ASR_CHUNK_SECONDS

    merged_ranges = []
    current_start = None
    current_end = None
    for region in regions:
        start = region["start"]
        end = region["end"]
        if current_start is None:
            current_start, current_end = start, end
            continue
        if end - current_start > QWEN_ASR_CHUNK_SECONDS:
            merged_ranges.append((current_start, current_end))
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_start is not None:
        merged_ranges.append((current_start, current_end))

    chunks = []
    for start, end in merged_ranges:
        padded_start = max(0.0, start - QWEN_ASR_AUDIO_PAD_SECONDS)
        padded_end = min(audio_seconds, end + QWEN_ASR_AUDIO_PAD_SECONDS)
        left = int(round(padded_start * sampling_rate))
        right = int(round(padded_end * sampling_rate))
        if right <= left:
            continue
        chunks.append(
            {
                "start": padded_start,
                "end": padded_end,
                "audio": (audio[left:right], sampling_rate),
            }
        )
    return chunks


def transcribe_qwen_reference(audio_path, speech_regions, shared_audio=None):
    """Qwen3-ASR 1.7B 提供第三份中文文字证据，不生成或修改时间戳。"""
    if not USE_QWEN_ASR_REFERENCE:
        return []

    import gc
    import torch

    model = None
    audio = shared_audio
    owns_audio = shared_audio is None
    try:
        print(f"   加载 Qwen3-ASR 1.7B，按 VAD 短块生成第三份文字参考...")
        sampling_rate = AUDIO_SAMPLE_RATE
        if audio is None:
            audio = decode_audio_to_array(audio_path)
        chunks = build_qwen_asr_chunks(audio, speech_regions, sampling_rate)
        if not chunks:
            print("   [警告] Qwen3-ASR 没有可转写的人声短块，本次跳过。")
            return []

        model = load_qwen_asr_model()
        if model is None:
            add_review_item(
                0.0,
                "Qwen3跳过",
                "Qwen3 复核未运行，本次仍使用 FireRed/MOSS",
                priority=1,
            )
            return []

        context = build_qwen_asr_context(audio_path)
        started = time.perf_counter()
        references = []
        batch_count = (len(chunks) + QWEN_ASR_BATCH_SIZE - 1) // QWEN_ASR_BATCH_SIZE
        for batch_index, offset in enumerate(
            range(0, len(chunks), QWEN_ASR_BATCH_SIZE), 1
        ):
            batch = chunks[offset : offset + QWEN_ASR_BATCH_SIZE]
            batch_started = time.perf_counter()
            results = model.transcribe(
                audio=[item["audio"] for item in batch],
                context=[context] * len(batch),
                language=["Chinese"] * len(batch),
                return_time_stamps=False,
            )
            for chunk, result in zip(batch, results):
                text = clean_subtitle_text(result.text)
                if content_only(text):
                    references.append(
                        {
                            "start": chunk["start"],
                            "end": chunk["end"],
                            "text": text,
                        }
                    )
            print(
                f"      Qwen3-ASR 批次 {batch_index}/{batch_count}："
                f"{time.perf_counter() - batch_started:.1f} 秒",
                flush=True,
            )
        elapsed = time.perf_counter() - started
        print(
            f"   [完成] Qwen3-ASR：{len(references)}/{len(chunks)} 个短块，"
            f"纯转写 {elapsed:.1f} 秒。"
        )
        return references
    except Exception as exc:
        print(f"   [警告] Qwen3-ASR 复核失败，自动沿用 FireRed/MOSS：{exc}")
        add_review_item(
            0.0,
            "Qwen3失败",
            str(exc)[:160],
            priority=2,
        )
        return []
    finally:
        session_owned = model is not None and _qwen_model_is_session_owned(model)
        if model is not None and not session_owned:
            del model
        if owns_audio and audio is not None:
            del audio
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def write_pcm16_wav(path, audio):
    """从统一 float32 采样直接写 WAV，避免 ffmpeg 分段 seek 的时间取整。"""
    import numpy as np

    pcm = np.clip(np.asarray(audio), -1.0, 1.0)
    pcm = np.rint(pcm * 32767.0).astype("<i2", copy=False)
    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(AUDIO_SAMPLE_RATE)
        wav_file.writeframes(pcm.tobytes())


def transcribe_firered_reference(audio_source, audio_seconds, *, beam_size=3):
    """FireRed 提供第二份文字证据和可信边界，不直接覆盖主转写。"""
    if not USE_FIRERED_BOUNDARY_REFINEMENT:
        return []
    if not os.path.isdir(FIRERED_SOURCE_DIR) or not os.path.isdir(FIRERED_MODEL_DIR):
        print("   FireRed 边界模型未安装，本次仅做 60 fps 对齐。")
        return []
    print("   加载 FireRedASR2-AED，辅助校准字级首尾边界...")
    import gc
    import torch

    if not torch.cuda.is_available():
        print("   [警告] FireRed 边界校准需要 CUDA，本次跳过。")
        return []

    if FIRERED_SOURCE_DIR not in sys.path:
        sys.path.insert(0, FIRERED_SOURCE_DIR)

    original_bf16_check = torch.cuda.is_bf16_supported
    with _TORCH_PATCH_LOCK:
        # FireRedASR2-AED 在 bf16 下不稳定，强制 FP16；持锁替换防止并发残留。
        torch.cuda.is_bf16_supported = lambda: False
    model = None
    audio = None
    owns_audio = isinstance(audio_source, (str, bytes, os.PathLike))
    try:
        from twobyteasr.model_integrity import verify_model_files

        verify_model_files("firered_aed", FIRERED_MODEL_DIR)
        from fireredasr2s.fireredasr2 import FireRedAsr2, FireRedAsr2Config

        audio = (
            decode_audio_to_array(audio_source)
            if owns_audio
            else audio_source
        )
        decoded_seconds = len(audio) / AUDIO_SAMPLE_RATE
        audio_seconds = min(float(audio_seconds), decoded_seconds)

        config = FireRedAsr2Config(
            use_gpu=True,
            use_half=True,
            beam_size=max(1, min(8, int(beam_size))),
            nbest=1,
            decode_max_len=0,
            softmax_smoothing=1.25,
            aed_length_penalty=0.6,
            eos_penalty=1.0,
            return_timestamp=True,
        )
        model = FireRedAsr2.from_pretrained("aed", FIRERED_MODEL_DIR, config)
        tokens = []
        with tempfile.TemporaryDirectory(prefix="asr_firered_") as temp_dir:
            offset = 0.0
            chunk_index = 0
            while offset < audio_seconds - 0.01:
                chunk_index += 1
                chunk_end = min(audio_seconds, offset + FIRERED_CHUNK_SECONDS)
                is_first = chunk_index == 1
                is_last = chunk_end >= audio_seconds - 0.01
                owned_start = 0.0 if is_first else offset + 1.0
                owned_end = float("inf") if is_last else offset + FIRERED_CHUNK_SECONDS - 1.0
                chunk_path = os.path.join(temp_dir, f"chunk_{chunk_index:04d}.wav")
                start_sample = int(round(offset * AUDIO_SAMPLE_RATE))
                end_sample = int(round(chunk_end * AUDIO_SAMPLE_RATE))
                write_pcm16_wav(chunk_path, audio[start_sample:end_sample])
                result = model.transcribe(
                    [f"chunk_{chunk_index:04d}"], [chunk_path]
                )[0]
                for token, start, end in result.get("timestamp") or []:
                    global_start = offset + float(start)
                    global_end = offset + float(end)
                    midpoint = (global_start + global_end) / 2.0
                    if owned_start <= midpoint < owned_end:
                        tokens.append(
                            {
                                "text": str(token),
                                "start": global_start,
                                "end": global_end,
                                "confidence": float(result.get("confidence", 0.75)),
                            }
                        )
                if is_last:
                    break
                offset += FIRERED_CHUNK_STEP_SECONDS

        print(f"   [完成] FireRed：{len(tokens)} 个候选字词边界。")
        return tokens
    except Exception as exc:
        print(f"   [警告] FireRed-AED 识别失败：{exc}")
        return []
    finally:
        with _TORCH_PATCH_LOCK:
            torch.cuda.is_bf16_supported = original_bf16_check
        if model is not None:
            del model
        if owns_audio and audio is not None:
            del audio
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# subtitle_core 通过 `from twobyteasr.asr import *` 使用本模块实现；
# 反向注册保证 legacy 端访问到的也是这里的版本，避免循环导入下的两份实现分叉。
import subtitle_core as _core
for _name in __all__:
    setattr(_core, _name, globals()[_name])
del _core, _name


