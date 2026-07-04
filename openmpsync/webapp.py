"""
webapp.py - local companion web UI for Funk's OpenMPSync.

Serves a clean page on 127.0.0.1 that detects your saves and drives the
share-code host-swap flow. Same shape as MPSync / FMCSL: a local page talking
to the (remote, self-hostable) sync server. Run:  python -m openmpsync.webapp

GPL-3.0.
"""
import os, sys, time, webbrowser, threading
from flask import Flask, request, jsonify, send_from_directory
from . import store, remote, saveinfo, locate

WEB = os.path.join(os.path.dirname(__file__), "web")
if not os.path.isdir(WEB) and hasattr(sys, "_MEIPASS"):   # PyInstaller onefile
    WEB = os.path.join(sys._MEIPASS, "openmpsync", "web")
app = Flask(__name__, static_folder=None)


def _cfg():
    c = store.load_config()
    c.setdefault("worlds", {})
    c.setdefault("server", store.DEFAULT_SERVER)
    return c


def _err(msg, code=400):
    return jsonify(error=msg), code


# --- AUTO MODE: watch linked worlds' local saves, auto-upload when you save ---
_auto_last = {}   # ref -> mtime of the newest save we've already handled
_events = []      # recent auto-mode events, surfaced in the UI console


def _log(msg):
    _events.append({"t": time.strftime("%H:%M:%S"), "msg": msg})
    del _events[:-40]


def _auto_tick():
    """One pass: for each auto-enabled world, if a NEW save appeared and has
    settled (game finished writing), upload it."""
    c = _cfg()
    changed = False
    for ref, w in c["worlds"].items():
        if not w.get("auto", True):
            continue
        ldir, session = w.get("local_dir"), w.get("session")
        if not ldir or not session:
            continue
        latest = store.latest_local_save(ldir, session)
        if not latest:
            continue
        mt = os.path.getmtime(latest)
        if ref not in _auto_last:
            _auto_last[ref] = mt          # baseline: ignore the pre-existing save
            continue
        if mt <= _auto_last[ref] or (time.time() - mt) < 8:
            continue                       # unchanged, or still being written
        _auto_last[ref] = mt
        try:
            ver = remote.RemoteWorld(w["server"], w["code"]).push(
                latest, c.get("user") or "anon", w.get("base_version", 0))
            w["base_version"] = ver
            changed = True
            _log(f"Auto-uploaded '{ref}' as v{ver} (you saved)")
        except remote.RemoteError as e:
            _log(f"Auto-upload skipped for '{ref}': {e}")
    if changed:
        store.save_config(c)


def _auto_loop():
    while True:
        try:
            _auto_tick()
        except Exception:
            pass
        time.sleep(15)


@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/api/state")
def state():
    c = _cfg()
    worlds = []
    for ref, w in c["worlds"].items():
        item = {"ref": ref, "code": w.get("code"), "session": w.get("session"),
                "server": w.get("server"), "base_version": w.get("base_version", 0)}
        try:
            st = remote.RemoteWorld(w["server"], w["code"]).status()
            item["version"] = st["current_version"]
            item["lock"] = st.get("lock")
        except Exception as e:  # server down / bad code - show but don't crash
            item["error"] = str(e)
        worlds.append(item)
    saves = [{"session": s.session_name, "play": s.play_hms, "file": os.path.basename(s.path)}
             for s in saveinfo.find_local_saves()[:25] if s.session_name]
    return jsonify({"user": c.get("user", ""), "server": c.get("server", ""),
                    "worlds": worlds, "saves": saves, "events": _events[-15:]})


@app.post("/api/settings")
def settings():
    c = _cfg(); d = request.get_json(force=True)
    if "user" in d:
        c["user"] = (d["user"] or "").strip()
    if "server" in d:
        c["server"] = (d["server"] or "").strip().rstrip("/")
    store.save_config(c)
    return jsonify(ok=True)


@app.post("/api/create")
def create():
    c = _cfg(); d = request.get_json(force=True)
    server = (d.get("server") or c["server"]).rstrip("/")
    ref = (d.get("ref") or "").strip(); session = (d.get("session") or "").strip()
    if not server:
        return _err("Set a server URL first (Settings).")
    if not ref or not session:
        return _err("Both a name and the in-game session name are required.")
    try:
        rw = remote.RemoteWorld.create(server, session)
    except remote.RemoteError as e:
        return _err(str(e), 502)
    c["worlds"][ref] = {"code": rw.code, "server": server, "session": session,
                        "local_dir": locate.primary_save_dir(), "base_version": 0}
    store.save_config(c)
    return jsonify(ok=True, code=rw.code)


