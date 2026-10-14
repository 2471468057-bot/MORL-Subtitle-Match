"""Real-window check of the 2026-10-14 UI polish, 匹配文稿, CTC switch and language plans.

Runs only for ``TWOBYTEASR_ACCEPTANCE_SCENARIO=ui-polish`` (isolated data, from
``scripts/verify_ui_polish_headed.py``; source or frozen). Checks, with
screenshots in the output folder:

* geometry: 「最近」 chips inside their row, recognition-record stage rows tall
  enough for their pills and long resources ending in “…”, the play button
  with room in the transport pill, the save-frame icon clear of its menu
  separator, the punctuation/render buttons in the toolbar's button family;
* Studio 匹配文稿 on the runner's fixture project (captions with measured
  per-character words): text kept, order, measured words, review marks, undo
  and redo;
* language plans and the Japanese CTC switch (needs the runner's linked
  models; reported as skipped otherwise);
* Home 匹配文稿 with the real FireRedASR2-AED run when the runner passes speech
  media and the model (skipped otherwise).

Nothing here contacts the network or AI services.
"""
from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path

STUDIO_SCRIPT = '大家好，欢迎回到直播间\n今天我们继续打至冬国\n派蒙在哪里呢？\n我们先去找找看\n这一句根本没说\n好的，出发吧！\n'
HOME_SCRIPT = ('大家好，欢迎回到直播间\n今天我们继续玩洛克王国\n先去城堡找一下派蒙\n这句话视频里没有说\n'
               '好的，我们出发吧\n这里的风景真漂亮\n下一关要小心一点\n谢谢大家的支持\n')
RECENT = ['洛克王国：世界', '瓦罗兰特', '明日方舟终末地', '原神', '异环', '绝区零']


