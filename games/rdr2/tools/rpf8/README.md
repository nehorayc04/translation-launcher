# `rpf8` — standalone RDR2 RPF8 archive extractor

A command-line tool that reads, decrypts and unpacks **Red Dead Redemption 2's `.rpf`
archives** — including the nested archives inside them — with **no OpenIV, no GUI and no
screen/mouse automation**. Built 2026-08-06.

```
bin\rpf8.exe info    <archive.rpf>
bin\rpf8.exe list    <archive.rpf>
bin\rpf8.exe names   <archive.rpf>                     # dump the decrypted name table
bin\rpf8.exe du      <archive.rpf | folder>            # exact unpacked size, writes nothing
bin\rpf8.exe probe   <archive.rpf> [hash]              # why did one entry fail? dump its decrypt plan
bin\rpf8.exe extract <archive.rpf> <outdir> [--recursive]
bin\rpf8.exe unpack  <folder> [--inplace] [--dry-run]  # every .rpf -> a folder of the same name
bin\rpf8.exe namedb  <game folder> [names.txt]         # build the hash->path database
```

`bin\` is self-contained (.NET 8 embedded) — copy the whole folder anywhere. Keep
`oo2core_5_win64.dll` beside `rpf8.exe`; `names.txt` is optional and only improves naming.

## The format (verified byte-for-byte against all 24 shipping archives)

```
0x000  u32 magic 'RPF8' (0x52504638, reads "8FPR" in a hex dump)
0x004  i32 entryCount
0x008  i32 namesLength
0x00C  u16 decryptionTag     0xFF = the TOC is NOT encrypted
0x00E  u16 platformId        'y' (121) = PC, 'o' (111) = PS4
0x010  256-byte RSA signature
0x110  entryCount * 24-byte entries      <- encrypted when tag != 0xFF
 ...   file bodies, laid out contiguously
