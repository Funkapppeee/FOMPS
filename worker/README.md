# OpenMPSync sync server — Cloudflare Worker + R2

Serverless, free-tier, zero-maintenance backend for OpenMPSync. Same HTTP API as
the Flask server (`../server`), so the desktop client works with either.

Free-tier headroom: Workers 100k req/day, R2 10 GB storage + **no egress fees**,
100 MB max upload — plenty for a save-sync service.

## Deploy your own (community instance OR self-host — same steps)
Anyone with a free Cloudflare account can run their own copy. One-time:

```bash
npm install                       # gets wrangler + types
npx wrangler login                # opens browser, log into Cloudflare
npx wrangler r2 bucket create openmpsync
npx wrangler deploy               # prints your https://openmpsync.<you>.workers.dev URL
```

Put that URL into the desktop app (**Settings → Sync server URL**). Done — no VM,
no port forwarding, HTTPS + DDoS protection included.

## Test locally (no Cloudflare account needed)
`npx wrangler dev` runs it with a local emulated R2, on `http://127.0.0.1:8787`.
Point the client's server URL there to exercise the full flow offline.

## Notes
- `KEEP` (in `wrangler.toml`) = backups kept per world (default 10).
- Data-safety is the push conflict-guard (`base` version check); the lock is
  advisory UX, so no save is ever clobbered even under a rare race.
- For bulletproof locking later, a Durable Object per code can serialize writes.
