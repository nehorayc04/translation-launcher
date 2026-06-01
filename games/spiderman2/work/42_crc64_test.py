"""Test CRC64 against a known path."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "ALERT"))
import dat1lib.crc64

_TABLE = dat1lib.crc64.table
def crc64(s: str) -> int:
    norm = s.lower().replace("\\", "/").encode("utf-8")
    v = 0xC96C5795D7870F42
    for b in norm:
        v = 0xFFFFFFFFFFFFFFFF & ((v >> 8) ^ _TABLE[0xFF & (v ^ b)])
    return (v >> 2) | 0x8000000000000000

# localization/localization_all.localization -> 13715107173940066526
known = 13715107173940066526
print(f'Expected: 0x{known:016X}')
for p in [
    "localization/localization_all.localization",
    "Localization/localization_all.localization",
    "localization\\localization_all.localization",
]:
    h = crc64(p)
    match = "*** MATCH" if h == known else ""
    print(f"  {p!r}  -> 0x{h:016X}  {match}")
