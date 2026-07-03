"""
OpenMPSync sync server - the r2modman-style "share code" backend.

Host uploads a save -> gets a short CODE -> friends paste the code to pull it.
No accounts, no sign-in; the code is the key. All clients talk to this server
over OUTBOUND HTTP, so no player ever needs port forwarding. Self-hostable;
reuses the tested openmpsync.store.WorldStore (one store per code).

Run:  python server/app.py            (PORT / OPENMPSYNC_DATA env vars)
GPL-3.0. Part of Funk's OpenMPSync.
"""
import os, sys, secrets
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import Flask, request, jsonify, send_file, abort
from openmpsync import store

DATA = os.environ.get("OPENMPSYNC_DATA", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(DATA, exist_ok=True)
RETENTION = int(os.environ.get("OPENMPSYNC_KEEP", "10"))  # backups kept per world
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no ambiguous 0/O/1/I/L
app = Flask(__name__)
# reject absurd uploads (a huge Satisfactory save is ~50-100MB; 256 is generous)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("OPENMPSYNC_MAX_MB", "256")) * 1024 * 1024


def _code(n=8):
    return "".join(secrets.choice(ALPHABET) for _ in range(n))


def _dir(code):
    # keep codes filesystem-safe
    if not code or not all(c in ALPHABET for c in code):
        abort(404, description="Invalid code.")
    return os.path.join(DATA, code)


def _ws(code):
    d = _dir(code)
    if not os.path.isdir(d):
        abort(404, description="No world with that code.")
    return store.WorldStore(d, retention=RETENTION)


@app.post("/api/worlds")
def create_world():
    body = request.get_json(silent=True) or {}
    session = body.get("session") or request.args.get("session") or "World"
    code = next((c for c in (_code() for _ in range(20)) if not os.path.isdir(_dir(c))), None)
    if not code:
        return jsonify({"error": "could not allocate code"}), 500
    store.WorldStore(_dir(code)).init(code, session)
    return jsonify({"code": code, "session": session})


@app.get("/api/w/<code>")
def status(code):
    ws = _ws(code); m = ws.load()
    return jsonify({"code": code, "session": m.get("session_name"),
                    "current_version": m["current_version"],
                    "lock": ws.active_lock(m), "history": m["history"][-10:]})


@app.post("/api/w/<code>/lock")
def lock(code):
    ws = _ws(code)
    user = (request.get_json(silent=True) or {}).get("user") or request.args.get("user") or "anon"
    try:
        return jsonify({"lock": ws.claim(user)})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 409


@app.post("/api/w/<code>/unlock")
def unlock(code):
    ws = _ws(code)
    user = (request.get_json(silent=True) or {}).get("user") or request.args.get("user") or "anon"
    return jsonify({"released": ws.release(user)})


@app.post("/api/w/<code>/push")
def push(code):
    ws = _ws(code)
    user = request.args.get("user", "anon")
    base = request.args.get("base", type=int)
    data = request.get_data()
    if not data:
        return jsonify({"error": "empty body"}), 400
    tmp = os.path.join(_dir(code), ".upload.tmp")
    with open(tmp, "wb") as f:
        f.write(data)
    try:
        return jsonify({"version": ws.push(tmp, user, base_version=base)})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 409
    finally:
        try: os.remove(tmp)
        except OSError: pass


@app.get("/api/w/<code>/pull")
def pull(code):
    ws = _ws(code); m = ws.load()
    if not m.get("current_file"):
        return jsonify({"error": "no save uploaded yet"}), 404
    path = os.path.join(ws.shared, m["current_file"])
    resp = send_file(path, as_attachment=True, download_name=os.path.basename(path))
    resp.headers["X-Version"] = str(m["current_version"])
    resp.headers["X-Session"] = m.get("session_name") or ""
    return resp


@app.get("/")
def home():
    return "OpenMPSync server up. Use the desktop app + a share code.", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8765)))
