"""One-shot multi-term bundle-name search across multiple .toc files (efficient: decodes
each file's bundle table once, then greps in-memory for every term)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bf6_toc import TocFile  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: bf6_bundle_grep.py <term1,term2,...> <file.toc> [more.toc ...]")
        return 1
    terms = [t.lower() for t in argv[0].split(",")]
    for p in argv[1:]:
        t = TocFile.read(p)
        print(f"=== {t.summary()} ===")
        for term in terms:
            hits = [b for b in t.bundles if b.name and term in b.name.lower()]
            if hits:
                print(f"  -- '{term}': {len(hits)} hits --")
                for b in hits[:30]:
                    print(f"     [{b.index:5d}] size={b.size:>10d}  {b.name}")
                if len(hits) > 30:
                    print(f"     ... +{len(hits)-30} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
