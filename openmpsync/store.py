"""
store.py - Open MPSync sync store (the host-swap engine).

Moves a Satisfactory save through shared storage (v1: a shared cloud folder)
with a cooperative lock ("Funk is hosting") and full versioned history so no
one's factory is ever lost or clobbered. No game, no Unreal - fully testable.

Shared layout:
    <shared>/manifest.json          # world state + lock + history
    <shared>/versions/vNNN_<session>_<ts>_<user>.sav

Local config (%APPDATA%/OpenMPSync/config.json) remembers your name + worlds.
"""
from __future__ import annotations
import os, json, shutil, hashlib, getpass, glob
from datetime import datetime, timezone, timedelta
try:
    from . import saveinfo          # package import
except ImportError:
    import saveinfo                 # run-as-script fallback

LOCK_HOURS = 6
# Default community instance (free Cloudflare Worker). Users can override in
# Settings, or point at their own self-hosted server.
DEFAULT_SERVER = "https://openmpsync.funksopenmultisync.workers.dev"


def _now() -> datetime: return datetime.now(timezone.utc)
def _iso() -> str: return _now().isoformat()
def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------- local config
def config_dir() -> str:
    base = os.environ.get("OPENMPSYNC_HOME") or os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    d = os.path.join(base, "OpenMPSync")
    os.makedirs(d, exist_ok=True)
    return d


def load_config() -> dict:
    p = os.path.join(config_dir(), "config.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"user": getpass.getuser(), "worlds": {}}


def save_config(cfg: dict) -> None:
    with open(os.path.join(config_dir(), "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def latest_local_save(local_dir: str, session: str) -> str | None:
    """Newest local .sav belonging to `session` (matches header session name,
    falls back to filename prefix). This is what you just played and will upload."""
    best, best_mtime = None, -1.0
    for p in glob.glob(os.path.join(local_dir, "*.sav")):
        name = os.path.basename(p)
        if "_autosave" not in name and not name.startswith(session):
            info = saveinfo.read_save_info(p)
            if info.session_name != session:
                continue
        else:
            info = saveinfo.read_save_info(p)
            if info.session_name and info.session_name != session:
                continue
        m = os.path.getmtime(p)
        if m > best_mtime:
            best, best_mtime = p, m
    return best


# ---------------------------------------------------------------- world store
class WorldStore:
    def __init__(self, shared: str, retention: int | None = None):
        self.shared = shared
        self.versions = os.path.join(shared, "versions")
        self.manifest_path = os.path.join(shared, "manifest.json")
        self.retention = retention   # keep only the newest N backups (None = keep all)

    def _prune(self, m: dict) -> None:
        """Drop oldest backups beyond `retention` (deletes files + history)."""
        if not self.retention:
            return
        extra = len(m["history"]) - self.retention
        for entry in m["history"][:max(0, extra)]:
            try:
                os.remove(os.path.join(self.shared, entry["file"]))
            except OSError:
                pass
        if extra > 0:
            m["history"] = m["history"][extra:]

    def exists(self) -> bool:
        return os.path.exists(self.manifest_path)

    def init(self, world_id: str, session: str) -> dict:
        os.makedirs(self.versions, exist_ok=True)
        if not self.exists():
            self._save({"world_id": world_id, "session_name": session,
                        "current_version": 0, "current_file": None,
                        "lock": None, "history": []})
        return self.load()

    def load(self) -> dict:
        with open(self.manifest_path, encoding="utf-8") as f:
            return json.load(f)

    def _save(self, m: dict) -> None:
        os.makedirs(self.shared, exist_ok=True)
        tmp = self.manifest_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(m, f, indent=2)
        os.replace(tmp, self.manifest_path)  # atomic on same volume

    def active_lock(self, m: dict | None = None):
        m = m or self.load()
        lk = m.get("lock")
        if not lk:
            return None
        if datetime.fromisoformat(lk["expires"]) < _now():
            return None  # stale (host crashed) -> treat as free
        return lk

    def claim(self, user: str) -> dict:
        m = self.load()
        lk = self.active_lock(m)
        if lk and lk["holder"] != user:
            raise RuntimeError(f"{lk['holder']} is hosting (since {lk['since'][:16]}).")
        m["lock"] = {"holder": user, "since": _iso(),
                     "expires": (_now() + timedelta(hours=LOCK_HOURS)).isoformat()}
        self._save(m)
        return m["lock"]

    def release(self, user: str, force: bool = False) -> bool:
        m = self.load()
        lk = m.get("lock")
        if lk and (force or lk["holder"] == user):
            m["lock"] = None
            self._save(m)
            return True
        return False

    def pull(self, local_dir: str, session: str | None = None):
        """Download the group's current save into local_dir (backing up any
        existing file). Returns (version, dest_path)."""
        m = self.load()
        if not m.get("current_file"):
            raise RuntimeError("No save has been uploaded to this world yet.")
        src = os.path.join(self.shared, m["current_file"])
        session = session or m.get("session_name") or "World"
        os.makedirs(local_dir, exist_ok=True)
        dst = os.path.join(local_dir, f"{session}.sav")
        if os.path.exists(dst):
            shutil.copy2(dst, dst + f".bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(src, dst)
        return m["current_version"], dst

    def push(self, local_save: str, user: str, base_version: int | None = None) -> int:
        """Upload local_save as the next version. Refuses if you're behind
        (someone pushed since you pulled). Releases your lock (session done)."""
        m = self.load()
        if base_version is not None and base_version < m["current_version"]:
            raise RuntimeError(
                f"Out of date: your base v{base_version} < current v{m['current_version']}. Pull first.")
        info = saveinfo.read_save_info(local_save)
        ver = m["current_version"] + 1
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        fname = f"v{ver:03d}_{info.session_name or 'world'}_{stamp}_{user}.sav"
        os.makedirs(self.versions, exist_ok=True)
        dst = os.path.join(self.versions, fname)
        shutil.copy2(local_save, dst)
        m["history"].append({
            "version": ver, "file": os.path.join("versions", fname),
            "session": info.session_name, "play_seconds": info.play_seconds,
            "saved_at": info.saved_at.isoformat() if info.saved_at else None,
            "pushed_by": user, "pushed_at": _iso(),
            "sha256": _sha256(dst), "size": os.path.getsize(dst),
        })
        m["current_version"], m["current_file"] = ver, os.path.join("versions", fname)
        if (m.get("lock") or {}).get("holder") == user:
            m["lock"] = None  # finishing your session releases the lock
        self._prune(m)        # keep only the newest N backups
        self._save(m)
        return ver
