/**
 * OpenMPSync sync server - Cloudflare Worker + R2 edition.
 *
 * Serverless, free-tier, zero-maintenance backend for the share-code host-swap
 * flow. Implements the SAME HTTP API as the Flask server, so the Python client
 * works unchanged. Saves + manifest live in R2 (one prefix per code).
 *
 * Deploy: see worker/README.md.  GPL-3.0.
 */
export interface Env {
  BUCKET: R2Bucket;
  KEEP?: string;
}

const ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"; // no ambiguous 0/O/1/I/L
const LOCK_HOURS = 6;

type Lock = { holder: string; since: string; expires: string } | null;
interface Manifest {
  world_id: string;
  session_name: string;
  current_version: number;
  current_file: string | null;
  lock: Lock;
  history: Array<Record<string, unknown>>;
}

const nowISO = () => new Date().toISOString();

function genCode(n = 8): string {
  const a = new Uint8Array(n);
  crypto.getRandomValues(a);
  return Array.from(a, (b) => ALPHABET[b % ALPHABET.length]).join("");
}
function validCode(c: string): boolean {
  return c.length >= 4 && [...c].every((ch) => ALPHABET.includes(ch));
}
function json(data: unknown, status = 200, extra: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json", ...extra },
  });
}
const err = (msg: string, status = 400) => json({ error: msg }, status);

async function loadManifest(env: Env, code: string): Promise<Manifest | null> {
  const obj = await env.BUCKET.get(`${code}/manifest.json`);
  return obj ? (JSON.parse(await obj.text()) as Manifest) : null;
}
async function saveManifest(env: Env, code: string, m: Manifest): Promise<void> {
  await env.BUCKET.put(`${code}/manifest.json`, JSON.stringify(m), {
    httpMetadata: { contentType: "application/json" },
  });
}
function activeLock(m: Manifest): Lock {
  if (!m.lock) return null;
  return new Date(m.lock.expires).getTime() < Date.now() ? null : m.lock;
}
async function readUser(req: Request, url: URL): Promise<string> {
  const body = (await req.json().catch(() => ({}))) as { user?: string };
  return (body.user || url.searchParams.get("user") || "anon").toString().slice(0, 40);
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    const p = url.pathname;
    try {
      if (req.method === "GET" && p === "/") {
        return new Response("OpenMPSync (Cloudflare) up. Use the desktop app + a share code.");
      }

      // create a world -> code
      if (req.method === "POST" && p === "/api/worlds") {
        const body = (await req.json().catch(() => ({}))) as { session?: string };
        const session = (body.session || url.searchParams.get("session") || "World").toString().slice(0, 64);
        let code = genCode();
        for (let i = 0; i < 20 && (await env.BUCKET.head(`${code}/manifest.json`)); i++) code = genCode();
        await saveManifest(env, code, {
          world_id: code, session_name: session, current_version: 0,
          current_file: null, lock: null, history: [],
        });
        return json({ code, session });
      }

      // /api/w/<code>[/lock|/unlock|/push|/pull]
      const mm = p.match(/^\/api\/w\/([^/]+)(?:\/(lock|unlock|push|pull))?$/);
      if (mm) {
        const code = mm[1].toUpperCase();
        const action = mm[2];
        if (!validCode(code)) return err("Invalid code.", 404);
        const m = await loadManifest(env, code);
        if (!m) return err("No world with that code.", 404);

        if (!action && req.method === "GET") {
          return json({
            code, session: m.session_name, current_version: m.current_version,
            lock: activeLock(m), history: m.history.slice(-10),
          });
        }

        if (action === "lock" && req.method === "POST") {
          const user = await readUser(req, url);
          const lk = activeLock(m);
          if (lk && lk.holder !== user) return err(`${lk.holder} is hosting (since ${lk.since.slice(0, 16)}).`, 409);
          m.lock = { holder: user, since: nowISO(), expires: new Date(Date.now() + LOCK_HOURS * 3600e3).toISOString() };
          await saveManifest(env, code, m);
          return json({ lock: m.lock });
        }

        if (action === "unlock" && req.method === "POST") {
          const user = await readUser(req, url);
          let released = false;
          if (m.lock && m.lock.holder === user) { m.lock = null; await saveManifest(env, code, m); released = true; }
          return json({ released });
        }

        if (action === "push" && req.method === "POST") {
          const user = (url.searchParams.get("user") || "anon").slice(0, 40);
          const base = url.searchParams.get("base");
          if (base !== null && Number(base) < m.current_version) {
            return err(`Out of date: your base v${base} < current v${m.current_version}. Pull first.`, 409);
          }
          const data = await req.arrayBuffer();
          if (data.byteLength === 0) return err("empty body");
          const ver = m.current_version + 1;
          const stamp = nowISO().replace(/[-:T]/g, "").slice(0, 15);
          const file = `versions/v${String(ver).padStart(3, "0")}_${m.session_name || "world"}_${stamp}_${user}.sav`;
          await env.BUCKET.put(`${code}/${file}`, data);
          m.history.push({ version: ver, file, session: m.session_name, pushed_by: user, pushed_at: nowISO(), size: data.byteLength });
          m.current_version = ver;
          m.current_file = file;
          if (m.lock && m.lock.holder === user) m.lock = null;
          const keep = parseInt(env.KEEP || "10", 10);
          while (m.history.length > keep) {
            const old = m.history.shift() as { file?: string } | undefined;
            if (old?.file) await env.BUCKET.delete(`${code}/${old.file}`);
          }
          await saveManifest(env, code, m);
          return json({ version: ver });
        }

        if (action === "pull" && req.method === "GET") {
          if (!m.current_file) return err("no save uploaded yet", 404);
          const obj = await env.BUCKET.get(`${code}/${m.current_file}`);
          if (!obj) return err("save missing", 404);
          return new Response(obj.body, {
            headers: {
              "content-type": "application/octet-stream",
              "content-disposition": `attachment; filename="${m.current_file.split("/").pop()}"`,
              "x-version": String(m.current_version),
              "x-session": m.session_name || "",
            },
          });
        }
      }
      return err("Not found", 404);
    } catch (e) {
      return err("server error: " + ((e as Error)?.message || String(e)), 500);
    }
  },
};
