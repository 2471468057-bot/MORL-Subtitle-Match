import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_stage_modules_are_available_and_compatibility_api_is_published():
    command = [
        sys.executable,
        "-c",
        (
            "import twobyteasr.cache, subtitle_core; "
            "required=('stable_digest','run_cached_stage','transcribe_qwen_reference',"
            "'group_subtitles','normalize_cue_times','render_srt'); "
            "assert all(hasattr(subtitle_core, name) for name in required)"
        ),
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_pipeline_legacy_configuration_is_kept_on_compatibility_module():
    command = [
        sys.executable,
        "-c",
        (
            "import subtitle_core; "
            "required=('ASR_CONSENSUS_MIN_SIMILARITY','AUDIO_SAMPLE_RATE',"
            "'FIRERED_MODEL_DIR','FIRERED_SOURCE_DIR','HF_TOKEN',"
            "'MIN_SUBTITLE_SECONDS','QWEN_ASR_ALTERNATE_MIN_SIMILARITY',"
            "'QWEN_ASR_TEXT_ALIGNMENT_PAD_SECONDS','RUNTIME_OUTPUT_REVIEW_TRACK',"
            "'SCRIPT_DIR'); "
            "assert all(hasattr(subtitle_core, name) for name in required)"
        ),
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_main_runtime_dependencies_are_declared():
    requirements = (ROOT / "requirements-main.txt").read_text(encoding="utf-8")
    for package in (
        "qwen-asr",
        "pypinyin",
        "requests",
        "jieba",
        "speechbrain",
        "kaldiio",
        "kaldi-native-fbank",
        "PySide6",
        "QtAwesome",
    ):
        assert package in requirements


def test_correction_facade_reexports_split_implementations():
    command = [
        sys.executable,
        "-c",
        (
            "import twobyteasr.correction as facade; "
            "import twobyteasr.correction_safety as safety; "
            "import twobyteasr.domain_terms as terms; "
            "import twobyteasr.polishing as polishing; "
            "assert facade.apply_correction_edits is safety.apply_correction_edits; "
            "assert facade.discover_global_domain_term_mappings is terms.discover_global_domain_term_mappings; "
            "assert facade.polish_subtitles is polishing.polish_subtitles"
        ),
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_segmentation_facade_reexports_split_implementations():
    command = [
        sys.executable,
        "-c",
        (
            "import twobyteasr.segmentation as facade; "
            "import twobyteasr.cue_cleanup as cleanup; "
            "import twobyteasr.grouping as grouping; "
            "import twobyteasr.segmentation_alignment as alignment; "
            "assert facade.call_grouping_api is grouping.call_grouping_api; "
            "assert facade.merge_isolated_two_character_cues is cleanup.merge_isolated_two_character_cues; "
            "assert facade.segment_content_timeline is alignment.segment_content_timeline"
        ),
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_text_rules_are_published_through_compatibility_core():
    command = [
        sys.executable,
        "-c",
        (
            "import subtitle_core; import twobyteasr.text_rules as rules; "
            "assert subtitle_core.normalize_output_text is rules.normalize_output_text; "
            "assert subtitle_core.apply_editorial_segment_rules is rules.apply_editorial_segment_rules"
        ),
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_compatibility_facades_do_not_regrow_implementation_blocks():
    maximum_lines = {
        "twobyteasr/correction.py": 300,
        "twobyteasr/segmentation.py": 1850,
        "subtitle_core.py": 2500,
    }
    for relative_path, maximum in maximum_lines.items():
        line_count = len((ROOT / relative_path).read_text(encoding="utf-8").splitlines())
        assert line_count <= maximum, f"{relative_path} 已增长到 {line_count} 行"


def test_runtime_context_module_has_no_compatibility_core_import_cycle():
    tree = ast.parse((ROOT / "twobyteasr/runtime.py").read_text(encoding="utf-8"))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "subtitle_core" not in imported_modules | imported_from


def test_stage_modules_do_not_copy_mutable_runtime_globals():
    forbidden = (
        "RUNTIME_GAME_NAME",
        "RUNTIME_ENABLE_DOMAIN_TERMS",
        "RUNTIME_DISCOVERED_TERMS",
        "RUNTIME_OUTPUT_REVIEW_TRACK",
        "RUNTIME_FORCE_REFRESH_API_CACHE",
        "RUNTIME_FORCE_REFRESH_POLISH_CACHE",
        "RUNTIME_FORCE_REFRESH_GROUP_CACHE",
        "RUNTIME_CANCELLATION_TOKEN",
        "RUN_REVIEW_ITEMS",
    )
    stage_paths = (
        "twobyteasr/domain_terms.py",
        "twobyteasr/polishing.py",
        "twobyteasr/segmentation.py",
        "twobyteasr/output.py",
        "twobyteasr/timing.py",
        "twobyteasr/text_rules.py",
        "twobyteasr/pipeline_runtime.py",
    )
    for relative_path in stage_paths:
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        copied = [name for name in forbidden if name in source]
        assert not copied, f"{relative_path} 仍复制可变运行状态：{copied}"


def test_phonetic_similarity_is_available_in_production_import_order():
    command = [
        sys.executable,
        "-c",
        (
            "import subtitle_core; import twobyteasr.correction_safety as safety; "
            "assert safety.asr_consensus_similarity('测试', '测试') == 1.0; "
            "assert subtitle_core.phonetic_text('测试') == 'ceshi'"
        ),
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_stage_function_globals_resolve_in_production_import_order():
    command = [
        sys.executable,
        "-c",
        (
            "import builtins,dis,importlib,inspect,subtitle_core; "
            "mods=('twobyteasr.cache','twobyteasr.asr','twobyteasr.correction',"
            "'twobyteasr.correction_safety','twobyteasr.domain_terms','twobyteasr.polishing',"
            "'twobyteasr.segmentation','twobyteasr.segmentation_alignment',"
            "'twobyteasr.cue_cleanup','twobyteasr.grouping','twobyteasr.timing',"
            "'twobyteasr.output','twobyteasr.text_rules'); missing=[]; "
            "[(missing.append((mn,n,str(i.argval))) if "
            "i.opname in ('LOAD_GLOBAL','LOAD_NAME') and str(i.argval) not in vars(m) "
            "and not hasattr(builtins,str(i.argval)) and str(i.argval) != '_GeneratorContextManager' "
            "else None) for mn in mods for m in (importlib.import_module(mn),) "
            "for n,f in vars(m).items() if inspect.isfunction(f) and f.__module__==mn "
            "for i in dis.get_instructions(f)]; assert not missing, missing"
        ),
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
