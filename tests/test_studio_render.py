import subprocess
from pathlib import Path

import pytest

from twobyteasr.studio_render import (
    CONTAINER_CODECS,
    RenderJob,
    RenderSettings,
    build_render_command,
    encoder_choices,
    preview_job,
    run_render_job,
    probe_encoder,
    render_fallback_job,
)
from twobyteasr.ass_compiler import _ass_color


ROOT = Path(__file__).resolve().parents[1]
FFMPEG = ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "tools" / "ffmpeg" / "bin" / "ffprobe.exe"


@pytest.mark.parametrize(
    ("color", "expected"),
    [
        ("#FFFFFFFF", "&H00FFFFFF"),
        ("#80FF0000", "&H7F0000FF"),
        ("#00FF0000", "&HFF0000FF"),
        ("#FF000000", "&H00000000"),
    ],
)
def test_qt_argb_alpha_is_inverted_for_ass_colors(color, expected):
    assert _ass_color(color, "#000000") == expected


def _fixture(tmp_path):
    media = tmp_path / "source.mp4"
    subprocess.run(
        [
            str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(media),
        ],
        check=True,
    )
    ass = tmp_path / "subtitle.ass"
    ass.write_text(
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 320\nPlayResY: 180\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,24,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,15,1\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:00.00,0:00:00.90,Default,,0,0,0,,Burn in\n",
        encoding="utf-8",
    )
    return media, ass


def test_encoder_choices_only_show_machine_available_items():
    choices = encoder_choices(FFMPEG, "h264")
    assert "libx264" in choices
    assert all(name in {"h264_nvenc", "h264_qsv", "h264_amf", "libx264"} for name in choices)
    assert probe_encoder(str(FFMPEG.resolve()), "libx264")


def test_existing_output_requires_explicit_overwrite(tmp_path):
    media, ass = _fixture(tmp_path)
    output = tmp_path / "already-there.mp4"
    output.write_bytes(b"keep")
    job = RenderJob(str(media), str(ass), str(output), RenderSettings(encoder="libx264"))

    with pytest.raises(FileExistsError, match="输出文件已存在"):
        run_render_job(FFMPEG, job)
    assert output.read_bytes() == b"keep"


def test_known_hardware_and_audio_copy_failures_have_safe_fallbacks():
    hardware = RenderJob(
        "source.mp4", "subtitle.ass", "output.mp4",
        RenderSettings(codec="h264", encoder="h264_nvenc"),
    )
    retried, notice = render_fallback_job(
        hardware, RuntimeError("FFmpeg render failed: no capable devices found for nvenc")
    )
    assert retried.settings.encoder == "libx264"
    assert "硬件编码不可用" in notice

    copy_job = RenderJob(
        "source.mp4", "subtitle.ass", "output.mp4",
        RenderSettings(codec="h264", encoder="libx264", audio_codec="copy"),
    )
    retried, notice = render_fallback_job(
        copy_job, RuntimeError("muxer does not support audio codec")
    )
    assert retried.settings.audio_codec == "aac"
    assert "AAC" in notice


def test_preview_is_centered_and_uses_same_command_builder(tmp_path):
    media, ass = _fixture(tmp_path)
    settings = RenderSettings(encoder="libx264", preset="ultrafast")
    job = preview_job(str(media), str(ass), str(tmp_path / "preview.mp4"), settings, 30, 100)
    command = build_render_command(FFMPEG, job)
    assert job.start_seconds == 25
    assert job.duration_seconds == 10
    assert "-vf" in command and any("ass=filename=" in item for item in command)
    filter_chain = command[command.index("-vf") + 1]
    assert "setpts=PTS+25.000/TB" in filter_chain
    assert filter_chain.endswith("setpts=PTS-STARTPTS")
    assert "libx264" in command


def test_container_compatibility_and_audio_controls_reach_ffmpeg(tmp_path):
    media, ass = _fixture(tmp_path)
    output = tmp_path / "delivery.mov"
    settings = RenderSettings(
        container="mov",
        codec="h264",
        encoder="libx264",
        audio_codec="aac",
        audio_bitrate_kbps=256,
        audio_sample_rate=48000,
        audio_channels=2,
    )
    command = build_render_command(FFMPEG, RenderJob(str(media), str(ass), str(output), settings))
    assert CONTAINER_CODECS["webm"] == ("av1",)
    assert command[command.index("-b:a") + 1] == "256k"
    assert command[command.index("-ar") + 1] == "48000"
    assert command[command.index("-ac") + 1] == "2"
    assert "+faststart" in command

    silent = build_render_command(
        FFMPEG,
        RenderJob(str(media), str(ass), str(tmp_path / "silent.mp4"), RenderSettings(encoder="libx264", audio_codec="none")),
    )
    assert "-an" in silent

    invalid = RenderSettings(container="webm", codec="h264")
    try:
        invalid.validate()
    except ValueError as exc:
        assert "not supported" in str(exc)
    else:
        raise AssertionError("WebM must reject H.264")


def test_real_ass_burn_in_produces_playable_mp4(tmp_path):
    media, ass = _fixture(tmp_path)
    output = tmp_path / "burned.mp4"
    settings = RenderSettings(encoder="libx264", preset="ultrafast", quality=28)
    rendered = run_render_job(
        FFMPEG,
        RenderJob(
            str(media), str(ass), str(output), settings, overwrite_existing=True
        ),
    )
    probe = subprocess.run(
        [str(FFPROBE), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height", "-of", "default=nw=1", str(rendered)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "codec_name=h264" in probe.stdout
    assert "width=320" in probe.stdout
    assert rendered.stat().st_size > 1000


def test_render_replaces_output_only_after_success(tmp_path):
    media, ass = _fixture(tmp_path)
    output = tmp_path / "burned.mp4"
    output.write_bytes(b"existing")
    settings = RenderSettings(encoder="libx264", preset="ultrafast", quality=28)
    rendered = run_render_job(
        FFMPEG,
        RenderJob(
            str(media), str(ass), str(output), settings, overwrite_existing=True
        ),
    )
    assert rendered == output.resolve()
    assert output.stat().st_size > 1000
    assert not list(tmp_path.glob("*.partial.mp4"))