EOF-namesLength   NUL-separated path table
```

Entry = 3 little-endian u64:

| field | bits |
|---|---|
| `hash` (JOAAT of the path) | Val1 0..31 |
| `encryptionConfig` (strided-cipher layout) | Val1 32..39 |
| `encryptionKeyId` (0xFF = not encrypted) | Val1 40..47 |
| `fileExtId` | Val1 48..55 |
| `isResource` / `isSignatureProtected` | Val1 56 / 57 |
| `onDiskSize` (<< 4) | Val2 0..27 |
| `offset` (<< 4) | Val2 28..58 |
| `compressorId` (0 none, 1 deflate, 2 Oodle) | Val2 59..63 |
| `originalSize` / resource flags | Val3 |

## Encryption

The cipher is **TFIT** — a white-box block cipher in CBC mode, *not* plain AES with an
extractable key. The PC variant (`Tfit2`) is 17 rounds over 16-byte blocks driven by
per-round mask/lookup tables plus a per-tag key; the key material only exists baked into
those tables. Ciphers and tables come from the open-source
[`lazenes/RPF8_TOOL`](https://github.com/lazenes/RPF8_TOOL); the container reader, name
resolution and the whole CLI are ours.

Two properties matter in practice:

* Only **whole 16-byte blocks** are transformed (`len & ~15`); the trailing remainder stays
  in the clear. That is why fragments like `pack/row` and `ifest_tu.xml` are readable in
  the raw name table of an encrypted archive.
* File bodies are only **partially** encrypted — `StridedCipher` covers a head, a strided
  set of blocks and a 1 KB tail, selected by the entry's `encryptionConfig`.

### 🔴 A real bug was fixed in the imported ciphers

Both `TfitCbcCipher.Decode` and `Tfit2CbcCipher.Decode` as published write the CBC result
to `input[j]` instead of `input[i + j]` — correct for the first block only, and silent
corruption for every block after it. Fixed in `src/Core/*.cs`; the fix is what makes a
multi-block TOC decrypt.

## Names

Entries reference paths only by JOAAT hash, and the in-archive name table of an
**encrypted** archive cannot be recovered with the TOC key — verified by brute-forcing
every key tag in the container against it, and consistent with OpenIV shipping its own
external name database. Names therefore come from:

* the name table of any archive whose TOC is unencrypted (`shaders_x64.rpf`), and
* `namedb`, which harvests real archive paths out of the game's own **RPFC / `pfm.dat`**
  mount cache inside `appdata0_update.rpf`.

Anything unresolved is written as `0x<HASH>.<ext>` — extraction is unaffected.

## 🔴 Two bugs that only a full run exposed

**1. Oodle `fuzzSafe=NO` crashes the whole process.** A malformed entry made the native
`OodleLZ_Decompress` read past its buffer → `AccessViolationException` → the entire unpack
died mid-run (exit 139) after 2,014 archives. That is a **corrupted-state exception: .NET
cannot catch it**, so wrapping the extractor in `try/catch` does nothing. The only fix is to
stop Oodle running off the buffer — `fuzzSafe=YES` plus 64 bytes of output slack. Verified
byte-identical output on a known-good archive (45 files, 64,225,212 bytes), so it costs
nothing.

**2. The 256-byte "signature" is not always a leading header.** Every one of the 461 entries
in `data_0/data/ui/screens.rpf` sets `IsSignatureProtected`, and skipping 256 bytes at the
front makes **all 461 fail**; not skipping decodes them **461/461, 0 errors**. `GetFile` now
tries the documented layout first and retries without the leading skip — a fallback, not a
replacement, so archives that already decoded keep decoding.

## 🔒 Nothing is ever lost to a failed decode

Three rules, all added after a real incident where a single bad entry silently cost a file:

* **A source archive is deleted only when EVERY entry extracted.** A per-entry failure marks
  the archive `PARTIAL` and the `.rpf` stays on disk. (`--inplace` used to delete regardless,
  so one codec failure destroyed the only copy of that file.)
* **A failed entry is still written out**, as `<name>.rpf8raw` — the decrypted but
  undecodable bytes. The archive's data is preserved byte-for-byte even when the codec
  refuses it.
* **Kept archives are listed at the end** and excluded from later rounds, so a partial
  archive can never make the round loop spin forever.

## Known undecodable entry (1 of ~490,000)

`levels_1 → 0x2A9BF706.rpf → 0xAEB90D10.ydr` fails `Oodle decompress failed (0 != 1400912)`.
`probe` establishes what it is and is not:

| test | result |
|---|---|
| decrypt correct? | yes — undecrypted input fails at every size, decrypted decodes fine |
| how much decodes? | **1,310,720 of 1,400,912 bytes (93.6 %)** — exactly 5 × 256 KB Oodle blocks |
| input truncated? | no — 5 blocks consume 479,856 of 524,752 bytes, so 44,896 remain for the last one |
| is the declared size wrong? | no — a 16-aligned sweep of every possible final-block size decodes at none of them |
| is part of the tail still encrypted? | no — decrypting it *breaks* the 5 blocks that currently work |
| split into 512 KB compressed pieces? | no — a piece boundary at `chunk_size` stalls at the same place |
| independent streams packed back-to-back? | no — nothing decodes at the byte right after the first stream |
| a second stream anywhere in the tail? | no — **every** 16-aligned offset in the remaining 44,896 bytes was tried |

Every failure shares one signature: a **compressed size just above `chunk_size` (524,288)** —
524,752 and 524,336 — so it is a narrow, systematic edge case, not random corruption. But no
packing rule explains the missing bytes, so the final partial block is genuinely unrecoverable
with this codec. It is salvaged as `.rpf8raw` and its archive is kept. **The reference
implementation fails identically** — the `DecodeBlock`/`StridedCipher` port is
character-for-character the same. Affected: ~4 entries in ~490,000 (0.0008 %).

## Validation

| check | result |
|---|---|
| `shaders_x64.rpf` (unencrypted TOC, control) | 4/4 entries, real names, exact contiguous layout |
| `common_0.rpf` (encrypted, tag 10) | 1586 entries, **1585/1585 contiguous chain**, ends exactly at the name table |
| `appdata0_update.rpf` (encrypted, tag 68) | XML manifest and RPFC cache extract intact |
| `levels_0.rpf` **recursive** | 11 archives (10 nested, 11 different key tags) → **20,143 files, 1.6 GB, 0 errors, 42 s** |

## ⚠ Disk space — measure it, don't guess it

`rpf8 du` answers this exactly, reading only TOCs and writing nothing (validated: it
reproduces `levels_0`'s real extraction to the byte and the file, in 2 s instead of 42 s).

**Never estimate the cost from one archive's ratio.** The measured ratios span
**×1.00 → ×5.44** — audio (`.awc`) and video are already compressed and don't grow at all,
while `textures_*` explode. And a *first-level* sum is worse than useless here: it reports
**×1.01**, because the big archives hold nested archives stored **uncompressed**, so all
the growth is one level down. Only a recursive walk is honest.

Measured on the full shipping game (2026-08-07):

| | |
|---|---|
| archives | **119.14 GB** — 89 top-level, **4,960** including nested |
| unpacked | **225.73 GB** — **488,721** files |
| ratio | **×1.89** |
| net growth with `--inplace` | **+106.6 GB** |

`unpack` computes each archive's exact cost from its TOC (a round extracts one level, so
the cost *is* the sum of that archive's entry sizes) and skips it when the volume can't
take it — rather than filling the disk and leaving a half-written tree. Sources are deleted
only after their replacement folder is complete, so peak usage ≈ the final total.
