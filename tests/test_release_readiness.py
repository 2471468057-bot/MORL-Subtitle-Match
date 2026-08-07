import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dependency_lock_has_pinned_public_components():
    lock = json.loads((ROOT / "dependencies.lock.json").read_text(encoding="utf-8"))
    assert lock["python"] == {"main": "3.10", "moss": "3.12"}
    assert set(lock["sources"]) == {"moss", "firered"}
    assert set(lock["models"]) == {
        "moss",
        "firered_vad",
        "firered_aed",
        "qwen_asr",
        "speaker_embedding",
    }
    for group in (lock["sources"], lock["models"]):
        for item in group.values():
            assert len(item["revision"]) == 40
            int(item["revision"], 16)
            assert item["license"] == "Apache-2.0"


def test_launcher_never_falls_back_to_path_python():
    launcher = (ROOT / "2ByteASR.bat").read_text(encoding="utf-8")
    assert "MAIN_PY" not in launcher
    assert ".venv-main" in launcher
    assert "setup_environment.bat" in launcher


def test_gitignore_covers_private_and_large_runtime_state():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in (
        "archive/",
        "backups/",
        "models/",
        "outputs/",
        "reports/",
        "review_tracks/",
        "dist/",
        "2ByteASR.exe",
        "scripts/ShortcutIdentity.exe",
        "design-qa.md",
        "third_party/MOSS-Transcribe-Diarize/",
        "third_party/FireRedASR2S/",
        "*.wav",
        "*.mp4",
    ):
        assert entry in ignored


def test_windows_installer_and_release_workflow_are_present():
    installer = (ROOT / "installer" / "2ByteASR.iss").read_text(encoding="utf-8")
    bootstrap = (ROOT / "scripts" / "bootstrap_install.ps1").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in installer
    assert "AppId={{D2CA55A8-6992-4C39-BAF1-2D790E9B5E26}" in installer
    assert 'Source: "..\\2byteasr_settings.json"; DestDir: "{app}"; Flags: onlyifdoesntexist' in installer
    assert 'Source: "..\\game_profiles.json"; DestDir: "{app}"; Flags: onlyifdoesntexist' in installer
    assert 'Source: "..\\glossary.txt"; DestDir: "{app}"; Flags: onlyifdoesntexist' in installer
    assert "setup_2byteasr.bat" in installer
    assert "astral-sh.uv" in bootstrap
    assert "Gyan.FFmpeg" in bootstrap
    assert "gh release create" in workflow


def test_model_downloader_can_adopt_existing_huggingface_revision_metadata():
    downloader = (ROOT / "scripts" / "download_models.ps1").read_text(encoding="utf-8")
    assert "Test-ModelRevisionMetadata" in downloader
    assert "Test-AllRequiredFilesHashed" in downloader
    assert ".cache\\huggingface\\trees" in downloader
    assert "[跳过]" in downloader
