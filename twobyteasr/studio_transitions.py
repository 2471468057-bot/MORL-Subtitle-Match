"""Saved clip transitions, sampled in project time without shifting the edit."""
from __future__ import annotations
import copy
import math
import uuid
from dataclasses import asdict, is_dataclass

KEY = 'clip_transitions'


def _data(value):
    return asdict(value) if is_dataclass(value) else dict(value)


def _graph(project):
    if isinstance(project, dict):
        return project
    return dict(video_tracks=[_data(t) for t in project.video_tracks],
                audio_tracks=[_data(t) for t in project.audio_tracks],
                media_pool=[_data(a) for a in project.media_pool],
                clip_transitions=copy.deepcopy(project.studio_state.get(KEY, [])))


def transition_records(project, media=None):
    records = (project.get(KEY,project.get('transitions',[])) if isinstance(project,dict)
               else project.studio_state.get(KEY,[]))
    return [dict(t) for t in records if isinstance(t, dict) and (media is None or t.get('media') == media)]


def _constraint(graph, item):
    media = item['media']
    tracks = graph.get(media + '_tracks', [])
    track = next((t for t in tracks if t['id'] == item['track_id']), None)
    if track is None:
        raise ValueError('转场关联片段已不存在')
    clips = {c['id']: c for c in track['clips']}
    left = clips.get(item.get('left_clip_id', ''))
    right = clips.get(item.get('right_clip_id', ''))
    edge = item.get('edge', 'seam')
    requested = max(1, int(item.get('duration_ms', 500)))
    if edge == 'seam':
        if left is None or right is None or left['timeline_out_ms'] != right['timeline_in_ms']:
            raise ValueError('请选择同轨相邻片段的接缝')
        assets = {a['asset_id']: a for a in graph['media_pool']}
        lrate = (left['source_out_ms']-left['source_in_ms']) / max(1, left['timeline_out_ms']-left['timeline_in_ms'])
        rrate = (right['source_out_ms']-right['source_in_ms']) / max(1, right['timeline_out_ms']-right['timeline_in_ms'])
        lhandle = max(0, assets[left['asset_id']]['duration_ms']-left['source_out_ms']) / max(.01, lrate)
        rhandle = right['source_in_ms'] / max(.01, rrate)
        available = min(left['timeline_out_ms']-left['timeline_in_ms'], right['timeline_out_ms']-right['timeline_in_ms'], int(lhandle*2), int(rhandle*2))
        duration = min(requested, available)
        if duration < 2:
            raise ValueError('接缝素材余量不足，请选择片段边缘淡入或淡出')
        seam = left['timeline_out_ms']
        start = seam-duration//2
        end = start+duration
    else:
        clip = right if edge == 'in' else left
        if clip is None or edge not in ('in', 'out'):
            raise ValueError('请选择片段首端或尾端')
        duration = min(requested, clip['timeline_out_ms']-clip['timeline_in_ms'])
        if duration <= 0:
            raise ValueError('片段时长为空')
        start = clip['timeline_in_ms'] if edge == 'in' else clip['timeline_out_ms']-duration
        end = start+duration
    linkage={}
    if media=='audio':
        linkage=dict(left_linked_video_clip_id=(left or {}).get('linked_video_clip_id',''),
                     right_linked_video_clip_id=(right or {}).get('linked_video_clip_id',''))
    return dict(item, **linkage, duration_ms=duration, start_ms=start, end_ms=end,
                type='cross_dissolve' if media == 'video' else 'equal_power')


def reconcile_transitions(project):
    graph = _graph(project)
    from .studio_edit_sequence import sequence_of
    lineage=sequence_of(project).segment_lineage
    records = []
    seen = set()
    for original in transition_records(graph):
        item=dict(original)
        # A razor preserves the parent ID on one child and records the other
        # child's ancestry. Keep terminal fades on the correct surviving end
        # and seam references on the adjacent descendants. Cross-track moves
        # similarly relocate the transition when both endpoint IDs move.
        tracks=graph.get(item.get('media','')+'_tracks',[])
        matches=[]
        for track in tracks:
            clips=track['clips']
            def descendants(key):
                identity=item.get(key,'')
                ancestor=item.get(key.replace('_clip_id','_linked_video_clip_id'),identity)
                return [c for c in clips if c['id']==identity or ancestor in lineage.get(c.get('linked_video_clip_id') or c['id'],[])]
            left=descendants('left_clip_id');right=descendants('right_clip_id')
            if item.get('edge')=='seam':
                matches.extend(dict(item,track_id=track['id'],left_clip_id=l['id'],right_clip_id=r['id'])
                    for l in left for r in right if l['timeline_out_ms']==r['timeline_in_ms'] and l['id']!=r['id'])
            elif item.get('edge')=='in' and right:
                first=min(right,key=lambda c:(c['timeline_in_ms'],c['id']))
                matches.append(dict(item,track_id=track['id'],right_clip_id=first['id']))
            elif item.get('edge')=='out' and left:
                last=max(left,key=lambda c:(c['timeline_out_ms'],c['id']))
                matches.append(dict(item,track_id=track['id'],left_clip_id=last['id']))
        # Do not choose an unrelated remote seam when descendants are ambiguous.
        matches.sort(key=lambda t:(t['track_id']!=item.get('track_id'),t.get('left_clip_id')!=item.get('left_clip_id'),t.get('right_clip_id')!=item.get('right_clip_id')))
        if not matches:continue
        try:
            result = _constraint(graph, matches[0])
        except (ValueError, KeyError, TypeError):
            continue
        key = (result['media'], result['track_id'], result.get('left_clip_id'), result.get('right_clip_id'), result['edge'])
        if key not in seen:
            records.append(result)
            seen.add(key)
    if records or KEY in project.studio_state:
        project.studio_state[KEY] = records
    return records


