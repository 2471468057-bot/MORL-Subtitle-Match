import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from twobyteasr.nemotron_diarization import activity_assignment,merge


def test_activity_overlap_unknown_and_word_boundaries_preserve_short_reply():
    values=np.zeros((300,8),np.float32)
    values[:100,0]=.95;values[100:160,1]=.95;values[160:240,:2]=.9
    rows=[dict(start=0,end=3,text='你好回话重叠尾声',tokens=[
        dict(start=0,end=1,text='你好'),dict(start=1,end=1.6,text='回话'),
        dict(start=1.6,end=2.4,text='重叠'),dict(start=2.4,end=3,text='尾声')])]
    result=merge(rows,values,.01)
    assert [r['speaker'] for r in result]==['NEMO_01','NEMO_02','UNASSIGNED','UNASSIGNED']
    assert ''.join(r['text'] for r in result)==rows[0]['text']
    assert result[2]['speaker_evidence']['overlap'] and result[2]['speaker_evidence']['needs_confirmation']
    assert result[-1]['speaker_evidence']['needs_confirmation']
    coarse=merge([dict(start=0,end=2.4,text='一句换人但没有词时间')],values,.01)
    assert len(coarse)==1 and coarse[0]['speaker_evidence']['granularity']=='coarse_sentence'
    assert coarse[0]['speaker']=='UNASSIGNED'


