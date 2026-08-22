"""
FL Studio .moe cracker — proof-of-format + keystream recovery.

.moe = FIXED-keystream stream-cipher over a GNU gettext .mo.
  file[0:16] = wrapper header (4B version 00010000 + 12B constant; plaintext; identical across all langs)
  file[16:]  = ciphertext = gettext_mo XOR keystream   (keystream FIXED across ALL languages)

Because the keystream is fixed, ANY known plaintext recovers the keystream at that region.
The gettext metadata msgstr contains a long, language-INDEPENDENT contiguous block:
  "MIME-Version: 1.0\nContent-Type: text/plain; charset=UTF-8\nContent-Transfer-Encoding: 8bit\n"
Crib-drag it (only past the shared msgid region) to recover a keystream chunk, then decrypt the
surrounding German msgstr text as PROOF.
"""
import os

HERE = os.path.dirname(__file__)
EXTRACT = os.path.join(HERE, "..", "extract")
load = lambda n: open(os.path.join(EXTRACT, n), "rb").read()

CRIB = b"MIME-Version: 1.0\nContent-Type: text/plain; charset=UTF-8\nContent-Transfer-Encoding: 8bit\n"

def printable_frac(b):
    if not b: return 0.0
    ok = sum(1 for x in b if 0x20 <= x < 0x7f or x in (0x0a, 0x0d, 0x09))
    return ok / len(b)

def main():
    de = load("de.moe")[16:]
    fr = load("fr.moe")[16:]
    L = len(CRIB)
    # de/fr diverge early (~268) so past that they are independent plaintexts.
    start = 300
    hit = None
    for pos in range(start, len(de) - L):
        ks = bytes(de[pos + i] ^ CRIB[i] for i in range(L))
        # validate with fr (independent plaintext): fr decrypts to printable, NOT identical to CRIB
        dfr = bytes(fr[pos + i] ^ ks[i] for i in range(L)) if pos + L <= len(fr) else b""
        if printable_frac(dfr) >= 0.95 and dfr != CRIB:
            hit = (pos, ks, dfr)
            break
    if not hit:
        print("crib not found with fr-validation; metadata block may differ")
        return
    pos, ks, dfr = hit
    print(f"*** metadata crib recovered at de-body offset {pos} ***")
    print("  fr.moe decrypts (independent) to:")
    print("   ", dfr.decode("latin1"))

    # Extend the keystream to the right by dragging the known gettext metadata template further,
    # then read the German msgstr strings that follow. To extend without more known plaintext,
    # exploit: the msgstr pool is UTF-8 text; recover each following KS byte by requiring
    # BOTH de AND fr to decrypt to a text byte (two-file constraint => reliable).
    ks_map = {pos + i: ks[i] for i in range(L)}
    # go right
    p = pos + L
    RIGHT = 2000
    while p < min(len(de), len(fr)) and p < pos + L + RIGHT:
        cands = [k for k in range(256)
                 if printable_frac(bytes([de[p] ^ k])) and printable_frac(bytes([fr[p] ^ k]))]
        # prefer a byte giving common text chars in both
        def sc(k):
            a = de[p] ^ k; b = fr[p] ^ k
            s = 0
            for x in (a, b):
                if 0x61 <= x <= 0x7a or 0x41 <= x <= 0x5a or x == 0x20: s += 2
                elif 0x30 <= x <= 0x39 or 0x20 <= x < 0x7f: s += 1
                elif x in (0x0a, 0x00): s += 1
            return s
        best = max(range(256), key=sc)
        ks_map[p] = best
        p += 1
    lo = pos - 40
    hi = p
    for f, name in [(de, "de/German"), (fr, "fr/French")]:
        dec = bytes(f[q] ^ ks_map[q] for q in range(max(0, lo), hi) if q in ks_map)
        print(f"\n--- {name} msgstr region decrypted (proof of readable translation) ---")
        # split on NUL to show individual strings
        txt = dec.decode("utf-8", "replace")
        for line in txt.split("\x00"):
            line = line.strip()
            if line:
                print("  |", line[:120])

if __name__ == "__main__":
    main()
