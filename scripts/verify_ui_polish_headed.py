"""Real-window check of the 2026-10-14 UI polish, 匹配文稿, CTC switch and language plans.

Starts the real app (source, or ``--exe`` for a frozen candidate) on a private
desktop with an isolated data folder and runs the ``ui-polish`` acceptance
scenario (``twobyteasr/ui_polish_audit.py``). The runner prepares, under
``--output``: a recognition report with long resource names, a Studio project
whose captions carry measured per-character words (recognition slips, a filler
line), the interface zoom, and optionally links to installed models
(``--models``; only the folders the checks need, read-only, removed after the
run) plus speech media for the Home 匹配文稿 run (``--media``). Offline; no AI.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
MODEL_FOLDERS = ('FireRedASR2-AED', 'FireRedVAD', 'spkrec-ecapa-voxceleb', 'MOSS-Transcribe-Diarize',
                 'Qwen3-ASR-1.7B', 'Qwen3-ForcedAligner-0.6B', 'wav2vec2-large-xlsr-53-japanese')
JUNCTION = 0xA0000003


def _report(path: Path) -> Path:
    stages = [('统一 16k 音频采样时钟', 0.7, 'CPU+磁盘缓存'), ('MOSS 全局说话人与粗时间转写', 200, '独立 Python 3.12 + GPU'),
              ('FireRedASR2-AED 独立文字证据', 106, 'GPU'), ('Qwen3-ASR VAD短块复核', 85, 'GPU'),
              ('云端模型受限校对', 28.4, 'deepseek/deepseek-v4-pro · openai_compatible+本地安全裁决'),
              ('云端模型全文智能断句', 10.8, 'deepseek/deepseek-v4-pro · openai_compatible+说话人插话保护'),
              ('保存识别结果与工程', 1.1, '磁盘')]
    payload = {'media': {'name': '洛克王国直播.mp4', 'duration_seconds': 1419}, 'status': 'completed',
               'started_at': '2026-10-14T10:00:00', 'finished_at': '2026-10-14T10:08:00',
               'settings': {'models': {'primary_asr_backend': 'moss', 'firered_asr_backend': 'local',
                                       'qwen_asr_backend': 'local'}, 'switches': {}},
               'result': {'elapsed_seconds': 451, 'cue_count': 312, 'audio_seconds': 1419},
               'stages': [dict(index=i + 1, label=a, status='completed', elapsed_seconds=b, resource=c)
                          for i, (a, b, c) in enumerate(stages)]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), 'utf-8')
    return path


def _fixture(out: Path) -> Path:
    """Captions with measured per-character words, like FireRed evidence."""
    from twobyteasr.sample_project import ensure_sample_project, sample_root
    from twobyteasr.studio_project import project_from_runtime_cues, save_project
    ensure_sample_project()
    media = sample_root() / '范例影片.mp4'
    heard = [(400, '大家好欢迎回到直播间今天我们继续打至东国'), (5200, '派门在哪里呢我们先去找找看'),
             (8400, '嗯嗯那个就是说'), (10600, '好的出发吧')]
    cues, rows = [], {}
    for index, (start, text) in enumerate(heard, 1):
        words = [{'text': c, 'start_ms': start + k * 180, 'end_ms': start + k * 180 + 160} for k, c in enumerate(text)]
        rows[f'segment:{index}'] = {'text': text, 'words': words, 'final_timing_owner': 'FireRedASR2-AED'}
        cues.append(SimpleNamespace(cue_id=f'asr-{index}', start=start / 1000, end=(words[-1]['end_ms'] + 40) / 1000,
                                    text=text, speaker='S00'))
    project = project_from_runtime_cues(media, cues, asr_evidence=rows,
                                        generation_metadata={'language': {'code': 'zh', 'requested': 'zh'}})
    for cue in project.cues:
        cue.evidence_refs = ['segment:' + cue.id.split('-')[1]]
    path = out / 'projects' / 'match-fixture' / 'match-fixture.2byteproj'
    path.parent.mkdir(parents=True)
    return save_project(project, path)


def _link_models(source: Path, model_root: Path) -> list[Path]:
    import subprocess
    links = []
    for name in MODEL_FOLDERS:
        target, link = source / name, model_root / name
        if target.is_dir() and not link.exists():
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)], check=True, capture_output=True)
            links.append(link)
    return links


def _runtime_shim(real_python: Path, target: Path) -> Path:
    """A small venv inside the isolated root that imports a real runtime's packages.

    Under ``TWOBYTEASR_TEST_ROOT`` the runtime registry only accepts
    interpreters inside the root (a frozen build has no other fallback), and
    copying a multi-GB runtime is not needed for a read-only check. The venv
    uses the runtime's own base Python; one ``.pth`` line adds the runtime's
    site-packages (its own ``.pth`` files included).
    """
    import subprocess
    real_root = real_python.resolve().parent.parent
    config = (real_root / 'pyvenv.cfg').read_text('utf-8')
    home = next(line.split('=', 1)[1].strip() for line in config.splitlines()
                if line.split('=', 1)[0].strip() == 'home')
    subprocess.run([str(Path(home) / 'python.exe'), '-m', 'venv', '--without-pip', str(target)], check=True,
                   capture_output=True)
    shim = target / 'Lib' / 'site-packages' / '_real_runtime.pth'
    shim.write_text(f"import site; site.addsitedir(r'{real_root / 'Lib' / 'site-packages'}')\n", 'utf-8')
    return target / 'Scripts' / 'python.exe'


def _unlink(links) -> None:
    for link in links:
        try:
            if getattr(os.lstat(link), 'st_reparse_tag', 0) == JUNCTION:
                os.rmdir(link)  # the link only; the installed model is untouched
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--zoom', type=int, default=110)
    parser.add_argument('--theme', default='slate')
    parser.add_argument('--models', type=Path, help='folder with installed models to link (read-only)')
    parser.add_argument('--main-python', type=Path, help='registered main runtime python (Home 匹配文稿, source runs)')
    parser.add_argument('--main-runtime', type=Path,
                        help='real main runtime python, used through a small venv inside the isolated root '
                             '(needed by frozen builds)')
    parser.add_argument('--moss-python', type=Path, help='MOSS runtime python (language plans)')
    parser.add_argument('--media', type=Path, help='speech media whose words match the scenario script')
    parser.add_argument('--timeout', type=int, default=900)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT / 'tmp'):
        raise ValueError('A fresh output directory under the repository tmp/ is required')
    out.mkdir(parents=True)
    profile = out / 'profile'
    os.environ['TWOBYTEASR_TEST_ROOT'] = str(profile)
    sys.path.insert(0, str(ROOT))
    from twobyteasr.test_isolation import install
    install()
    from twobyteasr import ui_zoom
    ui_zoom.set_zoom_percent(args.zoom)   # isolated QSettings shared with the app (same test root)
    report = _report(out / 'fixture_字幕任务报告.json')
    fixture = _fixture(out)
    links = _link_models(args.models.resolve(), Path(os.environ['2BYTEASR_MODEL_ROOT'])) if args.models else []
    try:
        local, roaming = out / 'local', out / 'roaming'
        local.mkdir()
        roaming.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith('TWOBYTEASR_')}
        env.update(LOCALAPPDATA=str(local), APPDATA=str(roaming), **{'2BYTEASR_USER_DATA_ROOT': str(local)},
                   TWOBYTEASR_STARTUP_PROJECT=str(fixture), TWOBYTEASR_TEST_ROOT=str(profile), PYTHONUTF8='1',
                   HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONFAULTHANDLER='1',
                   TWOBYTEASR_ACCEPTANCE_DIR=str(out), TWOBYTEASR_ACCEPTANCE_SCENARIO='ui-polish',
                   TWOBYTEASR_INVOKER_CWD=str(ROOT), TWOBYTEASR_SKIP_FIRST_RUN_WIZARD='1', QT_QPA_PLATFORM='windows',
                   NO_PROXY='127.0.0.1,localhost', HTTP_PROXY='http://127.0.0.1:9', HTTPS_PROXY='http://127.0.0.1:9',
                   TWOBYTEASR_UI_POLISH_REPORT=str(report), TWOBYTEASR_UI_POLISH_THEME=args.theme)
        if args.media:
            env['TWOBYTEASR_UI_POLISH_MEDIA'] = str(args.media.resolve())
        if args.main_runtime:
            env['TWOBYTEASR_MAIN_PYTHON'] = str(_runtime_shim(args.main_runtime, profile / 'runtime-shim' / 'main'))
        elif args.main_python:
            env['TWOBYTEASR_MAIN_PYTHON'] = str(args.main_python)
        if args.moss_python:
            env['TWOBYTEASR_MOSS_PYTHON'] = str(args.moss_python)
        command = [str(args.exe.resolve())] if args.exe else [sys.executable, '-B', str(ROOT / 'quick_start.py')]
        from isolated_windows_desktop import run_on_desktop
        code = run_on_desktop(command, cwd=ROOT, env=env, output=out / 'process', timeout=args.timeout)
    finally:
        _unlink(links)
    path = out / 'result.json'
    result = json.loads(path.read_text('utf-8')) if path.exists() else dict(passed=False, error='no result')
    summary = dict(passed=bool(result.get('passed')) and code == 0 and bool(result.get('gui_shutdown')), exit=code,
                   shutdown=result.get('gui_shutdown'), executable=result.get('executable'),
                   checks=[(c['name'], c['passed']) for c in result.get('checks', [])],
                   skipped=result.get('skipped'), errors=[e[-800:] for e in result.get('errors', [])])
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
