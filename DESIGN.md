# Open MPSync — design doc (working name)

A free, open-source, self-hostable successor to **MPSync**: play the same
Satisfactory multiplayer world with friends **without a dedicated server** —
whoever is free hosts next, saves sync automatically, nobody's work is lost.

## Why the original died, and what that teaches us
MPSync was a **game mod + one person's central backend** (`mpsync.app`). Two
fatal properties:
1. **A mod** → every Satisfactory/SML update broke it. Endless maintenance; it
   fell behind at 1.0 (last build 3.0.7, Oct 2024) and never came back for 1.1/1.2.
2. **One central server** → when the maintainer went quiet, the whole thing was
   orphaned. Users can't self-rescue.

**Both are design choices we will not repeat.**

## The landscape (2026)
- **MPSync** — mod + central backend. Abandoned for 1.2. (what we're replacing)
- **SaveSync** (savesync.games) — the modern working solution. Notably it is an
  **external tool, not a mod**, and it works. But it's **paid/closed**.
- **florstone/Satisfactory-multiplayer** & **patrix87/SatisfactorySync** — crude
  open-source PowerShell scripts: shared cloud folder + lock file. Proves the
  mechanic; unpolished, Windows/Epic-only, 2020.

**Gap we fill:** a *polished, free, open-source, cross-platform* host-swap tool.
The free/open answer to paid SaveSync; the modern answer to the old scripts.

## Core decision: an EXTERNAL TOOL, not a mod
Confirmed by three independent sources (SaveSync, florstone, MPSync's own FAQ):
hosting a downloaded `.sav` and starting a **friends-only** game is all that's
needed — no in-game code required. Going external means:
- **Immune to game/SML updates** (the thing that killed MPSync-the-mod).
- No 150 GB Unreal toolchain; ships as a normal app.
- Reuses mature open-source **save-header parsers** (GreyHak/sat_sav_parse has
  `readSaveFileInfo()` → session name, playtime, timestamp, cheap/no full decompress).

Trade-off: no in-game menu. You use the app, then host normally. Acceptable for
host-swapping, and far more robust. (A thin optional mod for in-game UX could
come much later.)

## Architecture
```
[Player A app] ──┐                        ┌── [Player B app]
                 ├──►  shared storage  ◄──┤
[Player C app] ──┘   (saves + lock + versions)
```
**Storage is bring-your-own (never a single point we control):**
- **Tier 1 (v1): shared cloud folder** — point the app at a Dropbox/Drive/
  OneDrive/Nextcloud-synced folder. Zero hosting. This is v1.
- **Tier 2 (later): self-hostable sync server** — small REST service (Flask,
  like FMCSL) for groups who want internet sync without a shared cloud folder.
- **Tier 3 (later): direct S3/WebDAV/Drive API.**

## The locking model (prevents the #1 danger: divergent saves)
A `world.lock` in shared storage: `{ holder, since, expires, base_version }`.
- **Pull & Host:** must acquire the lock. If someone else holds it → app shows
  "Levy is hosting since 20:14" and blocks hosting.
- **Finish & Upload:** pushes the new save (version+1), releases the lock.
- **Stale lock** (host crashed): auto-expires after N hours + manual override.
- **Conflict guard:** if your local base_version ≠ remote, warn before upload.

## Safety
- **Every upload is a new versioned copy** (`Nuts_v37_20260703-2014_funk.sav`),
  never an overwrite. Full history = never lose a factory. (This was florstone's
  whole reason to exist; we do it properly.)
- Detect & warn if Steam/Epic **cloud save** is enabled (it fights the tool).

## Save awareness
- Auto-detect the local SaveGames folder per platform
  (Win: `%LOCALAPPDATA%\FactoryGame\Saved\SaveGames\<id>\`).
- Read `.sav` headers → show "Nuts · 42h played · saved 3h ago by Funk".
- Header format is documented & versioned (v13/save v46 @ 1.0); parsers exist.

## UX flow (host-swap)
1. Open app → see the shared world + lock status ("Free" / "Funk hosting").
2. **Pull & Host** → downloads latest into your SaveGames, takes the lock.
3. Play — host **friends-only** in-game as normal.
4. **Finish & Upload** → uploads, bumps version, releases lock.
5. Group sees the new version; next free person pulls.

## Tech stack (proposed)
- **Python** (cross-platform; matches FMCSL; lets us reuse the Python save parser).
- Core as a library/CLI first (testable), GUI on top.
- GUI: Flask + local web UI (consistent with FMCSL) **or** native (PySide6). TBD.
- License: **GPL-3.0** or MIT (open, community-forkable — the anti-orphan clause).

## v1 scope (smallest genuinely useful release)
1. Detect local Satisfactory saves + read headers.
2. Configure a shared-folder "world."
3. Pull & Host / Finish & Upload with lock + versioned backups + conflict guard.
4. Minimal GUI showing world, lock holder, last save, the two buttons.
Everything else (self-hosted server, in-game mod, multi-world, accounts) = later.

## Open questions
- Final name/branding (Funk's ___?).
- GUI: web (Flask) vs native (PySide6)?
- v1 storage: shared-folder only, or also ship the self-hosted server?
- Distribution: PyInstaller .exe (like FMCSL) + GitHub releases.

## Prior art / references
- GreyHak/sat_sav_parse (Python save parser, header reader)
- etothepii4/satisfactory-file-parser (TS), Goz3rr/SatisfactorySaveEditor (C#)
- florstone/Satisfactory-multiplayer, patrix87/SatisfactorySync (shared-folder scripts)
- SaveSync (savesync.games) — paid external tool, feature benchmark
