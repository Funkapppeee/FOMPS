# FOMPS — in-game mod

The Satisfactory side of FOMPS: a small SML mod that adds a **FOMPS** button to
the in-game pause menu. Clicking it opens a panel that talks to the FOMPS desktop
app (`127.0.0.1:8770`) so you can **Pull & Host** / **Finish (upload)** / **Refresh**
a shared world without leaving the game.

The mod is only a remote control — all the syncing lives in the desktop app (this
keeps the mod tiny and means Satisfactory updates rarely break it).

## Install (players)

1. Install **Satisfactory Mod Loader (SML)** via the Satisfactory Mod Manager
   (it's on ficsit.app).
2. Grab `FOMPS-Windows.zip` from this repo's
   [Releases](https://github.com/Funkapppeee/FOMPS/releases).
3. Extract it into your game so you end up with:
   `…/Satisfactory/FactoryGame/Mods/GameFeatures/FOMPS/`
   (containing `Binaries/`, `Content/`, `FOMPS.uplugin`).
4. Run the **FOMPS desktop app**, set your name, and **Join by code** with the
   world's share code.
5. Launch the game, press **Esc**, click **FOMPS**.

Works on both Steam and Epic (the zip ships both DLLs).

## Build from source (developers)

This folder (`FOMPS/`) is a GameFeatures plugin. Drop it into an SML dev setup at
`<SatisfactoryModLoader>/Mods/GameFeatures/FOMPS`, open the project in the
CSS Unreal Engine, and package with **Alpakit** (or build the module and cook the
content). Requires SML `^3.12.0`.

Key files:
- `Source/FOMPS/Public/FOMPSSubsystem.h` / `Private/FOMPSSubsystem.cpp` — the
  `UGameInstanceSubsystem` bridge (HTTP to the app) + the pause-menu button/panel.
- `Content/WBP_FOMPS.uasset` — the UMG panel.

GPL-3.0, same as the rest of the project.
