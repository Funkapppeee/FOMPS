# FOMPS in-game mod — design

An in-game panel in Satisfactory that mirrors the FOMPS desktop app: see your
world's share code and who's hosting, and take/release the host — without
alt-tabbing.

## Key idea: the mod is a thin VIEW over the running desktop app
The FOMPS desktop app already runs a local web server on `127.0.0.1:8770`
(`/api/state`, `/api/host`, `/api/finish`, `/api/create`, `/api/join`). The mod
just calls those **localhost** endpoints. So the mod holds almost no logic — the
already-tested app does all the real work (save detection, cloud sync, locking,
versioning). Tiny mod = survives game/SML updates with minimal fixes.

```
game (mod UI)  ->  127.0.0.1:8770 (desktop app)  ->  Cloudflare  ->  R2
```

## In-game UX
- A keybind (default **F6**) toggles a FOMPS panel (UMG widget); optionally also
  an entry in the pause menu.
- Panel (data from `GET /api/state`):
  - each world: name, **share code** (copy), version, host status (free / "X hosting")
  - per world: **Take Host** (`POST /api/host`), **Finish & Upload** (`POST /api/finish`)
  - **Create** / **Join by code** (`POST /api/create` / `/api/join`)
  - a status line for results and errors
- **Open FOMPS app** button → focuses the desktop UI for anything advanced.

## Requirements
- The desktop app must be running (auto-start with Windows, or the mod launches
  `FOMPS.exe` if nothing answers on `127.0.0.1:8770`).
- HTTP from the mod: Unreal `FHttpModule` (C++) or an HTTP blueprint helper.

## Components
- **UMG widget** (Blueprint): the panel, world list, buttons.
- **Small C++/BP helper**: HTTP GET/POST to localhost, parse JSON, fill the widget.
- **Keybind** (SML input action) or pause-menu injection.
- Packaged with **Alpakit**, published to ficsit.app.

## v1 scope (thin)
Status view + Take Host + Finish + Create/Join, all via the localhost app.
NOT in v1: sync logic inside the mod, save-load automation, in-game save transfer.

## Build toolchain (separate, heavy — the real cost)
CSS **Unreal Engine 5.6.1** + **Visual Studio 2022** + the **SML starter project**
(~100–150 GB total). The engine and starter project can live on **any drive
(E: is fine; slow HDD is OK here)**. Stock UE 5.5 on D: is unrelated and stays
untouched. VS keeps some core components on C: (~10–20 GB, unavoidable); the big
engine goes on E:.
