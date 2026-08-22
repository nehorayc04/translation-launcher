"""
Dump ALL oasis (id, Arabic-text) pairs from a running FarCry6.exe (read-only).
Writes progress + result to the path given as argv[1].
The oasis VALUES live in RAM as: [u32 id][utf16le string]\0\0  repeated.
"""
import sys, re, struct, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc6_memdump as M

OUT = sys.argv[1] if len(sys.argv) > 1 else "fc6_full_corpus.json"
LOG = OUT + ".log"


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")


def main():
    pid = M.find_pid()
    if not pid:
        log("GAME NOT RUNNING"); return
    log(f"pid={pid} scanning...")
    h = M.open_proc(pid)
    pat = re.compile(rb'(?:[\x20-\x7e]\x00|[\x00-\xff]\x06){2,400}\x00\x00')
    pairs = {}
    regs = 0; mb = 0; t0 = time.time()
    for base, size in M.regions(h):
        d = M.read(h, base, size)
        if not d:
            continue
        regs += 1; mb += len(d) >> 20
        n0 = len(pairs)
        for m in pat.finditer(d):
            s0 = m.start()
            if s0 < 4:
                continue
            body = m.group()[:-2]
            try:
                s = body.decode('utf-16-le')
            except Exception:
                continue
            if not any(0x0600 <= ord(x) <= 0x06ff for x in s):
                continue
            idv = struct.unpack_from('<I', d, s0 - 4)[0]
            if 0 < idv < 0x00ffffff:
                pairs.setdefault(idv, s)
        if len(pairs) > n0:
            log(f"  region {base:#x} (+{len(d)>>20}MB) -> total {len(pairs)} pairs")
    import json
    json.dump({f"{i:#08x}": s for i, s in sorted(pairs.items())},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    lens = sorted(len(s) for s in pairs.values())
    log(f"DONE: {regs} regions, ~{mb} MB, {len(pairs)} unique pairs in {time.time()-t0:.0f}s")
    if lens:
        log(f"len min/med/max {lens[0]}/{lens[len(lens)//2]}/{lens[-1]}  >60ch={sum(1 for x in lens if x>60)}")


if __name__ == "__main__":
    main()
