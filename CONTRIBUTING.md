# Contributing to FOMPS

Thanks for helping keep FOMPS alive and open! It's **GPL-3.0** — anyone can fork
it, and derivatives stay open, so it can never be orphaned like the original.

## Layout
- `openmpsync/` — Python client, engine, CLI, and web UI
- `server/` — Flask + Docker backend (self-host)
- `worker/` — Cloudflare Worker + R2 backend (serverless)

The client speaks a small HTTP API (`/api/worlds`, `/api/w/<code>/{lock,unlock,push,pull}`);
**any backend implementing it works**, so client and server can evolve independently.

## Dev setup
- **Client / UI:** `pip install flask`, then `python -m openmpsync.webapp`.
- **Worker:** `cd worker && npm install && npx wrangler dev` (runs with a local
  emulated R2 — no Cloudflare account needed to test).
- No heavy dependencies, please — the client core is stdlib-only on purpose.

## Roadmap / good first issues
- Optional **LAN sync** (zero server on a home network)
- **Durable Object** per code for strict, race-free locking
- **Multi-game** support (Ludusavi's save-location manifest)
- A thin optional **in-game SML mod** for an in-game menu + cloud link

## Before a PR
Run the flow against a local server (`server/app.py`) or `wrangler dev` and make
sure create → host → finish still works. Keep it simple.
