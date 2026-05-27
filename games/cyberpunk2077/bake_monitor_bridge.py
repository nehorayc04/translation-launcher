"""
bake_monitor_bridge.py
======================
Bridges the subtitle bake's log into the format the progress monitor reads,
so cp2077_monitor.py (and the website + launcher it feeds) track the bake LIVE.

The bake (rebuild_subtitles_and_pack.py) writes `[N/702] OK ...` lines to
rebuild_subtitles.log. The monitor's cp2077 adapter instead watches
subtitle_batch.log and expects the `[####] X% N/T rate=R/s ETA Hh
(processed=P skipped=S failed=F)` progress line. This bridge tails the bake
log and emits adapter-format lines into subtitle_batch.log every ~90 s, with
a `cp2077_subtitle_batch starting` anchor the adapter keys on. It exits when
the bake logs DONE. Read-only on the bake — touches nothing it depends on.
"""
import os
import re
import time

SD  = os.path.dirname(os.path.abspath(__file__))    # games/cyberpunk2077/
SRC = os.path.join(SD, 'rebuild_subtitles.log')      # the bake writes here
DST = os.path.join(SD, 'subtitle_batch.log')         # the adapter reads here

PROG = re.compile(r'\[(\d+)\s*/\s*(\d+)\]\s+(?:OK|FAIL|SKIP)')


def last_progress():
    """(current, total) from the newest [N/T] line in the bake log."""
    try:
        lines = open(SRC, encoding='utf-8', errors='replace').readlines()[-250:]
    except OSError:
        return None
    for ln in reversed(lines):
        m = PROG.search(ln)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def bake_done():
    try:
        tail = open(SRC, encoding='utf-8', errors='replace').readlines()[-20:]
    except OSError:
        return False
    return any('DONE' in ln for ln in tail)


def emit(msg):
    try:
        with open(DST, 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except OSError:
        pass


def main():
    emit("cp2077_subtitle_batch starting")           # adapter run anchor
    print("[bridge] started — mirroring rebuild_subtitles.log -> "
          "subtitle_batch.log", flush=True)
    t0 = time.time()
    while True:
        p = last_progress()
        if p:
            cur, total = p
            el = max(1.0, time.time() - t0)
            rate = cur / el
            eta = (total - cur) / rate / 3600 if rate > 0 else 0.0
            pct = cur * 100.0 / total if total else 0.0
            fill = min(10, int(pct // 10))
            bar = '#' * fill + '-' * (10 - fill)
            emit(f"[{bar}] {pct:.1f}% {cur}/{total} rate={rate:.3f}/s "
                 f"ETA {eta:.1f}h (processed={cur} skipped=0 failed=0)")
            print(f"[bridge] {cur}/{total} ({pct:.1f}%)", flush=True)
        if bake_done():
            emit("[##########] 100.0% subtitle bake + pack complete")
            print("[bridge] bake done — exiting", flush=True)
            break
        time.sleep(90)


if __name__ == '__main__':
    main()
