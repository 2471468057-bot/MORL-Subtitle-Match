import json,os,sys,threading,time
from pathlib import Path
import pytest
import psutil
from twobyteasr import advanced_renderer
from twobyteasr.processes import stop_process_tree

pytestmark=pytest.mark.skipif(os.name!='nt',reason='Windows renderer descendant cleanup')


def test_cancel_silent_renderer_stops_its_descendants(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'local'))
    children=[];original=advanced_renderer.popen_hidden_subprocess
    def launch(*args,**kwargs):
        process=original(*args,**kwargs);children.append(process);return process
    monkeypatch.setattr(advanced_renderer,'popen_hidden_subprocess',launch)
    pidfile=tmp_path/'child.json';cancel=threading.Event();sent=[]
    command=("import subprocess,sys,time,json;from pathlib import Path;"
        f"p=subprocess.Popen({[sys.executable,'-c','import time;time.sleep(30)']!r},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));"
        f"Path({str(pidfile)!r}).write_text(json.dumps(p.pid));print('ready',flush=True);time.sleep(30)")
    def request():sent.append(time.perf_counter());cancel.set()
    timer=threading.Timer(.25,request)
    rescue=threading.Timer(3,lambda:[stop_process_tree(p) for p in children])
    timer.start();rescue.start()
    try:
        with pytest.raises(InterruptedError):
            advanced_renderer._run_streaming_process([sys.executable,'-u','-c',command],cancelled=cancel.is_set,stall_timeout=30)
        assert time.perf_counter()-sent[0]<1.5
        assert children[0].poll() is not None
        if pidfile.exists():assert not psutil.pid_exists(json.loads(pidfile.read_text()))
    finally:
        timer.cancel();rescue.cancel()
        for process in children:stop_process_tree(process)
