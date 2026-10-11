"""Ownership of disposable mpv pixels; never owns authored PNG/HTML assets."""
from pathlib import Path
import json
import os
import time
import threading
import re
import weakref
from contextlib import nullcontext


_workers_lock = threading.Lock()
_session_workers = {}


def register_overlay_worker(folder, worker):
    """Retain worker identity through page teardown, without retaining pages."""
    with _workers_lock:
        _session_workers.setdefault(str(Path(folder).resolve()), weakref.WeakSet()).add(worker)


def lease_overlay(path, producer):
    """An unavailable storage index must not prevent the native preview."""
    try:
        from .storage_service import register_cache, cache_lease
        register_cache(path, 'overlay', producer=producer)
        lease=cache_lease(path);lease.__enter__()
        return lease
    except Exception as exc:
        from .runtime_trace import GLOBAL_STUDIO_TRACE
        GLOBAL_STUDIO_TRACE.emit('OVERLAY_STORAGE',dict(stage='registration_failed',error=str(exc)[-300:]))
        return nullcontext()


def ensure_overlay_session(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / 'owner.json'
    if marker.is_file():
        return
    import psutil
    marker.write_text(json.dumps(dict(producer='mpv_overlay_session', schema=1,
        pid=os.getpid(), create_time=psutil.Process().create_time(),
        created_at=time.time(), state='active')), encoding='utf-8')


def retire_overlay_session(folder, *, workers=(), controller=None):
    """Reap only our session after IPC and buffer workers have relinquished it.

    No GUI waits for shutdown, and an owner marker left by a crash is enough
    for the storage scanner to distinguish disposable pixels from user art.
    """
    folder = Path(folder)
    def retire():
        deadline = time.monotonic() + 5
        while controller is not None and controller.running:
            if time.monotonic() >= deadline:
                return
            time.sleep(.02)
        key = str(folder.resolve())
        with _workers_lock:
            owned_workers = tuple(_session_workers.get(key, ()))
        for worker in set((*workers, *owned_workers)):
            if worker is not None and worker is not threading.current_thread():
                worker.join(timeout=max(0, deadline-time.monotonic()))
                if worker.is_alive():
                    return
        try:
            from .storage_service import safe_path
            if not safe_path(folder, (folder.parent,)):
                return
            marker = folder / 'owner.json'
            owner = json.loads(marker.read_text(encoding='utf-8'))
            if owner.get('producer') != 'mpv_overlay_session' or owner.get('pid') != os.getpid():
                return
            pixel_dirs = (folder / 'caption-prepared', folder / 'caption-scenes')
            for directory in (folder, *pixel_dirs):
                if directory != folder and not safe_path(directory, (folder,)):
                    continue
                for path in directory.glob('*.rgba'):
                    owned_name = re.fullmatch(
                        r'(?:overlay-\d+-(?:sync-)?[01]|web-overlay-\d+-[01]|native-[a-f0-9]+-\d+-[01]|[a-f0-9]{32})\.rgba', path.name)
                    if owned_name and safe_path(path, (folder,)):
                        path.unlink(missing_ok=True)
            # Do not recursively delete unexpected assets, even in our folder.
            for prepared in pixel_dirs:
                if safe_path(prepared, (folder,)) and prepared.is_dir() and not any(prepared.iterdir()):
                    prepared.rmdir()
            if all(path == marker for path in folder.iterdir()):
                marker.unlink()
                folder.rmdir()
                with _workers_lock:
                    _session_workers.pop(key, None)
        except (OSError, ValueError):
            pass
    threading.Thread(target=retire, name='mpv-overlay-session-reaper', daemon=True).start()
