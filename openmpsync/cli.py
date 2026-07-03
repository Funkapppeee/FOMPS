"""
cli.py - Funk's OpenMPSync command line.

The usable front-end: remembers your name + server, and drives the share-code
host-swap flow.

    openmpsync set-user Funk
    openmpsync set-server https://sync.example.com
    openmpsync create nuts --session Nuts     # -> prints a share CODE to give friends
    openmpsync join nuts ABCD2345             # friend registers that code
    openmpsync host nuts                       # pull latest + claim (Pull & Host)
    ...play a friends-only game...
    openmpsync finish nuts                      # upload + release (Finish & Upload)
    openmpsync list / status nuts / saves

GPL-3.0.
"""
from __future__ import annotations
import argparse, sys
from . import store, remote, saveinfo, locate


def _cfg():
    c = store.load_config()
    c.setdefault("worlds", {})
    c.setdefault("server", store.DEFAULT_SERVER)
    return c


def _world(c, ref):
    w = c["worlds"].get(ref)
    if not w:
        sys.exit(f"No world '{ref}'. Use `create` or `join` first (`list` to see them).")
    return w


def cmd_set_user(a):
    c = _cfg(); c["user"] = a.name; store.save_config(c); print(f"You are '{a.name}'.")


def cmd_set_server(a):
    c = _cfg(); c["server"] = a.url.rstrip("/"); store.save_config(c); print(f"Default server: {c['server']}")


def cmd_saves(a):
    rows = saveinfo.find_local_saves()
    if not rows:
        print("No local Satisfactory saves found."); return
    for s in rows[:30]:
        print(f"  {s.session_name or '(unreadable)':<16} {s.play_hms:>8}  {s.path}")


def cmd_create(a):
    c = _cfg()
    server = (a.server or c["server"]).rstrip("/")
    if not server:
        sys.exit("No server set. `openmpsync set-server <url>` or pass --server.")
    rw = remote.RemoteWorld.create(server, a.session)
    c["worlds"][a.ref] = {"code": rw.code, "server": server, "session": a.session,
                          "local_dir": a.local or locate.primary_save_dir(), "base_version": 0}
    store.save_config(c)
    print(f"Created world '{a.ref}'.  SHARE THIS CODE with friends:  {rw.code}")


def cmd_join(a):
    c = _cfg()
    server = (a.server or c["server"]).rstrip("/")
    if not server:
        sys.exit("No server set. `openmpsync set-server <url>` or pass --server.")
    rw = remote.RemoteWorld(server, a.code)
    st = rw.status()  # validates the code exists
    session = a.session or st.get("session") or "World"
    c["worlds"][a.ref] = {"code": a.code, "server": server, "session": session,
                          "local_dir": a.local or locate.primary_save_dir(),
                          "base_version": st.get("current_version", 0)}
    store.save_config(c)
    print(f"Joined '{a.ref}' (code {a.code}, session {session}, v{st.get('current_version', 0)}).")


def cmd_list(a):
    c = _cfg()
    if not c["worlds"]:
        print("No worlds yet. `create` or `join` one."); return
    for ref, w in c["worlds"].items():
        print(f"  {ref:<14} code={w['code']:<10} session={w['session']:<12} base=v{w.get('base_version',0)}  {w['server']}")


def _rw(w):
    return remote.RemoteWorld(w["server"], w["code"])


def cmd_status(a):
    w = _world(_cfg(), a.ref); st = _rw(w).status()
    lk = st.get("lock")
    print(f"World '{a.ref}' (code {w['code']}): v{st['current_version']}  session={st.get('session')}")
    print(f"  host: {lk['holder'] + ' since ' + lk['since'][:16] if lk else 'FREE'}")
    for h in st.get("history", [])[-5:]:
        print(f"  v{h['version']:<3} by {h['pushed_by']:<10} {h.get('pushed_at','')[:16]}")


def cmd_host(a):
    c = _cfg(); w = _world(c, a.ref); rw = _rw(w)
    try:
        rw.claim(c["user"])
    except remote.RemoteError as e:
        sys.exit(f"Can't host: {e}")
    ver, dst = rw.pull(w["local_dir"], w["session"])
    w["base_version"] = ver; store.save_config(c)
    print(f"Hosting '{a.ref}' v{ver}. Pulled to:\n  {dst}\nNow start a FRIENDS-ONLY game on '{w['session']}', then `finish {a.ref}` when done.")


def cmd_finish(a):
    c = _cfg(); w = _world(c, a.ref); rw = _rw(w)
    local = saveinfo and store.latest_local_save(w["local_dir"], w["session"])
    if not local:
        sys.exit(f"No local '{w['session']}' save found in {w['local_dir']} to upload.")
    try:
        ver = rw.push(local, c["user"], w.get("base_version", 0))
    except remote.RemoteError as e:
        sys.exit(f"Upload refused: {e}")
    w["base_version"] = ver; store.save_config(c)
    print(f"Uploaded '{a.ref}' as v{ver} and released the host lock. ({local})")


def build_parser():
    p = argparse.ArgumentParser(prog="openmpsync", description="FOMPS (Funk's OpenMPSync) - Satisfactory host-swap save sync.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set-user"); s.add_argument("name"); s.set_defaults(fn=cmd_set_user)
    s = sub.add_parser("set-server"); s.add_argument("url"); s.set_defaults(fn=cmd_set_server)
    s = sub.add_parser("saves"); s.set_defaults(fn=cmd_saves)
    s = sub.add_parser("create"); s.add_argument("ref"); s.add_argument("--session", required=True); s.add_argument("--server"); s.add_argument("--local"); s.set_defaults(fn=cmd_create)
    s = sub.add_parser("join"); s.add_argument("ref"); s.add_argument("code"); s.add_argument("--session"); s.add_argument("--server"); s.add_argument("--local"); s.set_defaults(fn=cmd_join)
    s = sub.add_parser("list"); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("status"); s.add_argument("ref"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("host"); s.add_argument("ref"); s.set_defaults(fn=cmd_host)
    s = sub.add_parser("finish"); s.add_argument("ref"); s.set_defaults(fn=cmd_finish)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
