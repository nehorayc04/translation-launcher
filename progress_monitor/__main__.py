"""CLI runner: python -m progress_monitor --adapter cp2077 [--once] [--dry-run]"""
from __future__ import annotations

import argparse
import importlib
import logging
import sys


def main() -> int:
    p = argparse.ArgumentParser(prog='progress_monitor')
    p.add_argument('--adapter', required=True,
                   help='dotted path of an adapter module exposing build() -> Monitor')
    p.add_argument('--once',    action='store_true', help='single tick then exit')
    p.add_argument('--dry-run', action='store_true', help='log what would be pushed; no HTTP')
    p.add_argument('-v', '--verbose', action='store_true')
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    try:
        mod = importlib.import_module(f'progress_monitor.adapters.{args.adapter}')
    except ImportError:
        mod = importlib.import_module(args.adapter)
    monitor = mod.build()
    monitor.run(once=args.once, dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    sys.exit(main())
