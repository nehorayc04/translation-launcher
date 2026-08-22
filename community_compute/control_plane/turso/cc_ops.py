"""Device-side client for the /cc/* Worker endpoints — the reference the
Android/desktop apps mirror when they repoint from Supabase RPCs to Turso.
Reads CC_BASE/CC_SECRET/CC_ADMIN_SECRET from .cc_env (or env)."""
import json, os, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))


def _envfile():
    d = {}
    p = os.path.join(HERE, ".cc_env")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                d[k] = v
    return d


_E = _envfile()
BASE = (os.environ.get("CC_BASE") or _E.get("CC_BASE", "")).rstrip("/")
SECRET = os.environ.get("CC_SECRET") or _E.get("CC_SECRET", "")
ADMIN = os.environ.get("CC_ADMIN_SECRET") or _E.get("CC_ADMIN_SECRET", "")
UA = "Mozilla/5.0 (cc-ops)"  # a real UA (Cloudflare 1010 blocks default urllib)


def call(op, body=None, admin=False, method="POST"):
    url = f"{BASE}/{op}"
    data = json.dumps(body or {}).encode() if method == "POST" else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json",
        "x-cc-secret": ADMIN if admin else SECRET,
        "User-Agent": UA,
    })
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        return {"_http": e.code, "_body": e.read().decode()[:300]}


# --- device routes ---
def enroll(w, platform="app"): return call("enroll", {"worker": w, "platform": platform})
def claim(w):                  return call("claim", {"worker": w})
def renew(w):                  return call("renew", {"worker": w})       # the cheap 1-write heartbeat
def submit(w, out):            return call("submit", {"worker": w, "out": out})
def release(w):                return call("release", {"worker": w})
def stats():                   return call("stats")


# --- operator routes ---
def get_config():              return call("config", method="GET")
def set_config(**kv):          return call("config", {"set": kv}, admin=True)
def block(w):                  return call("block", {"worker": w}, admin=True)
def unblock(w):                return call("unblock", {"worker": w}, admin=True)


if __name__ == "__main__":
    import sys
    print(json.dumps(call(sys.argv[1] if len(sys.argv) > 1 else "stats",
                          admin="--admin" in sys.argv,
                          method="GET" if "--get" in sys.argv else "POST"),
                     ensure_ascii=False, indent=2))
