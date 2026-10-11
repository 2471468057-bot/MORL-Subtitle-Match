# SPDX-License-Identifier: GPL-3.0-only
"""Explicit normal-entry acceptance; only guarded owned profiles can invoke it."""
from pathlib import Path
import copy
import json
import os


def steps(a, window, output, inputs):
    from PySide6.QtCore import QSettings,QTimer,Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QDialog,QComboBox,QFileDialog,QLabel,QTextBrowser,QMessageBox,QPushButton
    from .model_workshop import ModelCard,ModelVersionDialog,ModelTechnicalDialog
    from .optional_models import readiness,model_path,_consent_path
    from .settings import load_runtime_settings,project_settings_path
    from .unified_studio_audit import _sha
    output=Path(output)
    a.check('actual daily full bundle entry',Path(a.result['executable']).resolve()==Path(inputs['expected_executable']).resolve())
    a.check('normal initial Home',window.pages.currentWidget() is window.settings_scroll)
    before=copy.deepcopy(window.legacy.RUNTIME_SETTINGS)
    initial=before['models']['primary_asr_backend']
    a.result['initial_models']={k:before['models'].get(k) for k in ('primary_asr_backend','firered_asr_backend','qwen_asr_backend','speaker_source')}
    if inputs.get('restart_only'):
        a.check('applied small version restored after root launcher restart',initial=='vibevoice_1_5b' and window.primary_asr_backend.currentData()==initial)
    a.click(window.model_workshop_button);yield .3
    p=window.workshop_page
    a.check('one Vibe family card',sum(c.model.key=='vibevoice' for c in p._cards.values())==1)
    geometry=[]
    for key in ('vibevoice','diarizen','moss','firered_aed'):
        c=p._cards.get(key)
        if c is None and key=='firered_aed':c=p._cards.get('firered')
        a.check('actual shared ModelCard '+key,isinstance(c,ModelCard))
        a.check('no resident version/license controls '+key,not c.findChildren(QComboBox) and not any('可选模型许可' in x.text() for x in c.findChildren(QLabel)))
        a.check('shared right action parent '+key,c.action_host.isAncestorOf(c.action) and c.action_host.isAncestorOf(c.uninstall) and c._row.indexOf(c.action_host)==p._cards['moss']._row.indexOf(p._cards['moss'].action_host))
        geometry.append(dict(key=key,height=c.height(),width=c.width(),actions=c.action_host.geometry().getRect(),margins=c._root.contentsMargins().left()))
    a.result['card_geometry']=geometry
    a.shot('daily-model-cards')
    window.resize(1440,900);yield .25;a.shot('daily-model-cards-wide')
    window.resize(1200,800);yield .25;a.shot('daily-model-cards-1200')
    window.resize(1320,860);yield .2

    def dialog():
        return next((x for x in QApplication.topLevelWidgets() if isinstance(x,ModelVersionDialog) and x.isVisible()),None)
    def settings_state():
        settings=QSettings('2ByteASR','ModelWorkshop')
        return {k:settings.value(k) for k in settings.allKeys()}
    for intent in ('download','use'):
        snapshot=copy.deepcopy(window.legacy.RUNTIME_SETTINGS);ui_snapshot=settings_state()
        c=p._cards['vibevoice']
        QTimer.singleShot(0,lambda b=c.download if intent=='download' else c.action:a.click(b))
        yield lambda:dialog() is not None
        d=dialog();a.check('both independent versions in '+intent,set(d.choices)=={'vibevoice_1_5b','vibevoice_7b'})
        a.click(d.choices['vibevoice_7b']);yield .15
        a.check('radio does not write model or UI settings',window.legacy.RUNTIME_SETTINGS==snapshot and settings_state()==ui_snapshot)
        a.check('installed versions cannot download again',all(not d.download.isEnabled() for _ in (1,)) if d.complete[d.variant] else True)
        a.shot('daily-version-'+intent,d)
        a.click(d.cancel);yield .2
        a.check('cancel '+intent+' preserves all configuration',window.legacy.RUNTIME_SETTINGS==snapshot and settings_state()==ui_snapshot)
    for key in ('vibevoice_1_5b','vibevoice_7b','diarizen'):
        a.result.setdefault('readiness',{})[key]=dict(status=readiness(key),path=str(model_path(key)))
        a.check('stable model path '+key,'/tmp/' not in str(model_path(key)).replace('\\','/').lower())
    a.check('small ready and large remains truthfully blocked',readiness('vibevoice_1_5b')=='installed' and readiness('vibevoice_7b') in ('load_failed','inference_pending'))

    a.click(p._cards['vibevoice']);yield .15
    QTimer.singleShot(0,lambda:a.click(p.detail_docs))
    def tech():return next((x for x in window.findChildren(ModelTechnicalDialog) if x.isVisible()),None)
    yield lambda:tech() is not None
    t=tech();text='\n'.join(x.text() for x in t.findChildren(QLabel))+'\n'+'\n'.join(x.toPlainText() for x in t.findChildren(QTextBrowser))
    a.check('technical info has developer and version license chapters','1.5B' in text and '7B' in text and '许可' in text and ('Microsoft' in text or '微软' in text))
    a.shot('daily-vibevoice-technical');a.click(next(x for x in t.findChildren(QPushButton) if x.text()=='关闭'));yield .2
    a.click(p._cards['diarizen']);yield .15
    QTimer.singleShot(0,lambda:a.click(p.detail_docs));yield lambda:tech() is not None
    t=tech();text='\n'.join(x.text() for x in t.findChildren(QLabel))+'\n'+'\n'.join(x.toPlainText() for x in t.findChildren(QTextBrowser))
    a.check('Diari technical notice retains noncommercial restriction','非商用' in text or '非商业' in text or 'NonCommercial' in text)
    a.shot('daily-diarizen-technical');a.click(next(x for x in t.findChildren(QPushButton) if x.text()=='关闭'));yield .2

    # The owned profile contains its prior confirmed research-use receipt.
    consent=_consent_path().resolve()
    a.check('Diari research consent belongs to owned profile',consent.is_relative_to(output) and consent.is_file())
    primary=window.legacy.RUNTIME_SETTINGS['models']['primary_asr_backend']
    a.click(p._cards['diarizen']);yield .15;a.click(p._cards['diarizen'].action);yield .2
    a.check('Diari enabled independently of primary',window.legacy.RUNTIME_SETTINGS['models']['speaker_source']=='diarizen' and window.legacy.RUNTIME_SETTINGS['models']['primary_asr_backend']==primary)
    a.click(p._cards['diarizen'].action);yield .2
    a.check('Diari disabled without changing primary',window.legacy.RUNTIME_SETTINGS['models']['speaker_source']!='diarizen' and window.legacy.RUNTIME_SETTINGS['models']['primary_asr_backend']==primary)
    if inputs.get('restart_only'):return

    QTimer.singleShot(0,lambda:a.click(p._cards['vibevoice'].action));yield lambda:dialog() is not None
    d=dialog();a.click(d.choices['vibevoice_1_5b']);yield .1
    a.check('small use action actually available',d.use.isEnabled() and d.use.property('action')=='use')
    a.click(d.use);yield .3
    saved=load_runtime_settings()[0]
    a.check('accepted small selection persisted across actual Home and workshop',saved['models']['primary_asr_backend']=='vibevoice_1_5b' and window.primary_asr_backend.currentData()=='vibevoice_1_5b' and p.runtime_settings['models']['primary_asr_backend']=='vibevoice_1_5b')
    a.shot('daily-applied-small')
    a.click(p.workspace_navigation.buttons['recognition']);yield .3
    a.check('Home actual selected backend agrees',window.primary_asr_backend.currentData()=='vibevoice_1_5b')
    if not inputs.get('recognition') and not inputs.get('completed_project'):return
    # Use normal Home controls. Only this owned profile disables cloud stages;
    # actual user API configuration is never copied into evidence or altered.
    a.check('owned basic run cloud stages explicitly off',not window.ai_polish.isChecked() and not window.ai_grouping.isChecked())
    if inputs.get('completed_project'):
        project_path=Path(inputs['completed_project']).resolve()
        a.check('retained real inference project is an owned copy',project_path.is_relative_to(output) and project_path.is_file())
        a.result['recognition']=dict(retained_replay=True,new_inference=False,project=str(project_path))
        a.click(window.subtitle_studio_button);yield .2
        original=QFileDialog.getOpenFileName;QFileDialog.getOpenFileName=lambda *x,**k:(str(project_path),'project')
        try:a.click(a.page.project_import_button)
        finally:QFileDialog.getOpenFileName=original
        yield a.ready
    else:
        sample=Path(inputs['sample']).resolve();a.check('short real media is owned by this audit',sample.is_relative_to(output) and sample.is_file())
        original=QFileDialog.getOpenFileNames
        QFileDialog.getOpenFileNames=lambda *x,**k:([str(sample)],'media')
        try:a.click(window.choose_media_button)
        finally:QFileDialog.getOpenFileNames=original
        yield lambda:bool(window.media_paths)
        a.check('normal media chooser loaded actual short clip',list(map(str,window.media_paths))==[str(sample)])
        a.click(window.start_button);yield .3
        a.check('actual normal Home worker started',window.worker is not None and window._last_run_options is not None)
        yield (lambda:not window._run_in_progress and bool(window._completion_tasks),300)
        item,project=window._completion_tasks[0];project_path=Path(item.project_path)
        a.check('actual recognition delivered native project',bool(project and project.cues) and project_path.is_file(),dict(status=item.status,error=item.error,project=item.project_path,srt=item.srt_path))
        a.result['recognition']=dict(status=item.status,project=item.project_path,report=item.report_json_path,job_id=window._last_run_options.job_id,automatic_srt=item.srt_path or None,cue_count=len(project.cues),new_inference=True)
        a.shot('daily-small-recognition-result');a.click(window.open_studio_result_button);yield a.ready
    a.check('actual native recognition project entered Studio',Path(a.page.project_path).resolve()==project_path.resolve() and bool(a.page.project.cues))
    a.shot('daily-small-result-studio')
    from .studio_export_ui import SubtitleExportDialog
    QTimer.singleShot(0,lambda:a.click(a.page.studio_export_button))
    def export_dialog():return next((x for x in QApplication.topLevelWidgets() if isinstance(x,SubtitleExportDialog) and x.isVisible()),None)
    yield lambda:export_dialog() is not None
    d=export_dialog()
    for key,widget in d.format_checks.items():
        if widget.isChecked()!=(key=='srt'):a.click(widget)
    a.click(d.speaker_modes['both']);a.click(d.destination_modes['project']);yield .1
    folder=d.selected_destination()[0];a.check('Studio subtitle destination inside owned profile',folder.resolve().is_relative_to(output))
    a.shot('daily-studio-subtitle-export',d)
    acknowledged=[]
    def ack_export(box):
        # The normal export flow creates its information box after the first
        # dialog's nested event loop returns. Acknowledge only that real success
        # message; warning/error boxes remain failures of the normal GUI audit.
        if box.icon()!=QMessageBox.Icon.Information or box.windowTitle()!='导出字幕':return False
        files=list(folder.glob('*.srt'))
        a.check('actual export confirmation follows written artifacts',bool(files) and all(x.stat().st_size for x in files))
        acknowledged.append(box.text());a.shot('daily-studio-export-confirmation',box)
        QTest.mouseClick(box.button(QMessageBox.StandardButton.Ok),Qt.MouseButton.LeftButton)
        return True
    a.expected_modal_handler=ack_export
    a.click(next(x for x in d.findChildren(QPushButton) if x.text()=='导出字幕'))
    yield (lambda:bool(acknowledged),15)
    a.expected_modal_handler=None
    files=list(folder.glob('*.srt'))
    a.check('actual Studio combined and track SRT export completed',bool(acknowledged) and bool(files) and all(x.stat().st_size for x in files),dict(notices=acknowledged,files=list(map(str,files))))
    a.result['studio_subtitle_exports']=[dict(path=str(x),bytes=x.stat().st_size,sha256=_sha(x)) for x in files]
    a.write()
