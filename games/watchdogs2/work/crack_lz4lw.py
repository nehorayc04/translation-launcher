"""Experiment: crack the Disrupt 'LZ4LW' framing used by WD2 oasisstrings.
Raw sample: arabic oasisstrings, compressed=1,846,055 -> uncompressed=5,061,841."""
import struct, sys
import lz4.block as lb

RAW = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\raw_oasis\languages\arabic\oasisstrings.rml"
UNCOMP = 5061841
data = open(RAW, "rb").read()
print(f"compressed file size = {len(data)}  expected uncompressed = {UNCOMP}")
print("head hex:", data[:48].hex(" "))

def ok(b):  # quick sanity: rml/oasis text should start with bytes we can sniff
    return b[:16]

# H1: whole blob = one raw LZ4 block
try:
    out = lb.decompress(data, uncompressed_size=UNCOMP)
    print("H1 whole-block OK len", len(out), "head", out[:16].hex(" "))
    sys.exit(0)
except Exception as e:
    print("H1 fail:", str(e)[:120])

# H2: skip 4-byte header, rest = one LZ4 block
for hdr in (4, 8, 12, 16):
    try:
        out = lb.decompress(data[hdr:], uncompressed_size=UNCOMP)
        print(f"H2 skip{hdr} OK len", len(out), out[:16].hex(" ")); sys.exit(0)
    except Exception as e:
        print(f"H2 skip{hdr} fail:", str(e)[:80])

# H3: chained blocks. Each block: [u32 compressedSize] then LZ4 block of fixed
# uncompressed size (try 64KB and 256KB). LE and BE.
for BS in (0x10000, 0x40000, 0x20000):
    for endian in ("<", ">"):
        for hdrfield in (4,):
            pos = 0; out = bytearray(); blocks = 0; failed = False
            try:
                while pos < len(data) and len(out) < UNCOMP:
                    if pos + hdrfield > len(data): failed=True; break
                    csz = struct.unpack(endian + ("I" if hdrfield==4 else "H"), data[pos:pos+hdrfield])[0]
                    pos += hdrfield
                    if csz == 0 or pos + csz > len(data): failed=True; break
                    usz = min(BS, UNCOMP - len(out))
                    chunk = lb.decompress(data[pos:pos+csz], uncompressed_size=usz)
                    out += chunk; pos += csz; blocks += 1
                if not failed and len(out) == UNCOMP:
                    print(f"H3 BS={BS:#x} {endian} OK blocks={blocks} head={out[:16].hex(' ')}"); sys.exit(0)
            except Exception as e:
                pass
        # print one diag
print("H3 all fail")

# H4: block header = [u32 compressedSize][u32 uncompressedSize] per block
for endian in ("<", ">"):
    pos=0; out=bytearray(); blocks=0; failed=False
    try:
        while pos < len(data) and len(out) < UNCOMP:
            if pos+8 > len(data): failed=True; break
            csz, usz = struct.unpack(endian+"II", data[pos:pos+8]); pos+=8
            if csz==0 or usz==0 or pos+csz>len(data) or usz>0x1000000: failed=True; break
            chunk = lb.decompress(data[pos:pos+csz], uncompressed_size=usz)
            out+=chunk; pos+=csz; blocks+=1
        if not failed and len(out)==UNCOMP:
            print(f"H4 {endian} OK blocks={blocks} head={out[:16].hex(' ')}"); sys.exit(0)
    except Exception as e:
        pass
print("H4 all fail")
print("=> none of the simple hypotheses matched; needs the real LZ4LW spec")
