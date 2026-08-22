#!/usr/bin/env python3
"""
Run an operator tool (cc_seed / cc_collect / ...) against the SELF-HOSTED pool.

WHY THIS EXISTS — a real incident, caught during the pre-migration audit:

    cd control_plane/turso && PYTHONPATH=../selfhost python cc_seed.py corpus.json

looks like it targets the self-hosted pool. It does NOT. Python puts the
SCRIPT'S OWN directory at sys.path[0], ahead of everything in PYTHONPATH, so
`import turso_client` inside turso/cc_seed.py always resolves to
turso/turso_client.py — the LIVE Turso client. The seed reported success and
500 test rows landed in the PRODUCTION database beside the real corpus.

Nothing warned, because both backends are valid and both replies look correct.
So the fix is not a docs note — it is this runner, which puts the shim first
and then REFUSES to continue unless the module that actually got imported is
the self-hosted one.

Usage:
    python run.py cc_seed.py corpus.json --game crimson-desert
    python run.py cc_collect.py --game crimson-desert --out out.json
"""
from __future__ import annotations

import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, "..", "turso"))


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    tool = sys.argv[1]
    if not tool.endswith(".py"):
        tool += ".py"
    path = tool if os.path.isabs(tool) else os.path.join(TOOLS, tool)
    if not os.path.exists(path):
        print(f"no such tool: {path}", file=sys.stderr)
        return 2

    # the shim must win over the tool's own directory
    sys.path.insert(0, HERE)
    import turso_client  # noqa: E402

    resolved = os.path.abspath(turso_client.__file__)
    if os.path.dirname(resolved) != HERE:
        print("REFUSING TO RUN — the wrong backend was imported:", file=sys.stderr)
        print(f"  got      {resolved}", file=sys.stderr)
        print(f"  expected {os.path.join(HERE, 'turso_client.py')}", file=sys.stderr)
        return 3

    host = os.environ.get("CC_SSH_HOST", "root@10.0.0.20")
    print(f"[backend] SELF-HOSTED pool  ->  {host}:/opt/cc-pool/cc_pool.db")
    print(f"[tool]    {os.path.basename(path)}\n")

    sys.argv = [path] + sys.argv[2:]
    runpy.run_path(path, run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
