"""Back-compat shim — delegates to `python -m progress_monitor --adapter cp2077`."""
from __future__ import annotations

import sys

from progress_monitor.adapters.cp2077 import build


def main() -> int:
    once = '--once' in sys.argv
    dry  = '--dry-run' in sys.argv
    build().run(once=once, dry_run=dry)
    return 0


if __name__ == '__main__':
    sys.exit(main())
