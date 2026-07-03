"""
saveinfo.py - read Satisfactory .sav header info (no full decompress needed).

The .sav header is uncompressed at the start of the file. We only read the
early, stable fields (present across header versions): session name, play
duration, and save timestamp. That's all the sync engine needs to identify a
world and show "Nuts - 42h - saved 3h ago".

Part of Open MPSync (working name). Pure stdlib, cross-platform.
"""
from __future__ import annotations
import os, struct, glob
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def _read_int(f, n, signed=True):
    return int.from_bytes(f.read(n), "little", signed=signed)


def _read_fstring(f) -> str:
    """Unreal FString: int32 length, then bytes. >0 = UTF-8 (+null),
    <0 = UTF-16LE (len is negative char count, +null)."""
    n = _read_int(f, 4)
    if n == 0:
        return ""
    if n > 0:
        raw = f.read(n)
        return raw[:-1].decode("utf-8", "replace")
    raw = f.read(-n * 2)
    return raw[:-2].decode("utf-16-le", "replace")


def _ticks_to_dt(ticks: int) -> datetime | None:
    # .NET ticks: 100ns intervals since 0001-01-01.
    try:
        return datetime(1, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=ticks / 10)
    except Exception:
        return None


@dataclass
class SaveInfo:
    path: str
    session_name: str = ""
    play_seconds: int = 0
    saved_at: datetime | None = None
    save_header_version: int = 0
    save_version: int = 0
    build_version: int = 0
    map_name: str = ""
    error: str = ""

    @property
    def play_hms(self) -> str:
        s = self.play_seconds
        return f"{s // 3600}h{(s % 3600) // 60:02d}m"

    @property
    def mtime(self) -> datetime:
        return datetime.fromtimestamp(os.path.getmtime(self.path), tz=timezone.utc)


def read_save_info(path: str) -> SaveInfo:
    info = SaveInfo(path=path)
    try:
        with open(path, "rb") as f:
            info.save_header_version = _read_int(f, 4)
            info.save_version = _read_int(f, 4)
            info.build_version = _read_int(f, 4)
            if info.save_header_version >= 14:
                _read_fstring(f)                    # saveName (v14+, e.g. "Nuts_030726-003512")
            info.map_name = _read_fstring(f)        # mapName (e.g. "Persistent_Level")
            _read_fstring(f)                        # mapOptions (spawn query string, ignored)
            info.session_name = _read_fstring(f)    # what we want (e.g. "Nuts")
            info.play_seconds = _read_int(f, 4)
            info.saved_at = _ticks_to_dt(_read_int(f, 8))
    except Exception as e:  # noqa: BLE001 - fall back to file metadata
        info.error = f"{type(e).__name__}: {e}"
    return info


def default_savegames_dir() -> str | None:
    """Windows Satisfactory save root: %LOCALAPPDATA%\\FactoryGame\\Saved\\SaveGames"""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    root = os.path.join(base, "FactoryGame", "Saved", "SaveGames")
    return root if os.path.isdir(root) else None


def find_local_saves(roots=None) -> list[SaveInfo]:
    """Scan for local .sav files. `roots` may be None (auto-detect every
    SaveGames dir cross-platform via locate.save_roots()), a single path, or a
    list of paths."""
    if roots is None:
        try:
            from . import locate           # package import
        except ImportError:
            import locate                  # run-as-script fallback
        roots = locate.save_roots()
    elif isinstance(roots, str):
        roots = [roots]
    saves = []
    for root in roots:
        for p in glob.glob(os.path.join(root, "**", "*.sav"), recursive=True):
            saves.append(read_save_info(p))
    saves.sort(key=lambda s: s.mtime, reverse=True)
    return saves


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else None
    rows = find_local_saves(target if target and os.path.isdir(target) else None)
    if target and os.path.isfile(target):
        rows = [read_save_info(target)]
    print(f"{'SESSION':<16} {'PLAYED':>8} {'SAVED (header)':<20} FILE")
    print("-" * 90)
    for s in rows[:40]:
        try:
            when = s.saved_at.astimezone().strftime("%Y-%m-%d %H:%M") if s.saved_at else "?"
        except (OSError, ValueError):
            when = "?"
        name = s.session_name or "(unreadable)"
        print(f"{name:<16} {s.play_hms:>8} {when:<20} {os.path.basename(s.path)}"
              + (f"   !{s.error}" if s.error else ""))
