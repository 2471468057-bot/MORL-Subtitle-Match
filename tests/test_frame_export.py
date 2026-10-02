from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from twobyteasr.frame_export import save_project_frame,safe_frame_name
from twobyteasr.studio_project import SubtitleProject,StudioMedia,StudioCue
from twobyteasr.video_export import capture_video_graph
from twobyteasr.export_timeline import export_project_snapshot
from twobyteasr.processes import run_hidden_subprocess

FFMPEG=Path(__file__).resolve().parents[1]/'tools/ffmpeg/bin/ffmpeg.exe'


def test_exact_frame_unique_outputs_and_caption_option(tmp_path):
    app=QApplication.instance() or QApplication([])
    media=tmp_path/'frames.mkv'
    run_hidden_subprocess([str(FFMPEG),'-v','error','-f','lavfi','-i','testsrc2=s=640x360:r=25:d=2',
        '-c:v','ffv1',str(media)],check=True,timeout=20,purpose='frame export integration fixture')
    p=SubtitleProject(media=StudioMedia(str(media),duration_ms=2000,width=640,height=360),
        cues=[StudioCue('a',400,950,'保存指定帧')]);p.validate()
    frozen=export_project_snapshot(p);graph=capture_video_graph(p)
    a=save_project_frame(frozen,graph,777,tmp_path,'CON',subtitles=False,ffmpeg=FFMPEG)
    b=save_project_frame(frozen,graph,777,tmp_path,'CON',subtitles=True,ffmpeg=FFMPEG)
    assert a['decode'][0]['frame_seconds']<=.777<a['decode'][0]['next_seconds']
    assert a['path']!=b['path'] and (a['width'],a['height'])==(640,360)
    assert QImage(a['path'])!=QImage(b['path'])
    assert QImage(a['path']).width()==640
    with pytest.raises(ValueError):save_project_frame(frozen,graph,2000,tmp_path,'end',ffmpeg=FFMPEG)
    with pytest.raises(OSError):save_project_frame(frozen,graph,100,tmp_path/'missing','bad',ffmpeg=FFMPEG)
    assert safe_frame_name('a:b?',777).startswith('a_b_')


def test_frame_composes_layers_visibility_and_trim_rate(tmp_path):
    from twobyteasr.studio_project import VideoTransform
    from twobyteasr.studio_media_pool import add_media_asset,create_video_track,add_video_clip
    app=QApplication.instance() or QApplication([])
    paths=[]
    for color in ('red','blue','lime'):
        path=tmp_path/(color+'.mkv')
        run_hidden_subprocess([str(FFMPEG),'-v','error','-f','lavfi','-i',
            f'color={color}:s=320x180:r=25:d=2','-c:v','ffv1',str(path)],check=True,timeout=20,purpose='frame layer fixture')
        paths.append(path)
    p=SubtitleProject(media=StudioMedia(str(paths[0]),duration_ms=2000,width=320,height=180));p.validate()
    for i,path in enumerate(paths[1:]):
        asset=add_media_asset(p,path,duration_ms=2000,video_metadata={'has_video':True,'width':320,'height':180})
        track=create_video_track(p,f'V{i+2}')
        clip=add_video_clip(p,track.id,asset.asset_id,source_in_ms=200,source_out_ms=1800,timeline_in_ms=400)
        clip.playback_rate=2.;clip.timeline_out_ms=1200
        clip.transform=VideoTransform(scale_x=.5,scale_y=.5,position_x=.25 if i==0 else .75)
        track.enabled=i==0
    result=save_project_frame(export_project_snapshot(p),capture_video_graph(p),500,tmp_path,'layers',subtitles=False,extension='jpg',ffmpeg=FFMPEG)
    image=QImage(result['path'])
    assert result['path'].endswith('.jpg') and len(result['decode'])==2
    assert abs(result['decode'][1]['source_seconds']-.4)<1e-9
    assert image.pixelColor(80,90).blue()>230
    assert image.pixelColor(240,90).red()>230
