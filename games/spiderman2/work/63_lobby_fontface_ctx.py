import os, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = os.path.join(ROOT, "Game Lab", "Marvel's Spider-Man 2")
buf = open(os.path.join(GAME, "d", "userinterface"), "rb").read()

for off in (74055441, 76022581):
    print("=" * 70)
    print(f"context around @font-face url @ {off}")
    print("=" * 70)
    start = max(0, off - 1200)
    end = min(len(buf), off + 1200)
    for m in re.finditer(rb"[ -~]{4,160}", buf[start:end]):
        print(f"  [{start+m.start():>9}] {m.group().decode('latin-1')!r}")
    print()
