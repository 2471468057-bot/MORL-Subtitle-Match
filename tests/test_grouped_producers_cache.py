"""Validated local/mixed output reuses cache without claiming AI origin."""
import json
import pytest


@pytest.mark.parametrize('origin', ['ai','mixed','local_fast'])
def test_validated_group_cache_preserves_actual_producer(tmp_path, origin):
    import subtitle_core as core
    from twobyteasr.cache import run_cached_stage
    from twobyteasr.runtime import RuntimeContext, activate_runtime_context
    from twobyteasr.asr_provider_snapshot import GroupedBatchResult
    root = tmp_path/'cache'
    root.mkdir()
    cache = {'identity':{'sha256':'input'}, 'cache_dir':str(root)}
    dependency = {'segments':[{'id':1,'speaker':'S01','text':'你好世界'}]}
    called = []
    def produce():
        called.append(1)
        return GroupedBatchResult([core.SubtitleCue(1,0,1,'你好世界',speaker='S01')], origin=origin, validated=True)
    with activate_runtime_context(RuntimeContext(), legacy=core):
        first = run_cached_stage('grouped',cache,produce,encoder=core.serialize_cues,
            decoder=core.deserialize_cues,extra_signature=dependency)
        second = run_cached_stage('grouped',cache,produce,encoder=core.serialize_cues,
            decoder=core.deserialize_cues,extra_signature=dependency)
    assert called == [1]
    assert first.origin == second.origin == origin
    assert second.validated and second.cache_hit
    assert second[0].text == '你好世界'
    files = list(root.glob('*.json'))
    assert len(files)==1
    assert json.loads(files[0].read_text('utf8'))['producer']==origin


@pytest.mark.parametrize('origin,validated,text', [('fallback',True,'你好世界'),('mixed',False,'你好世界'),('mixed',True,'擅自改字')])
def test_fallback_unvalidated_or_changed_group_result_is_not_cached(tmp_path,origin,validated,text):
    import subtitle_core as core
    from twobyteasr.cache import run_cached_stage
    from twobyteasr.runtime import RuntimeContext, activate_runtime_context
    from twobyteasr.asr_provider_snapshot import GroupedBatchResult
    root = tmp_path/'cache'
    root.mkdir()
    cache = {'identity':{'sha256':'input'}, 'cache_dir':str(root)}
    with activate_runtime_context(RuntimeContext(), legacy=core):
        run_cached_stage('grouped',cache,
            lambda:GroupedBatchResult([core.SubtitleCue(1,0,1,text,speaker='S01')],origin=origin,validated=validated),
            encoder=core.serialize_cues,decoder=core.deserialize_cues,
            extra_signature={'segments':[{'id':1,'speaker':'S01','text':'你好世界'}]})
    assert not list(root.glob('*.json'))
