"""MOSS readiness accepts the full-context worker output (segments per chunk)."""
import importlib.util
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "scripts" / "validate_prepared_model.py"
    spec = importlib.util.spec_from_file_location("validate_prepared_model", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_context_chunks_count_as_speech():
    validator = _load()
    full_context = {"chunks": [{"segments": [{"start": 0.0, "end": 5.26, "speaker": "S01",
                                               "text": "Hello, this is a local speech recognition test."}]}]}
    assert validator.moss_has_speech(full_context)
    assert validator.moss_has_speech({"segments": [{"speaker": "S01", "text": "x"}]})
    assert not validator.moss_has_speech({"chunks": [{"segments": [{"speaker": "S01", "text": ""}]}]})
    assert not validator.moss_has_speech({"chunks": [], "segments": None})