@app.post("/api/join")
def join():
    c = _cfg(); d = request.get_json(force=True)
    server = (d.get("server") or c["server"]).rstrip("/")
    ref = (d.get("ref") or "").strip(); code = (d.get("code") or "").strip().upper()
    if not server:
        return _err("Set a server URL first (Settings).")
    if not ref or not code:
        return _err("A name and a share code are required.")
    try:
        st = remote.RemoteWorld(server, code).status()
    except remote.RemoteError as e:
        return _err(str(e), 502)
    c["worlds"][ref] = {"code": code, "server": server, "session": st.get("session") or "World",
                        "local_dir": locate.primary_save_dir(), "base_version": st.get("current_version", 0)}
    store.save_config(c)
    return jsonify(ok=True)


def _resolve(c, d):
    """Figure out which linked world a request means. Order of preference:
      1. an explicit `ref` (the user's own local nickname), if it exists;
      2. if the user has linked exactly ONE world, just use it (the common case
         for the in-game panel, so the Ref field can stay empty);
      3. otherwise match on the in-game `session` name the mod sent.
    Returns the world dict, or None if it can't be determined."""
    worlds = c["worlds"]
    ref = (d.get("ref") or "").strip()
    if ref and ref in worlds:
        return worlds[ref]
    if len(worlds) == 1:
        return next(iter(worlds.values()))
    sess = (d.get("session") or "").strip()
    if sess:
        for w in worlds.values():
            if (w.get("session") or "") == sess:
                return w
    return None


@app.post("/api/host")
def host():
    c = _cfg(); w = _resolve(c, request.get_json(force=True))
    if not w:
        return _err("Couldn't tell which world to host — link a world first, "
                    "or (if you have several) pass its name.")
    rw = remote.RemoteWorld(w["server"], w["code"])
    try:
        rw.claim(c.get("user") or "anon")
    except remote.RemoteError as e:
        return _err(str(e), 409)
    ver, dst = rw.pull(w["local_dir"], w["session"])
    w["base_version"] = ver; store.save_config(c)
    return jsonify(ok=True, version=ver, path=dst)


@app.post("/api/finish")
def finish():
    c = _cfg(); w = _resolve(c, request.get_json(force=True))
    if not w:
        return _err("Couldn't tell which world to finish — link a world first, "
                    "or (if you have several) pass its name.")
    local = store.latest_local_save(w["local_dir"], w["session"])
    if not local:
        return _err(f"No '{w['session']}' save found in your SaveGames to upload.")
    try:
        ver = remote.RemoteWorld(w["server"], w["code"]).push(local, c.get("user") or "anon", w.get("base_version", 0))
    except remote.RemoteError as e:
        return _err(str(e), 409)
    w["base_version"] = ver; store.save_config(c)
    return jsonify(ok=True, version=ver)


@app.post("/api/sync-down")
def sync_down():
    """Pull the latest save for each linked world IF the cloud is newer than our
    local copy (so hosting always hosts the newest; never clobbers unpushed work).
    Called by the in-game mod on startup = pull-on-host."""
    c = _cfg(); pulled = []
    for ref, w in c.get("worlds", {}).items():
        if not w.get("auto", True) or not w.get("local_dir") or not w.get("session"):
            continue
        try:
            rw = remote.RemoteWorld(w["server"], w["code"])
            st = rw.status()
            if st["current_version"] > w.get("base_version", 0):
                ver, dst = rw.pull(w["local_dir"], w["session"])
                w["base_version"] = ver
                _auto_last[ref] = os.path.getmtime(dst)   # don't let the watcher re-push what we just pulled
                pulled.append({"ref": ref, "version": ver})
                _log(f"Auto-pulled '{ref}' to v{ver} (newer version was available)")
        except remote.RemoteError:
            pass
    if pulled:
        store.save_config(c)
    return jsonify(ok=True, pulled=pulled)


@app.post("/api/forget")
def forget():
    c = _cfg(); c["worlds"].pop(request.get_json(force=True).get("ref"), None)
    store.save_config(c)
    return jsonify(ok=True)


def run(port=8770, open_browser=True):
    threading.Thread(target=_auto_loop, daemon=True).start()   # auto-mode watcher
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    run()