def set_transition(project, media, track_id, left_clip_id='', right_clip_id='', edge='seam', duration_ms=500):
    if media not in ('video', 'audio'):
        raise ValueError('转场仅适用于视频或音频')
    graph = _graph(project)
    track = next((t for t in graph[media+'_tracks'] if t['id'] == track_id), None)
    if track is None or track.get('locked'):
        raise ValueError('目标轨道已锁定或不存在')
    key = (media, track_id, left_clip_id, right_clip_id, edge)
    records = transition_records(graph)
    existing = next((t for t in records if (t['media'],t['track_id'],t.get('left_clip_id',''),t.get('right_clip_id',''),t['edge']) == key), None)
    item = dict(id=existing['id'] if existing else 'transition-'+uuid.uuid4().hex[:12], media=media,
                track_id=track_id, left_clip_id=left_clip_id, right_clip_id=right_clip_id,
                edge=edge, duration_ms=duration_ms)
    item = _constraint(graph, item)
    records = [t for t in records if t.get('id') != item['id']]
    records.append(item)
    project.studio_state[KEY] = records
    return item


def transition_windows(project, media):
    """Clip-ID windows and envelopes consumed by both preview and export."""
    if not transition_records(project,media):return {}
    graph = _graph(project)
    clips = {(t['id'],c['id']): c for t in graph.get(media+'_tracks',[]) for c in t['clips']}
    counts={}
    for tid,cid in clips:counts[cid]=counts.get(cid,0)+1
    result = {}
    for raw in transition_records(graph, media):
        try:
            item = _constraint(graph, raw)
        except (ValueError, KeyError, TypeError):
            continue
        for role, key in (('out','left_clip_id'), ('in','right_clip_id')):
            clip = clips.get((item['track_id'],item.get(key,'')))
            if clip is None:
                continue
            identity=(item['track_id'],clip['id'])
            window = result.setdefault(identity, dict(clip, track_id=item['track_id'], envelopes=[]))
            if counts[clip['id']]==1:result[clip['id']]=window
            if item['edge'] == 'seam':
                start = min(window['timeline_in_ms'], item['start_ms'])
                end = max(window['timeline_out_ms'], item['end_ms'])
                rate = (clip['source_out_ms']-clip['source_in_ms'])/max(1,clip['timeline_out_ms']-clip['timeline_in_ms'])
                window.update(timeline_in_ms=start,timeline_out_ms=end,
                    source_in_ms=clip['source_in_ms']+round((start-clip['timeline_in_ms'])*rate),
                    source_out_ms=clip['source_out_ms']+round((end-clip['timeline_out_ms'])*rate))
            # SourceOver implements an opaque video dissolve by retaining the
            # outgoing frame and fading the incoming frame above it. Audio has
            # two complementary, equal-power sampling envelopes.
            curve = 'equal_power' if media == 'audio' else 'linear'
            window['envelopes'].append(dict(start_ms=item['start_ms'],end_ms=item['end_ms'],
                role='hold' if media=='video' and role=='out' and item['edge']=='seam' else role,
                curve=curve,transition_id=item['id']))
    return result


def transition_gain(envelopes, timeline_ms):
    gain = 1.
    for item in envelopes:
        if item['role'] == 'hold':
            continue
        u = max(0., min(1., (float(timeline_ms)-item['start_ms'])/max(1,item['end_ms']-item['start_ms'])))
        if item['curve'] == 'equal_power':
            value = math.sin(u*math.pi/2) if item['role']=='in' else math.cos(u*math.pi/2)
        else:
            value = u if item['role']=='in' else 1-u
        gain *= value
    return gain


def transition_volume_expression(envelopes, *, origin_ms=0):
    factors=[]
    for item in envelopes:
        if item['role']=='hold':
            continue
        start=(item['start_ms']-origin_ms)/1000
        duration=(item['end_ms']-item['start_ms'])/1000
        u=f"clip((t-({start:.9f}))/{duration:.9f},0,1)"
        factors.append((f"sin(PI/2*{u})" if item['role']=='in' else f"cos(PI/2*{u})")
                       if item['curve']=='equal_power' else (u if item['role']=='in' else f"(1-{u})"))
    return '*'.join(factors) or '1'
