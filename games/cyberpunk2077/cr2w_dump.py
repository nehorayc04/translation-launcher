"""Dump CR2W header tables of a localization file so we can verify layout."""
import struct, sys
from pathlib import Path

f = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    r"C:\Users\nc528\סקריפטים\תרגום משחקים\תרגום_משחקים\source\archive\base\localization\en-us\onscreens\onscreens.json")

data = f.read_bytes()
assert data[:4] == b'CR2W', "not CR2W"

def u32(pos): return struct.unpack_from('<I', data, pos)[0]
def u16(pos): return struct.unpack_from('<H', data, pos)[0]
def u64(pos): return struct.unpack_from('<Q', data, pos)[0]

print(f"File: {f.name}  ({len(data):,} bytes)")
print(f"magic   @ 0x00 = {data[0:4]}")
print(f"version @ 0x04 = {u32(0x04)}")
print(f"flags   @ 0x08 = {u32(0x08):#010x}")
print()

# Probe candidate fileSize offsets
for off in (0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x24):
    val = u32(off)
    match = " ← FILE SIZE" if val == len(data) else (f" ← close ({val - len(data):+d})" if abs(val - len(data)) < 100 else "")
    print(f"  u32 @ 0x{off:02X} = {val:>12,}  {val:#010x}{match}")

print()
# Dump first 0x100 bytes as hex to see structure
print("First 0x100 bytes:")
for row in range(0, 0x100, 16):
    hex_part = ' '.join(f'{data[row+i]:02x}' for i in range(16) if row+i < len(data))
    print(f"  {row:04x}: {hex_part}")

print()
# Try to find table-of-tables at 0x28 (after 40-byte header: magic+ver+flags+ts64+buildver+filesize+bufsize+crc32+numchunks)
print("Probing tables[10] at 0x28 (v195 layout):")
for i in range(10):
    tbl = 0x28 + i * 12
    off, cnt, crc = u32(tbl), u32(tbl+4), u32(tbl+8)
    print(f"  table[{i}]: offset={off:#x} ({off:,})  count={cnt}  crc={crc:#010x}")

print()
# Find entries start marker
marker = data.find(b'\x0a\x00\x0b\x00', 0x200)
print(f"First 0a 00 0b 00 @ {marker:#x} ({marker:,})")

# Show what exports table[4] says
tbl4 = 0x28 + 4 * 12
exp_off = u32(tbl4)
exp_cnt = u32(tbl4 + 4)
print(f"\nExports table[4]: offset={exp_off:#x}, count={exp_cnt}")
if 0 < exp_off < len(data) and exp_cnt < 10000:
    for i in range(min(exp_cnt, 20)):
        e = exp_off + i * 24
        if e + 24 > len(data): break
        d_off = u32(e + 8)
        d_sz  = u32(e + 12)
        cls   = u16(e)
        print(f"  export[{i}]: cls={cls}  dataOffset={d_off:#x} ({d_off:,})  dataSize={d_sz:,}")
