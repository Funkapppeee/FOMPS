"""
locate.py - find Satisfactory SaveGames folders across OS + Steam/Epic.

Windows: %LOCALAPPDATA%/FactoryGame/Saved/SaveGames  (Steam & Epic share this).
Linux / Steam Deck: the game runs under Proton, so saves live inside the Proton
prefix:
  <steam-library>/steamapps/compatdata/526870/pfx/drive_c/users/steamuser/
      AppData/Local/FactoryGame/Saved/SaveGames
We scan every Steam library (from libraryfolders.vdf), the common Steam roots
(incl. Flatpak), and Steam Deck removable media.

Part of Funk's OpenMPSync (GPL-3.0). Pure stdlib.
"""
from __future__ import annotations
import os, sys, glob, re

STEAM_APPID = "526870"  # Satisfactory
_SUB = os.path.join("FactoryGame", "Saved", "SaveGames")
_PROTON_TAIL = os.path.join(
    "steamapps", "compatdata", STEAM_APPID, "pfx", "drive_c",
    "users", "steamuser", "AppData", "Local", _SUB)


def _existing(paths: list[str]) -> list[str]:
    seen, out = set(), []
    for p in paths:
        if p and os.path.isdir(p):
            rp = os.path.realpath(p)
            if rp not in seen:
                seen.add(rp)
                out.append(p)
    return out


def _steam_roots() -> list[str]:
    home = os.path.expanduser("~")
    return [
        os.path.join(home, ".steam", "steam"),
        os.path.join(home, ".steam", "root"),
        os.path.join(home, ".local", "share", "Steam"),
        os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"),  # Flatpak
        os.path.join(home, "Library", "Application Support", "Steam"),  # macOS
    ]


def _library_paths(steam_root: str) -> list[str]:
    """Every Steam library folder listed in libraryfolders.vdf (plus the root)."""
    libs = [steam_root]
    vdf = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
    try:
        with open(vdf, encoding="utf-8", errors="ignore") as f:
            libs += re.findall(r'"path"\s+"([^"]+)"', f.read())
    except OSError:
        pass
    return libs


def save_roots() -> list[str]:
    """All existing Satisfactory SaveGames directories on this machine."""
    roots: list[str] = []
    if sys.platform.startswith("win"):
        la = os.environ.get("LOCALAPPDATA")
        if la:
            roots.append(os.path.join(la, _SUB))
    else:
        for sr in _steam_roots():
            if os.path.isdir(sr):
                for lib in _library_paths(sr):
                    roots.append(os.path.join(lib, _PROTON_TAIL))
        for media in glob.glob("/run/media/*") + glob.glob("/run/media/*/*"):  # Deck SD cards
            roots.append(os.path.join(media, _PROTON_TAIL))
        roots.append(os.path.join(os.path.expanduser("~"), ".config", _SUB))
    return _existing(roots)


def primary_save_dir() -> str | None:
    """Best guess at the active account's SaveGames folder (the one with the
    most saves) - where we pull into and read the newest save from."""
    best, best_n = None, -1
    for root in save_roots():
        subs = [os.path.join(root, d) for d in os.listdir(root)
                if os.path.isdir(os.path.join(root, d))]
        for cand in (subs or [root]):
            n = len(glob.glob(os.path.join(cand, "*.sav")))
            if n > best_n:
                best, best_n = cand, n
    return best


if __name__ == "__main__":
    rs = save_roots()
    print(f"Platform: {sys.platform}")
    print(f"Found {len(rs)} SaveGames root(s):")
    for r in rs:
        print("  " + r)
    if not rs:
        print("  (none - is Satisfactory installed and has it been run at least once?)")
