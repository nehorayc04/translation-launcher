"""Back-compat shim — delegates to `python -m progress_monitor --adapter cp2077`.

Default behaviour matches the legacy cp2077_monitor.py: live ANSI multi-stage
dashboard. Pass --no-tui (or --once) for the headless plain-logs path used
by CI / scheduled pushes.
"""
from __future__ import annotations

import os
import sys

# progress_monitor lives in <repo_root>/universal/; we're in <repo_root>/games/<game>/.
_UNIVERSAL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "universal")
if _UNIVERSAL not in sys.path:
    sys.path.insert(0, _UNIVERSAL)

from progress_monitor.adapters.cp2077 import build


def main() -> int:
    once   = '--once'   in sys.argv
    dry    = '--dry-run' in sys.argv
    no_tui = '--no-tui'  in sys.argv
    # tui=True for the default interactive case (cp2077_monitor.bat with no
    # args). once/no-tui drop us to the headless polling path.
    tui = not (once or no_tui)
    build().run(once=once, dry_run=dry, tui=tui)
    return 0


if __name__ == '__main__':
    sys.exit(main())
