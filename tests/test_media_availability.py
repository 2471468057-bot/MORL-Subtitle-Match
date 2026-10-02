"""Real worker cancellation and project-edit preservation for offline media."""
import copy
import multiprocessing
import os
import time
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QApplication

from twobyteasr.media_availability import apply_availability, export_sources, probe_sources, require_available
from twobyteasr.studio_edit_sequence import sequence_of
from twobyteasr.studio_media_commands import media_graph_command
from twobyteasr.studio_media_pool import relink_media_asset
from twobyteasr.studio_project import StudioMedia, StudioCue, SubtitleProject


def test_real_probe_recovers_stale_flags_and_distinguishes_corrupt_media(tmp_path):
    valid = tmp_path/'readable.bin'
    valid.write_bytes(b'not a media stream')
    missing = str(tmp_path/'missing.mp4')
    result = probe_sources([str(valid), missing])
    assert result[str(valid)]['status'] == 'available'
    assert result[missing]['status'] == 'missing'
    decoded = probe_sources([str(valid)], decode=True, timeout=6)
    assert decoded[str(valid)]['status'] == 'decode_failed'


def test_timeout_and_cancel_reap_the_owned_probe_process(tmp_path):
    source = tmp_path/'readable'
    source.write_bytes(b'a')
    baseline = {p.pid for p in multiprocessing.active_children()}
    started = time.monotonic()
    result = probe_sources([str(source)], timeout=.001)
    assert result[str(source)]['status'] == 'timeout'
    assert time.monotonic() - started < 3
    deadline = time.monotonic() + .03
    with pytest.raises(InterruptedError):
        probe_sources([str(source)], cancel_check=lambda: time.monotonic() > deadline)
    assert {p.pid for p in multiprocessing.active_children()} == baseline


def test_relink_undo_keeps_trims_tracks_cues_and_rebinds_primary_paths(tmp_path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path/'old.mp4'
    p = SubtitleProject(media=StudioMedia(path=str(source), duration_ms=5000, width=1920, height=1080),
                        cues=[StudioCue('cue', 1000, 2000, '编辑后的字幕')])
    p.validate()
    seq = sequence_of(p)
    seq.segments[0].source_in_ms = 1000
    seq.segments[0].source_out_ms = 4000
    before_tracks = copy.deepcopy((p.video_tracks, p.audio_tracks, p.cues))
    asset_id = p.media_pool[0].asset_id
    apply_availability(p, {str(source):dict(path=str(source), status='missing', reason='文件不存在')})
    stack = QUndoStack()
    replacement = str(tmp_path/'new.mp4')
    stack.push(media_graph_command(p, '重新链接', lambda w: relink_media_asset(w, asset_id, replacement)))
    assert p.media.path == replacement and seq.source_path == replacement
    assert seq.segments[0].source_path == replacement
    assert (seq.segments[0].source_in_ms, seq.segments[0].source_out_ms) == (1000, 4000)
    assert (p.video_tracks, p.audio_tracks, p.cues) == before_tracks
    assert not p.media_pool[0].offline
    # Late results for the old path cannot mark the replacement offline.
    apply_availability(p, {str(source):dict(path=str(source), status='missing', reason='文件不存在')})
    assert not p.media_pool[0].offline
    stack.undo()
    assert p.media.path == str(source) and seq.segments[0].source_path == str(source)
    assert p.media_pool[0].offline
    stack.redo()
    assert p.media.path == replacement


def test_export_rejects_missing_asset_in_range_with_relink_message():
    graph = dict(media_pool=[dict(asset_id='a', canonical_source='missing.mp4')],
                 video_tracks=[dict(clips=[dict(asset_id='a', timeline_in_ms=500, timeline_out_ms=1500)])])
    assert export_sources(graph, 0, 500) == []
    assert export_sources(graph, 500, 1000) == ['missing.mp4']
    with pytest.raises(ValueError, match='重新链接'):
        require_available({'missing.mp4':dict(path='missing.mp4', status='missing', reason='文件不存在')})


def test_gap_clock_advances_after_seek_and_rejects_late_decoder():
    from twobyteasr.playback_clock import PlaybackClock
    clock = PlaybackClock()
    old = clock.begin_seek(5000).playback_generation
    snapshot = clock.begin_unattached_position(6000, paused=False)
    assert not snapshot.exact_seek_pending and not snapshot.seeking
    assert clock.presentation_position_ms(elapsed_ms=500) >= 6500
    _, accepted, _ = clock.observe(5000, source_generation=old, actor_sequence=100,
                                  observed_monotonic_ts=time.monotonic(), playback_rate=1,
                                  paused=True, seeking=False)
    assert not accepted


def test_relink_updates_probe_metadata_but_keeps_clip_edits_and_undo(tmp_path):
    app=QApplication.instance() or QApplication([])
    p=SubtitleProject(media=StudioMedia(str(tmp_path/'old.mp4'),duration_ms=5000,width=1920,height=1080));p.validate()
    clip=p.video_tracks[0].clips[0];clip.source_in_ms=100;clip.source_out_ms=4100;clip.playback_rate=2
    clip.transform.rotation=17
    clip.timeline_out_ms=2000
    from twobyteasr.studio_project import sync_linked_av_contract
    sync_linked_av_contract(p)
    before=copy.deepcopy((p.media_pool,p.video_tracks,p.audio_tracks));asset=p.media_pool[0]
    stack=QUndoStack();stack.push(media_graph_command(p,'relink',lambda w:relink_media_asset(w,asset.asset_id,str(tmp_path/'new.mp4'),
        identity=dict(duration_ms=5500,width=1280,height=720,has_video=True,has_audio=True,video_codec='h264',audio_codec='aac'))))
    assert p.media.width==1280 and p.media.height==720 and p.media_pool[0].duration_ms==5500
    assert p.video_tracks==before[1] and p.audio_tracks==before[2]
    stack.undo();assert (p.media_pool,p.video_tracks,p.audio_tracks)==before


def test_primary_lane_marks_only_offline_segments_and_skips_their_thumbnails():
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter
    from twobyteasr.studio_edit_sequence import EditSequence, VideoSegment
    from twobyteasr.studio_video_track import paint_video_track
    from twobyteasr.timeline_theme import timeline_palette
    app=QApplication.instance() or QApplication([])
    image=QImage(1000,80,QImage.Format_ARGB32_Premultiplied);image.fill(0)
    labels=[];painted_sources=[]
    class Painter(QPainter):
        def drawText(self,*args):
            labels.append(str(args[-1]))
            return super().drawText(*args)
    class Filmstrip:
        def paint(self,painter,rect,path,*args):painted_sources.append(path)
    sequence=EditSequence(source_path='missing.mp4',source_duration_ms=2000,segments=[
        VideoSegment('missing','missing.mp4',0,1000,0,1000),
        VideoSegment('healthy','healthy.mp4',0,1000,1000,2000)])
    painter=Painter(image)
    try:
        paint_video_track(painter,sequence,timeline_palette(),QRectF(0,0,1000,70),230,1000,
            lambda ms:230+ms*.38,'',Filmstrip(),False,offline_sources={'missing.mp4'})
    finally:painter.end()
    assert '媒体脱机 · missing.mp4' in labels
    assert 'healthy.mp4' in labels and '媒体脱机 · healthy.mp4' not in labels
    assert painted_sources==['healthy.mp4']
