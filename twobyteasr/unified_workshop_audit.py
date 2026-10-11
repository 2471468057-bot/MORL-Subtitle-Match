# SPDX-License-Identifier: GPL-3.0-only
"""Optional generator for the existing normal-startup unified acceptance window."""
from pathlib import Path
import copy


def steps(audit,window,output):
    from PySide6.QtCore import QSettings,QTimer,Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QMessageBox,QDialog,QPushButton,QTextBrowser,QLabel
    from .optional_models import component,model_path,readiness,_consent_path,confirm_license
    from .settings import load_runtime_settings
    from .license_documents import resolve_document
    from .unified_studio_audit import _sha
    output=Path(output).resolve()
    audit.check('workshop entered from normal initial Home',window.pages.currentWidget() is window.settings_scroll)
    audit.click(window.model_workshop_button);yield .3
    page=window.workshop_page
    audit.check('normal Home button opened actual workshop',window.pages.currentWidget() is page)
    role=next(b for b in page.tab_group.buttons() if b.property('role')=='primary')
    audit.click(role);yield .15
    audit.check('VibeVoice remains exactly one family card',sum(c.model.key=='vibevoice' for c in page._cards.values())==1)
    versions=[]
    for key in ('vibevoice_1_5b','vibevoice_7b'):
        other='vibevoice_7b' if key=='vibevoice_1_5b' else 'vibevoice_1_5b'
        audit.combo(page._cards['vibevoice'].version_combo,other);yield .15
        card=page._cards['vibevoice'];audit.combo(card.version_combo,key);yield .2
        spec=component(key);folder=model_path(key)
        files=[dict(name=name,exists=(folder/name).is_file(),actual_size=(folder/name).stat().st_size if (folder/name).is_file() else None,
            expected_size=spec['integrity_provenance']['files'][name]['size']) for name in spec['required_files']]
        audit.check('actual locked download files complete '+key,all(f['exists'] and f['actual_size']==f['expected_size'] for f in files),files)
        audit.check('actual family variant/download/adapter identities agree '+key,card.version_combo.currentData()==key
            and card.model.download_key==key and card.model.install_keys==(key,) and dict(card.model.adapter_bindings).get('primary')==key)
        audit.check('real viewed variant setting persisted '+key,QSettings('2ByteASR','ModelWorkshop').value('vibevoice_view_version')==key)
        state=page._model_state(card.model,'primary');before=copy.deepcopy(window.legacy.RUNTIME_SETTINGS)
        record=dict(key=key,files=files,folder=str(folder),state=state,actual_readiness=readiness(key),selected_before=before.get('models',{}).get('primary_asr_backend'))
        audit.shot('normal-workshop-'+key)
        if state in {'installed','selected'}:
            audit.click(card.action);yield .2
            if window.legacy.RUNTIME_SETTINGS.get('models',{}).get('primary_asr_backend')!=key:
                audit.click(card.action);yield .2
            saved=load_runtime_settings()[0]
            audit.check('actual available version selection and persisted backend agree '+key,
                saved.get('models',{}).get('primary_asr_backend')==key and window.primary_asr_backend.currentData()==key
                and page.runtime_settings.get('models',{}).get('primary_asr_backend')==key)
            record['selection_verified']=True
        elif state in {'inference_pending','load_failed'}:
            # Existing production deliberately requests a real sample here.
            # Cancel the native picker; never launch/retry blocked 7B inference.
            from PySide6.QtWidgets import QFileDialog
            original=QFileDialog.getOpenFileName;requests=[]
            def cancel_sample(*args,**kwargs):requests.append(str(args[1] if len(args)>1 else ''));return ('','')
            QFileDialog.getOpenFileName=cancel_sample
            try:audit.click(card.action)
            finally:QFileDialog.getOpenFileName=original
            yield .15
            audit.check('unverified inference sample cancellation keeps actual backend '+key,
                bool(requests) and window.legacy.RUNTIME_SETTINGS==before,requests)
            record.update(selection_verified=False,resource_or_inference_blocked=True,sample_picker_cancelled=True)
        else:
            audit.check('downloaded model has a truthful available or inference-blocked action '+key,False,record)
        versions.append(record)
    audit.result['normal_workshop']=dict(versions=versions,new_inference=False,large_model_inference_not_claimed=True)
    consent=_consent_path().resolve()
    from .test_isolation import isolation_root
    profile=isolation_root()
    audit.check('DiariZen consent only belongs to owned isolated profile',profile is not None and consent.is_relative_to(profile),str(consent))
    saved=consent.read_bytes() if consent.is_file() else None;consent.unlink(missing_ok=True)
    cancelled=[]
    def cancel_license():
        dialog=QApplication.activeModalWidget()
        if not isinstance(dialog,QMessageBox):return
        audit.shot('normal-diarizen-license-cancel',dialog)
        button=dialog.button(QMessageBox.Cancel)
        if button:QTest.mouseClick(button,Qt.LeftButton);cancelled.append(True)
        else:dialog.reject();cancelled.append(False)
    timer=QTimer();timer.timeout.connect(cancel_license);timer.start(100)
    try:
        # This runs while the parent audit is busy, avoiding nested generator
        # advancement. Only the real production licence dialog is cancelled.
        accepted=confirm_license(window)
        audit.check('real DiariZen license cancellation writes no consent',not accepted and cancelled==[True] and not consent.exists())
    finally:
        timer.stop()
        if saved is not None:consent.parent.mkdir(parents=True,exist_ok=True);consent.write_bytes(saved)
    audit.check('owned preexisting consent restored byte-for-byte',consent.read_bytes()==saved if saved is not None else not consent.exists())
    audit.click(page.workspace_navigation.buttons['recognition']);yield .2
    QTimer.singleShot(0,lambda:audit.click(window.app_settings_button))
    # SpringDialog.exec deliberately uses a guarded nonmodal window and a
    # nested event loop. Locate its real visible window, not Qt's modal slot.
    def settings_window():
        return next((w for w in QApplication.topLevelWidgets()
            if isinstance(w,QDialog) and w.objectName()=='applicationSettings' and w.isVisible()),None)
    yield lambda:settings_window() is not None
    settings=settings_window();navigation=settings.navigation
    item=navigation.item(navigation.count()-1);navigation.scrollToItem(item);yield .1
    QTest.mouseClick(navigation.viewport(),Qt.LeftButton,pos=navigation.visualItemRect(item).center());yield .2
    legal=settings.findChild(QLabel,'projectLicenseLabel')
    audit.check('About retains GPL3-only and exact historical boundary',legal is not None and 'GPL-3.0-only' in legal.text() and '0.2.6-test.3' in legal.text())
    audit.shot('normal-about-project-licenses',settings)
    for name,relative in (('openThirdPartyNotices','THIRD_PARTY_NOTICES.md'),('openProjectLicense','LICENSE'),('openCorrespondingSource','SOURCE_DELIVERY.md')):
        button=settings.findChild(QPushButton,name);audit.check('normal About original document entry '+name,button is not None)
        QTimer.singleShot(0,lambda b=button:audit.click(b))
        yield lambda:isinstance(QApplication.activeModalWidget(),QDialog) and QApplication.activeModalWidget().objectName()=='licenseDocumentDialog'
        document=QApplication.activeModalWidget();browser=document.findChild(QTextBrowser,'licenseDocumentText');location=document.findChild(QLabel,'licenseDocumentLocation')
        original=resolve_document(relative)
        audit.check('actual About local original document loaded '+relative,location.text()==relative and bool(browser.toPlainText().strip()),dict(path=str(original),sha256=_sha(original)))
        audit.shot('normal-about-original-'+name,document);document.reject();yield .15
    settings.reject();yield .2
