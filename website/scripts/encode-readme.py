"""Encode fixed-camera, exact 25 fps browser frames with one stable palette."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
RAW = Path(os.environ.get('README_RAW', ROOT/'tmp/readme-motion-daily-20260930/media'))
OUT = ROOT/'docs/assets/readme'
FFMPEG = ROOT/'tools/ffmpeg/bin/ffmpeg.exe'
names = ('speaker-tracks', 'word-split', 'candidate-review', 'live-clips', 'caption-effects')
records = []
for name in names:
    source = RAW/name
    capture = json.loads((source/'capture.json').read_text('utf-8'))
    pattern = 'render-%05d.png' if name == 'caption-effects' else 'frame-%05d.png'
    args = [str(FFMPEG), '-hide_banner', '-loglevel', 'error', '-y', '-framerate', '25', '-i', str(source/pattern)]
    # Global palette prevents color shimmer; opaque delta rectangles avoid
    # transparent frame disposal artifacts. Every delay is exactly 40 ms.
    graph = 'scale=1080:-2:flags=lanczos,split[a][b];[a]palettegen=stats_mode=full:reserve_transparent=0[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle'
    subprocess.run(args + ['-filter_complex', graph, '-loop', '0', '-gifflags', '+offsetting-transdiff', str(OUT/(name+'.gif'))], check=True)
    subprocess.run(args + ['-vf', 'scale=1080:-2:flags=lanczos', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(RAW/(name+'.mp4'))], check=True)
    records.append({'file':name+'.gif','type':capture['type'],'seconds':capture['duration'],'fps':25,'width':1080})
    print(name, (OUT/(name+'.gif')).stat().st_size, flush=True)
for source in RAW.glob('*.png'):
    if '-layout' not in source.stem:
        shutil.copyfile(source, OUT/source.name)
for file in sorted(OUT.glob('*.png')):
    records.append({'file':file.name,'type':'native window' if file.stem=='desktop-brand' else 'product interaction example / static frame'})
for record in records:
    file=OUT/record['file']
    record.update(bytes=file.stat().st_size, sha256=hashlib.sha256(file.read_bytes()).hexdigest())
(OUT/'manifest.json').write_text(json.dumps({'assets':records,'source':'website/product/readme.jsx; original product components; fixed camera',
    'not_claimed':['inference speed','recognition accuracy'],'gif_bytes':sum(r['bytes'] for r in records if r['file'].endswith('.gif'))},ensure_ascii=False,indent=2),'utf-8')
