"""Minimal Turso (libSQL) HTTP client over /v2/pipeline — reused by the cc
operator tools. Reads creds from env CC_TURSO_URL/CC_TURSO_TOKEN, falling back
to the pool creds stashed in the scratchpad (cc lives in isolated cc_* tables
on the same Turso DB as the /translate pool; a dedicated cc DB is a trivial
later swap — just point these two at it)."""
import json, os, urllib.request, urllib.error

_SCRATCH = os.environ.get(
    "CC_SCRATCH",
    r"C:\Users\NEHORA~1\AppData\Local\Temp\claude\c--Users-Nehoray-Cohen-Projects-Game-translator\e3f5c3b9-e948-4d52-888f-12c32af3deee\scratchpad",
)


def _cred(name, fallback_file):
    v = os.environ.get(name)
    if v:
        return v.strip()
    p = os.path.join(_SCRATCH, fallback_file)
    if os.path.exists(p):
        return open(p, encoding="utf-8").read().strip()
    raise SystemExit(f"missing {name} (and {p})")


URL = _cred("CC_TURSO_URL", "turso_url.txt").rstrip("/")
TOKEN = _cred("CC_TURSO_TOKEN", "turso_token.txt")


def _arg(v):
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    return {"type": "text", "value": str(v)}


def _cell(c):
    t = c.get("type")
    if t == "null":
        return None
    if t == "integer":
        return int(c["value"])
    if t == "float":
        return float(c["value"])
    return c.get("value")


def run(statements):
    """statements: list of (sql, [args]) OR bare sql str. Returns list of
    result dicts {cols, rows, affected}."""
    reqs = []
    for st in statements:
        sql, args = (st, []) if isinstance(st, str) else (st[0], st[1] or [])
        reqs.append({"type": "execute", "stmt": {"sql": sql, "args": [_arg(a) for a in args]}})
    reqs.append({"type": "close"})
    body = json.dumps({"requests": reqs}).encode()
    req = urllib.request.Request(
        URL + "/v2/pipeline", data=body,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    try:
        raw = urllib.request.urlopen(req, timeout=60).read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Turso HTTP {e.code}: {e.read().decode()[:400]}")
    data = json.loads(raw)
    out = []
    for r in data.get("results", []):
        if r.get("type") == "error":
            raise SystemExit(f"Turso SQL error: {json.dumps(r.get('error'))[:400]}")
        res = r.get("response", {}).get("result", {})
        cols = [c.get("name") for c in res.get("cols", [])]
        rows = [[_cell(c) for c in row] for row in res.get("rows", [])]
        out.append({"cols": cols, "rows": [dict(zip(cols, row)) for row in rows],
                    "affected": res.get("affected_row_count", 0)})
    return out


if __name__ == "__main__":
    print("Turso OK:", run(["SELECT 1 AS ok"])[0]["rows"])