@pytest.mark.parametrize('samples',[160,16679,16680,28304,28305,64000])
def test_stream_continuous_cache_logits_activation_and_tail(samples):
    import torch
    from twobyteasr.nemotron_stream import probabilities
    class Inputs(dict):
        def to(self,*a,**kw):return self
    class Processor:
        feature_extractor=SimpleNamespace(sampling_rate=16000,hop_length=160)
        num_samples_first_audio_chunk=16680;num_samples_per_audio_chunk=17040
        num_mel_frames_per_step=72;subsampling_factor=8
        def audio_chunk_start(self,cursor):return cursor*160-256
        def __call__(self,a,**kw):
            first=kw['is_first_audio_chunk'];last=kw.get('is_last_audio_chunk',False)
            frames=len(a)//160 if first else (len(a)-512)//160+1
            d=Inputs(input_features=torch.zeros(1,frames,128),attention_mask=torch.ones(1,frames,dtype=torch.bool))
            if not last:d['num_lookahead_frames']=4
            return d
    class Model:
        device='cpu';dtype=torch.float32
        def __init__(self):self.cache=None;self.calls=0
        def __call__(self,**kw):
            assert kw['speaker_cache'] is self.cache
            count=int(kw['attention_mask'].sum())-kw.get('num_lookahead_frames',0)*8
            logits=torch.full((1,count,8),-8.)
            logits[:,:,0:2]=2.
            self.cache=object();self.calls+=1
            return SimpleNamespace(logits=logits,speaker_cache=self.cache)
    model=Model();rows=list(probabilities(np.zeros(samples),Processor(),model,torch))
    assert rows[0][0]==0
    assert all(a+len(v)==b for (a,v),(b,_) in zip(rows,rows[1:]))
    result=np.concatenate([v for _,v in rows])
    assert len(result) in {samples//160,samples//160-1}
    assert np.all(result[:,:2]>.8) and np.all(result[:,2:]<.01)
    # Another media starts a fresh cache, not a saved speaker state.
    list(probabilities(np.zeros(160),Processor(),Model(),torch))


@pytest.mark.parametrize('text,token',[('3.5','35'),('-1','1'),('hello world','helloworld')])
def test_alignment_cannot_erase_signs_spaces_or_decimal(text,token):
    from twobyteasr.nemotron_diarization import merge
    row=dict(start=0,end=1,text=text,tokens=[dict(start=0,end=1,text=token)])
    values=np.zeros((100,8));values[:,0]=.95
    result=merge([row],values,.01)
    assert result[0]['text']==text
    assert result[0]['speaker_evidence']['granularity']=='coarse_sentence'


def test_too_short_and_cancellation_do_not_publish_frames():
    from twobyteasr.nemotron_stream import processor_chunks,probabilities
    processor=SimpleNamespace(feature_extractor=SimpleNamespace(sampling_rate=16000,hop_length=160))
    for n in [0,159]:
        with pytest.raises(ValueError):list(processor_chunks(np.zeros(n),processor))


def test_new_speaker_policy_save_reopen_grouping_export(tmp_path):
    from twobyteasr.studio_project import SubtitleProject,StudioMedia,StudioSpeaker,StudioCue
    from twobyteasr.speaker_organization import apply_new_project_policy,organize
    from twobyteasr.studio_subtitle_export import export_subtitle_artifacts,SubtitleExportOptions
    p=SubtitleProject(media=StudioMedia('fixture.mp4',duration_ms=3000),
        speakers=[StudioSpeaker('NEMO_01'),StudioSpeaker('NEMO_02')],
        cues=[StudioCue('a',0,1000,'主声','NEMO_01'),StudioCue('b',1000,1600,'回话','NEMO_02')])
    p.generation_metadata['speaker_recovery']={'processing':{'mode':'nemotron'},'raw_segments':[]}
    apply_new_project_policy(p)
    assert len(p.speakers)==2 and not any(s.is_host for s in p.speakers)
    original=p.to_dict();grouped=organize(p,{'NEMO_02'},'background')
    reopened=SubtitleProject.from_dict(json.loads(json.dumps(grouped.to_dict())))
    restored=organize(reopened,{'GAME_BACKGROUND'},'restore')
    assert [(c.text,c.speaker_id) for c in restored.cues]==[(c['text'],c['speaker_id']) for c in original['cues']]
    artifacts=export_subtitle_artifacts(restored,tmp_path,'nemotron-contract',SubtitleExportOptions(frozenset({'srt','json'}),'both'))
    assert len(artifacts)==6 and all(a.path.is_file() for a in artifacts)
    lane=[a for a in artifacts if a.format=='srt' and a.speaker_id=='NEMO_02'][0]
    assert '回话' in lane.path.read_text('utf8') and '主声' not in lane.path.read_text('utf8')
    assert restored.generation_metadata['speaker_organization']['cue_origins']['b']=='NEMO_02'


def test_workshop_new_entries_actions_and_optional_role(monkeypatch,tmp_path):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QSettings
    from twobyteasr.model_workshop import ModelWorkshopPage,MODELS
    from twobyteasr.ui import ASR_API_PRESETS
    app=QApplication.instance() or QApplication([])
    page=ModelWorkshopPage(Path(__file__).parents[1],{'models':{}})
    page._set_role('speaker')
    assert not page._cards['nemotron'].isHidden()
    assert page._cards['moss'].isHidden()
    page._installed.add('nemotron')
    monkeypatch.setattr('twobyteasr.environment.fast_preflight',lambda role:SimpleNamespace(ok=True))
    monkeypatch.setattr('twobyteasr.runtime_registry.resolve_runtime_python',lambda role:str(tmp_path/'Scripts/python.exe'))
    ready=tmp_path/'nemotron-readiness.json'
    ready.write_text(json.dumps(dict(model_loaded=True,forward_verified=True,inference_verified=False)),'utf8')
    assert page._model_state(next(m for m in MODELS if m.key=='nemotron'))=='inference_pending'
    ready.write_text(json.dumps(dict(model_loaded=True,forward_verified=True,inference_verified=True)),'utf8')
    selected_speakers=[]
    def apply(role,value):
        selected_speakers.append((role,value))
        page.runtime_settings['models']['speaker_source']=value
    page.backend_requested.connect(apply)
    page._perform_action('nemotron')
    assert selected_speakers[-1]==('speaker','nemotron')
    page._select_model('nemotron')
    assert len(selected_speakers)==1
    page._perform_action('nemotron')
    assert selected_speakers[-1]==('speaker','single')
    assert QSettings('2ByteASR','2ByteASR').value('recognition/speaker_source_v2') is None
    page._set_role('api');selected=[]
    page.api_preset_requested.connect(selected.append)
    monkeypatch.setattr('twobyteasr.llm_config.read_asr_api_key',lambda *a:('','test'))
    for key in ['spark_asr_v2','qwen31_flash','qwen31_filetrans']:
        assert not page._cards[key].isHidden()
        page._perform_action(key)
        assert selected[-1]==key
    assert ASR_API_PRESETS['qwen_filetrans']['model'].startswith('qwen-audio-3.0-')
    page.deleteLater();app.processEvents()