def start(window, output: Path):
    from PySide6.QtCore import QRect, QTimer
    from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPlainTextEdit, QTableWidget
    app = QApplication.instance()
    output.mkdir(parents=True, exist_ok=True)
    result = dict(checks=[], skipped=[], metrics={}, errors=[], passed=False, pid=os.getpid(),
                  executable=os.path.realpath(__import__('sys').executable))
    try:
        from .build_identity import load_build_identity
        result['identity'] = load_build_identity().to_dict()
    except Exception as exc:  # noqa: BLE001 - identity is informative only
        result['identity_error'] = str(exc)

    def check(name, ok, detail=None):
        result['checks'].append(dict(name=name, passed=bool(ok), detail=detail))

    def settle(ms=300):
        end = time.monotonic() + ms / 1000
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)

    def wait_for(predicate, timeout=40.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            app.processEvents()
            try:
                if predicate():
                    return True
            except Exception:  # noqa: BLE001 - keep polling
                pass
            time.sleep(0.05)
        return False

    def grab(widget, name, rect=None):
        try:
            (widget.grab(rect) if rect is not None else widget.grab()).save(str(output / f'{name}.png'))
        except Exception as exc:  # noqa: BLE001
            result['errors'].append(f'grab {name}: {exc!r}')

    def grab_around(widget, name, dx=24, dy=14):
        if widget is not None and widget.isVisible():
            parent = widget.parentWidget()
            grab(parent, name, widget.geometry().adjusted(-dx, -dy, dx, dy).intersected(parent.rect()))

    def modal(open_fn, drive, timeout=30.0):
        """Open a modal dialog and run ``drive(dialog)`` inside its loop."""
        before = {id(w) for w in app.topLevelWidgets()}
        state = {'done': False}

        def poll():
            if state['done']:
                return
            dialogs = [w for w in app.topLevelWidgets()
                       if isinstance(w, QDialog) and w.isVisible() and id(w) not in before]
            if not dialogs:
                QTimer.singleShot(200, poll)
                return
            state['done'] = True
            try:
                settle(500)
                drive(dialogs[-1])
            except Exception:  # noqa: BLE001
                result['errors'].append(traceback.format_exc())
                for dialog in dialogs:
                    QDialog.done(dialog, 0)

        QTimer.singleShot(800, poll)
        open_fn()
        wait_for(lambda: state['done'], timeout)
        settle(400)

    # ------------------------------------------------------------- home
    def step_home():
        window._content_quick_names = list(RECENT)
        window._sync_content_quick_picks()
        settle(500)
        picks = window.content_quick_picks
        chips = [c for c in picks.chips if c.isVisible()]
        grab(window.content_profile_card, 'home_content_card')
        check('最近 chips lie inside their row', bool(chips) and all(
            c.geometry().top() >= 0 and c.geometry().bottom() < picks.height() for c in chips),
            dict(row=picks.height(), chips=[c.geometry().getRect() for c in chips]))
        check('最近 caption and chips share a centre line', bool(chips) and abs(
            picks.caption.geometry().center().y() - chips[0].geometry().center().y()) <= 2)

    def step_history():
        from .recognition_history import RecognitionHistoryDetail, parse_recognition_report
        report = Path(os.environ['TWOBYTEASR_UI_POLISH_REPORT'])
        record = parse_recognition_report(report)

        def drive(dialog):
            detail = dialog.findChild(RecognitionHistoryDetail)
            table = detail.stage_table
            grab(table, 'history_stage_table')
            rows = [table.rowHeight(r) for r in range(table.rowCount())]
            pills = [table.cellWidget(r, c).findChild(QLabel) for r in range(table.rowCount()) for c in (1, 3)]
            check('stage rows are tall enough for their pills',
                  all(pill.height() >= pill.sizeHint().height() and table.rowHeight(r // 2) >= pill.height()
                      for r, pill in enumerate(pills)), rows)
            long = [p for p in pills if (p.property('fullText') or '') and p.text() != p.property('fullText')]
            check('long resources are elided with “…” and fit their pill',
                  bool(long) and all(p.text().endswith('…') and p.width() >= p.sizeHint().width() for p in long),
                  [(p.text(), p.width(), p.sizeHint().width()) for p in long])
            check('stage header has no box of its own', 'QHeaderView { background: transparent; border: 0; }'
                  in table.styleSheet())
            grab(dialog, 'history_detail_dialog')
            QDialog.done(dialog, 0)

        modal(lambda: window.history_page._show_detail(record), drive)

    # ----------------------------------------------------------- studio
    def open_fixture():
        fixture = os.environ['TWOBYTEASR_STARTUP_PROJECT']
        ready = {'v': False}
        window.open_studio_project(fixture, mode='edit', source='startup_audit',
                                   on_ready=lambda *a, **k: ready.__setitem__('v', True))
        wait_for(lambda: ready['v'], 60)
        settle(2500)
        return window._studio_page_instance

    def step_studio_chrome(page):
        play, bar = page.play_button, page.play_button.parentWidget()
        grab(window, 'studio_window')
        transport = QRect(play.geometry().left() - 80, 0, page.volume_slider.geometry().right() - play.geometry().left() + 120,
                          bar.height())
        grab(bar, 'zoom_transport', transport.intersected(bar.rect()))
        top, bottom = play.geometry().top(), bar.height() - play.geometry().bottom() - 1
        check('play button has room above and below in the transport pill', min(top, bottom) >= 5,
              dict(top=top, bottom=bottom, play=play.geometry().getRect()))
        check('play glyph is about half the circle', play.iconSize().width() <= play.width() * 0.6,
              (play.iconSize().width(), play.width()))
        frame = page.save_frame_button
        grab_around(frame, 'zoom_save_frame_button')
        check('save-frame button pads its menu segment', frame.property('splitMenu') is True
              and frame.width() >= frame.sizeHint().width())
        grab(page.punctuation_button.parentWidget(), 'studio_top_toolbar')
        check('标点 and 压制成片 use the toolbar button family',
              page.punctuation_button.property('buttonRole') == 'secondary'
              and page.studio_render_button.property('buttonRole') == 'secondary'
              and page.studio_render_button.property('emphasis') == 'accent',
              (page.punctuation_button.property('buttonRole'), page.studio_render_button.property('buttonRole')))

    def step_studio_match(page):
        from .cue_word_alignment import cue_words
        before = [(c.id, c.start_ms, c.end_ms, c.text) for c in page.project.cues]
        check('fixture captions carry measured words', all(cue_words(page.project, c)[0] for c in page.project.cues))
        button = page.studio_script_match_button
        check('匹配文稿 toolbar button visible', button.isVisible())
        grab_around(button, 'zoom_script_match_button', 30, 14)

        def drive(dialog):
            dialog.findChild(QPlainTextEdit, 'scriptMatchInput').setPlainText(STUDIO_SCRIPT)
            settle(200)
            dialog._run_preview()
            settle(500)
            grab(dialog, 'studio_match_dialog')
            table = dialog.findChild(QTableWidget, 'scriptMatchPreview')
            result['metrics']['studio_preview'] = [[table.item(r, c).text() for c in range(4)]
                                                   for r in range(table.rowCount())]
            dialog._accept_match()

        modal(button.click, drive)
        settle(1500)
        cues = page.project.cues
        lines = [line for line in STUDIO_SCRIPT.splitlines() if line.strip()]
        check('studio: one caption per line, text exactly as typed', [c.text for c in cues] == lines, [c.text for c in cues])
        check('studio: captions in order without overlap', all(a.end_ms <= b.start_ms for a, b in zip(cues, cues[1:])))
        words = [cue_words(page.project, c) for c in cues]
        heard = (0, 1, 2, 3, 5) if len(cues) == 6 else ()
        check('studio: heard lines keep measured words', bool(heard) and all(words[i][0] for i in heard),
              [w[1] for w in words])
        statuses = page.project.studio_state.get('cue_statuses', {})
        check('studio: the unheard line is marked for review', len(cues) == 6 and statuses.get(cues[4].id) == 'issue')
        grab(window, 'studio_after_match')
        page.undo_stack.undo()
        settle(800)
        check('studio: undo restores the captions',
              [(c.id, c.start_ms, c.end_ms, c.text) for c in page.project.cues] == before)
        page.undo_stack.redo()
        settle(800)
        check('studio: redo applies the script again', [c.text for c in page.project.cues] == lines)

    # ----------------------------------------------------- plans + CTC
    def step_plans():
        from . import ctc_alignment
        combo = window.recognition_mode_combo
        if combo.findData('japanese') < 0:
            check('language plans listed', False)
            return
        window._return_to_settings()
        settle(800)
        ctc_alignment.set_enabled(False, window.legacy.RUNTIME_SETTINGS)
        combo.setCurrentIndex(combo.findData('japanese'))
        settle(800)
        backends = (window.primary_asr_backend.currentData(), window.firered_asr_backend.currentData(),
                    window.qwen_asr_backend.currentData())
        if backends[0] != 'moss':
            result['skipped'].append(f'language plan backends: MOSS not selectable here {backends}')
        else:
            check('日语推荐: MOSS + Qwen3 aligner + Qwen3-ASR', backends == ('moss', 'qwen_aligner', 'local'), backends)
            check('日语推荐 shown while Japanese', combo.currentData() == 'japanese', combo.currentData())
            window.recognition_language.setCurrentIndex(window.recognition_language.findData('en'))
            settle(600)
            check('English shows 英语推荐', combo.currentData() == 'english', combo.currentData())
        check('日语推荐 sets Japanese', window.recognition_language.currentData() in {'ja', 'en'})
        check('日语推荐 turns CTC on', ctc_alignment.enabled())
        grab(window, 'home_plan')
        installed = window.workshop_page
        window._open_model_workshop()
        settle(2500)
        installed._set_role('timeline')
        settle(800)
        card = installed._cards.get('ja_ctc_aligner')
        if card is None or card.action.text() not in {'取消使用', '使用'}:
            result['skipped'].append(f'CTC card toggle: model not installed here ({card.action.text() if card else None})')
            return
        check('CTC card offers 取消使用 while on', card.action.text() == '取消使用' and card.action.isEnabled())
        card.action.click()
        settle(800)
        card = installed._cards['ja_ctc_aligner']
        check('CTC: clicking turns it off', card.action.text() == '使用' and not ctc_alignment.enabled())
        grab_around(card, 'ctc_card_off', 6, 6)
        card.action.click()
        settle(800)
        check('CTC: clicking again turns it on', installed._cards['ja_ctc_aligner'].action.text() == '取消使用'
              and ctc_alignment.enabled())

    # ------------------------------------------------------ home match
    def step_home_match():
        media = os.environ.get('TWOBYTEASR_UI_POLISH_MEDIA', '')
        from .home_script_match import timestamp_model_ready
        ready, reason = timestamp_model_ready()
        if not media or not ready:
            result['skipped'].append(f'home 匹配文稿: {reason or "no speech media"}')
            return
        studio = getattr(window, '_studio_page_instance', None)
        if studio is not None and getattr(studio, 'project', None) is not None:
            # Opening the result switches Studio's project; an edited fixture
            # would (rightly) ask whether to save first and block the run.
            studio.save()
            settle(500)
        window._return_to_settings()
        settle(800)
        window.media_paths = [media]
        state = {'error': None}

        def drive(dialog):
            dialog._script.setPlainText(HOME_SCRIPT)
            settle(300)
            grab(dialog, 'home_match_dialog')
            dialog._begin()

        # Never hang the run: after the deadline, record and close whatever
        # dialog is still waiting (the job's error text included).
        deadline = time.monotonic() + 420
        watchdog = QTimer()
        watchdog.setInterval(2000)

        def check_deadline():
            if time.monotonic() < deadline:
                return
            watchdog.stop()
            for widget in [w for w in app.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]:
                texts = [label.text() for label in widget.findChildren(QLabel) if label.text()]
                state['error'] = f'{type(widget).__name__}: ' + ' | '.join(texts)[-600:]
                grab(widget, 'home_match_stuck')
                QDialog.done(widget, 0)

        watchdog.timeout.connect(check_deadline)
        watchdog.start()
        started = time.monotonic()
        modal(window.script_match_button.click, drive, timeout=600)
        watchdog.stop()
        result['metrics']['home_match_seconds'] = round(time.monotonic() - started, 1)
        lines = [line for line in HOME_SCRIPT.splitlines() if line.strip()]
        ok = wait_for(lambda: window._studio_page_instance.project is not None
                      and [c.text for c in window._studio_page_instance.project.cues] == lines, 120)
        check('home: studio opened with one caption per script line', ok, state['error'])
        if not ok:
            return
        settle(2500)
        from .cue_word_alignment import cue_words
        project = window._studio_page_instance.project
        cues = project.cues
        result['metrics']['home_cues'] = [(c.text, c.start_ms, c.end_ms) for c in cues]
        check('home: only FireRedASR2-AED timestamps ran',
              project.generation_metadata.get('script_match', {}).get('timestamp_source') == 'FireRedASR2-AED')
        check('home: captions in order without overlap', all(a.end_ms <= b.start_ms for a, b in zip(cues, cues[1:])))
        check('home: spoken lines carry measured words', all(cue_words(project, c)[0] for i, c in enumerate(cues) if i != 3))
        check('home: the unspoken line is marked for review',
              project.studio_state.get('cue_statuses', {}).get(cues[3].id) == 'issue')
        grab(window, 'studio_after_home_match')

    def run_all():
        try:
            theme = os.environ.get('TWOBYTEASR_UI_POLISH_THEME', '')
            if theme:
                from .theme_manager import apply_theme
                apply_theme(theme, app)
            window.showMaximized()
            settle(1500)
            for dialog in [w for w in app.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]:
                QDialog.done(dialog, 0)
            for name, step in (('home', step_home), ('history', step_history)):
                try:
                    step()
                except Exception:  # noqa: BLE001
                    result['errors'].append(f'{name}: ' + traceback.format_exc())
            page = open_fixture()
            for name, step in (('studio chrome', step_studio_chrome), ('studio match', step_studio_match)):
                try:
                    step(page)
                except Exception:  # noqa: BLE001
                    result['errors'].append(f'{name}: ' + traceback.format_exc())
            for name, step in (('plans', step_plans), ('home match', step_home_match)):
                try:
                    step()
                except Exception:  # noqa: BLE001
                    result['errors'].append(f'{name}: ' + traceback.format_exc())
        except Exception:  # noqa: BLE001
            result['errors'].append(traceback.format_exc())
        result['passed'] = bool(result['checks']) and all(c['passed'] for c in result['checks']) and not result['errors']
        (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), 'utf-8')
        studio = getattr(window, '_studio_page_instance', None)
        if studio is not None and getattr(studio, 'project', None) is not None:
            try:
                studio.save()  # the copies under the output folder; no save prompt on close
            except Exception as exc:  # noqa: BLE001
                result['errors'].append(f'save before close: {exc!r}')
        window.close()
        QTimer.singleShot(500, app.quit)

    def shutdown():
        result['gui_shutdown'] = True
        (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), 'utf-8')

    app.aboutToQuit.connect(shutdown)
    QTimer.singleShot(2500, run_all)
