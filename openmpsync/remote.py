"""
remote.py - client for the OpenMPSync share-code server.

Same operations as the local folder store (status/claim/release/push/pull) but
over HTTP against a server, keyed by a short CODE. All requests are OUTBOUND,
so no player needs port forwarding. Stdlib only (urllib) - no extra deps.

GPL-3.0. Part of Funk's OpenMPSync.
"""
from __future__ import annotations
import os, json, shutil
from datetime import datetime
from urllib import request as _rq, parse as _parse, error as _err


class RemoteError(RuntimeError):
    pass


USER_AGENT = "OpenMPSync/0.1"  # default Python-urllib UA gets bot-blocked by Cloudflare


def _call(method, url, data=None, headers=None):
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    req = _rq.Request(url, data=data, method=method, headers=h)
    try:
        with _rq.urlopen(req, timeout=60) as resp:
            return resp.read(), resp.headers   # HTTPMessage: case-insensitive .get()
    except _err.HTTPError as e:
        raw = e.read()
        try:
            msg = json.loads(raw).get("error", raw.decode("utf-8", "replace"))
        except Exception:
            msg = raw.decode("utf-8", "replace")
        raise RemoteError(f"{e.code}: {msg}") from None
    except _err.URLError as e:
        raise RemoteError(f"cannot reach server: {e.reason}") from None


def _json(method, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    body, _ = _call(method, url, data=data,
                    headers={"Content-Type": "application/json"} if data else {})
    return json.loads(body) if body else {}


class RemoteWorld:
    def __init__(self, base_url: str, code: str):
        self.base = base_url.rstrip("/")
        self.code = code

    @classmethod
    def create(cls, base_url: str, session: str) -> "RemoteWorld":
        r = _json("POST", base_url.rstrip("/") + "/api/worlds", {"session": session})
        return cls(base_url, r["code"])

    def status(self) -> dict:
        return _json("GET", f"{self.base}/api/w/{self.code}")

    def claim(self, user: str) -> dict:
        return _json("POST", f"{self.base}/api/w/{self.code}/lock", {"user": user})["lock"]

    def release(self, user: str) -> bool:
        return _json("POST", f"{self.base}/api/w/{self.code}/unlock", {"user": user})["released"]

    def push(self, local_save: str, user: str, base_version: int) -> int:
        with open(local_save, "rb") as f:
            data = f.read()
        q = _parse.urlencode({"user": user, "base": base_version})
        body, _ = _call("POST", f"{self.base}/api/w/{self.code}/push?{q}",
                        data=data, headers={"Content-Type": "application/octet-stream"})
        return json.loads(body)["version"]

    def pull(self, local_dir: str, session: str | None = None):
        body, hdrs = _call("GET", f"{self.base}/api/w/{self.code}/pull")
        session = session or hdrs.get("X-Session") or "World"
        os.makedirs(local_dir, exist_ok=True)
        dst = os.path.join(local_dir, f"{session}.sav")
        if os.path.exists(dst):
            shutil.copy2(dst, dst + f".bak-{datetime.now():%Y%m%d-%H%M%S}")
        with open(dst, "wb") as f:
            f.write(body)
        return int(hdrs.get("X-Version", "0")), dst
