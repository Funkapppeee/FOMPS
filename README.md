# FOMPS — Funk's OpenMPSync

**Play the same Satisfactory multiplayer world with friends — no dedicated
server needed.** Whoever's free hosts next; the save syncs through a short
**share code**; a lock stops two people editing at once; every version is kept
so no factory is ever lost.

Free and open-source — the successor to the abandoned **MPSync**, and a free
alternative to the paid **SaveSync**.

**GPL-3.0** · Windows / Linux / Steam Deck · no sign-in · no port forwarding

## How it works
1. One person **Creates** a world → gets an 8-character **share code**.
2. Give the code to friends; they **Join** with it — no account, no sign-in.
3. **Pull & Host** grabs the group's latest save; you host a normal
   *friends-only* game.
4. **Finish & Upload** pushes your save back and frees the host lock.
5. The next free person pulls and hosts. Full version history is kept (last 10).

Every request is **outbound**, and gameplay rides Satisfactory's own EOS relay —
so **nobody ever needs to port-forward.**

## Install
- **Windows (easiest):** download **`FOMPS.exe`** from Releases and run it. A
  browser tab opens with the app. Done — it works out of the box against the
  free community server.
- **From source:** `pip install flask`, then `python -m openmpsync.webapp`
  (or run `Run-OpenMPSync.bat`).

## Usage (CLI, optional)
```
python -m openmpsync.cli set-user Funk
python -m openmpsync.cli create nuts --session Nuts   # prints a share code
python -m openmpsync.cli join   nuts <CODE>           # a friend, with the code
python -m openmpsync.cli host   nuts                  # pull latest + take the lock
python -m openmpsync.cli finish nuts                  # upload + release the lock
```

## Self-host the server (optional)
Two backends, same client — point **Settings → server URL** at your own:
- **Serverless (Cloudflare, free):** see [`worker/README.md`](worker/README.md).
  Deploy your own in minutes on a free Cloudflare account — no VM, no upkeep.
- **Any box (Docker):**
  `docker build -t fomps -f server/Dockerfile . && docker run -p 8765:8765 -v fomps:/data fomps`

## Project layout
```
openmpsync/  engine + client + CLI + web UI  (Python)
server/      Flask + Docker self-host backend
worker/      Cloudflare Worker + R2 backend  (serverless)
```

## License
[GPL-3.0](LICENSE) — free forever, and can never be closed off or orphaned.

## Support
Made by **Funk**. If FOMPS saved your co-op factory, [**buy me a coffee ☕**](https://ko-fi.com/funkapppeee) —
it helps keep the free community server running.
