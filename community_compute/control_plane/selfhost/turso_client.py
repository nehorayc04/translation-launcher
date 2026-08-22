"""DROP-IN replacement for control_plane/turso/turso_client.py, pointing the
operator tools at the SELF-HOSTED pool instead of Turso.

Same `run(statements)` signature, same return shape — so `cc_seed.py`,
`cc_collect.py` and friends run UNCHANGED. That matters: the QA gate inside
cc_collect.py is the battle-tested part (panel leaks, untranslated text, dropped
game tokens, niqqud, foreign script). Re-implementing it for the new backend
would be the single most likely way to ship a regression, so we swap the
TRANSPORT and leave the logic alone.

    # Turso (the live system)
    cd control_plane/turso  && python cc_collect.py --game X

    # self-hosted (this)
    cd control_plane/turso  && PYTHONPATH=../selfhost python cc_collect.py --game X

Transport is SSH, on purpose: an arbitrary-SQL HTTP endpoint gated only by the
shared DEVICE secret would be a hole, and the operator already has SSH.
"""
from __future__ import annotations

import json
import os
import subprocess

HOST = os.environ.get("CC_SSH_HOST", "root@10.0.0.20")
REMOTE = os.environ.get("CC_REMOTE_EXEC", "python3 /opt/cc-pool/dbexec.py")
SSH_TIMEOUT = int(os.environ.get("CC_SSH_TIMEOUT", "20"))


def run(statements):
    """statements: list of (sql, [args]) OR bare sql str.
    Returns list of {cols, rows, affected} — identical to the Turso client."""
    payload = {"statements": [list(s) if not isinstance(s, str) else s for s in statements]}
    p = subprocess.run(
        ["ssh", "-o", f"ConnectTimeout={SSH_TIMEOUT}", "-o", "BatchMode=yes", HOST, REMOTE],
        input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True,
        encoding="utf-8", timeout=300)
    if p.returncode != 0:
        detail = (p.stdout or p.stderr or "").strip()[:400]
        raise SystemExit(f"self-hosted SQL failed: {detail}")
    try:
        data = json.loads(p.stdout)
    except Exception:
        raise SystemExit(f"self-hosted SQL: unparseable reply: {p.stdout[:300]}")
    if "error" in data:
        raise SystemExit(f"self-hosted SQL error: {data['error'][:400]}")
    return data["results"]


if __name__ == "__main__":
    print("self-hosted pool OK:", run(["SELECT 1 AS ok"])[0]["rows"])
