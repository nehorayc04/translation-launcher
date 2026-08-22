# MSMR — Phase-1 gate: DRM / integrity screen

**Verdict: 🟢 GREEN — modified asset archives are expected to load.**
**The cleanest DRM profile measured in this project to date.**

Scope: read-only investigation. **Nothing under `D:\Games\Spider-man Remastered` was
modified, written or deleted.** Tools written this session (all read-only):
`_gate_drm_scan.py` (PE + string counts), `_gate_drm_ctx.py` (string attribution),
`_gate_drm_imports.py` (import table + cert dir), `_gate_drm_verify.py` (vendor manifest).
Run everything with `./.venv/Scripts/python.exe`.

---

## 0. Headline

`Spider-Man.exe` (121,325,496 B) contains **zero** Denuvo / VMProtect / packer /
anti-cheat markers, is an **ordinary unpacked PE**, and — the decisive fact —
**cannot compute a content hash at all**: it imports `bcrypt.dll` but calls only the
RNG entry points, and never imports `wintrust.dll`. Every "integrity-shaped" string in
the binary was individually attributed to NVIDIA DLSS, Havok physics, D3D12, or a
Mister Negative gameplay mechanic. The `toc` has no digest section to store a hash in.

---

## 1. Anti-cheat DLLs — exhaustive negative

The install is **81 files** (full recursive enumeration). There is **no**
`EasyAntiCheat*`, `BEClient*/BEService*/BattlEye*`, `vgk.sys`, `GameGuard`, or any
Denuvo runtime anywhere in the tree.

DLLs present (all accounted for): `amd_ags_x64`, `bink2w64`, `crs-client`,
`d3dcompiler_47`, `D3D12Core`, `ffx_fsr2_api_*` (FSR2), `gattaca`,
`GFSDK_SSAO_D3D11`, `liblipsync_tltb64`, `nvngx_dlss`, `steam_api64`,
`steamclient64`, `XAudio2_7`. `crs-client.dll` + `crs-handler.exe` = the
**crash-reporting service**, corroborated by `NOTICE` (below).

This is a single-player title; no anti-cheat is expected and none is present.

---

## 2. PE layout — unpacked, entry point in `.text`

```
machine=0x8664  magic=0x20B  sections=12  SizeOfImage=139,841,536  EntryRVA=0x35ED980

name           VirtSize      RawSize      VAddr  flags                     entropy
.text        58,308,108   58,308,608       1000  EXEC|READ|CODE               6.52  <== ENTRY
BINK              3,768        4,096    379D000  EXEC|READ|CODE               5.47
.rdata       39,076,164   39,076,352    379E000  READ|IDATA                   5.23
.data        34,195,656   15,705,088    5CE3000  READ|WRITE|IDATA             3.06
.pdata        4,183,368    4,183,552    7D80000  READ|IDATA                   7.20
BINKDATA              4          512    817E000  READ|WRITE|IDATA             0.02
BINKCONS            238          512    817F000  READ|IDATA                   3.00
UserSyst              4          512    8180000  READ|WRITE|IDATA             0.00
minATL               24          512    8181000  READ|IDATA                   0.00
_RDATA          140,548      140,800    8182000  READ|IDATA                   6.03
.rsrc         1,691,704    1,692,160    81A5000  READ|IDATA                   4.61
.reloc        2,201,788    2,202,112    8343000  READ|IDATA|DISCARD           5.47
```

Read against this project's three packing tells:

| tell | packed signature (Anno 1800) | MSMR | verdict |
|---|---|---|---|
| entry point section | exotic (`.xtls`) | **`.text`** | clean |
| huge RWX section | 320 MB `.text1` RWX | `.text` is **EXEC\|READ, not writable** | clean |
| `.reloc` vs image | ~12 KB / 411 MB = 0.003 % | **2,201,788 B / 139.8 MB = 1.574 %** | **unpacked** |

`.text` entropy **6.52** and `.rdata` **5.23** are normal compiled x86-64; encrypted/packed
code sits at ~7.9+. Section names are all stock (the `BINK*` ones are Bink video, `minATL`
is the ATL runtime). **The exe is fully statically analyzable** — which is exactly why the
string mining below is trustworthy.

**Packer/DRM needles — 0 hits in BOTH UTF-8 and UTF-16LE:**
`Denuvo`, `denuvo`, `DENUVO`, `VMProtect`, `vmprotect`, `.vmp0`, `.vmp1`, `.vmp2`,
`.xtls`, `Themida`, `WinLicense`, `UPX0`, `UPX1`, `Enigma`, `ASProtect`, `SecuROM`,
`SafeDisc`, `Arxan`.

---

## 3. Integrity strings — counted **and individually attributed**

A count alone proves nothing, so every hit was resolved to its surrounding string.
Exact occurrence counts (not ripgrep line counts), UTF-8 + UTF-16LE:

| needle | count | what it actually is |
|---|---:|---|
| `SHA256` | **2** | `Symantec Class 3 SHA256 Code Signing CA` / `… - G2` — entries in **NVIDIA's NGX/DLSS certificate-name table** |
| `sha256` / `SHA-256` / `SHA512` / `sha1` | 0 | — |
| `integrity` | 2 | `integritySystem`, `integrityType` — gameplay data field names |
| `Integrity` | 2 | `ancesterIntegrityUid`, `hkdIntegrityAnalyzerAction` — **Havok Destruction** (`hkd` prefix; "ancester" is Havok's own well-known typo) |
| `tamper` / `Tamper` / `TAMPER` | **0** | — |
| `checksum` / `CRC32` / `md5` / `MD5` | **0** | — |
| `Signature`/`signature`/`SIGNATURE` | 30 | **D3D12 Root Signature / Command Signature** (`CreateRootSignature`, `D3D12SerializeVersionedRootSignature`), Scaleform `XMLSignatureValidator`, and `Too many bytes for PNG signature` |
| `WinVerifyTrust` | 1 | a name string only — **`wintrust.dll` is NOT imported** (§4), resolved dynamically by NVIDIA NGX |
| `Corrupt` / `corrupt` | 79 distinct | **Mister Negative's "Corruption" mechanic**: `MrNeg_Corruption`, `NegativeCorruptionSystem`, `CorruptedBot`, `CorruptedMale1-5`, `OnPedestrianCorruptedAmbush`, `UIHudCorruptionAction` |

The NVIDIA attribution is substantiated, not asserted — the CA names sit in a contiguous
block with `NVIDIA Subordinate CA`, `NVIDIA Corporation-PE-Prod-Sha2`,
`DigiCert SHA2 Assured ID Code Signing CA`, immediately after
`NGXLoadCoreLibrary` / `nvsdk_ngx_lib_windows.cpp` / `NVidia Complete Version r510_00`.
Counts: `NGX` ×53, `nvngx` ×2. That machinery verifies **`nvngx_dlss.dll`** — NVIDIA
checking its own DLL — and has no relationship to `asset_archive/`.

Havok attribution likewise: `hknp` ×1054, `hkb` ×98, `hkd` ×48, `Havok` ×29.

---

## 4. 🔑 The structural proof — the binary cannot hash anything

Import table (23 DLLs): `ADVAPI32`, `amd_ags_x64`, **`bcrypt`**, `dbghelp`, `faultrep`,
`GDI32`, `GFSDK_SSAO_D3D11`, `HID`, `IPHLPAPI`, `KERNEL32`, `MFPlat`, `MFReadWrite`,
`ole32`, `OLEAUT32`, `pdh`, `SETUPAPI`, `SHELL32`, `steam_api64`, `USER32`, `UxTheme`,
`WINHTTP`, `WINMM`, `WS2_32`.

**`wintrust.dll` is absent** → no static Authenticode verification path.

What `bcrypt.dll` is used for:

```
BCryptOpenAlgorithmProvider    1
BCryptGenRandom                1     <-- RNG
BCryptCloseAlgorithmProvider   1
BCryptCreateHash               0
BCryptHashData                 0
BCryptFinishHash               0
BCryptDestroyHash              0
CryptAcquireContext            0
CryptCreateHash                0
CryptHashData                  0
CertGetCertificateChain        0
CryptCATAdminCalcHashFromFileHandle 0
```

**BCrypt is opened purely as a random-number source.** There is not a single
hash-computation API in the binary. This is a *structural* argument, not a statistical
one: even if a content-hash gate were desired, the exe has no Windows crypto path to
implement it, and `NOTICE` (§5) shows no bundled crypto library either.

---

## 5. Third-party libraries — no crypto shipped

`NOTICE` lists exactly four: **Crashpad**, **cpp-httplib**, **mini-chromium**, **Zlib** —
i.e. a crash-reporting stack (matching `crs-client.dll` / `crs-handler.exe`) plus zlib.
**No OpenSSL, mbedTLS, libtomcrypt, Botan or any hashing library is bundled.**

---

## 6. The container has nowhere to put a hash

`asset_archive/toc` parses with the vendored `dat1lib` (which declares
`VERSION_MSMR = 202200`) into exactly **6 sections**:

```
ArchivesSection   0x398ABFF0     AssetIdsSection  0x506D7B8A
SizesSection      0x65BCF461     KeyAssetsSection 0x6D921D7B
OffsetsSection    0xDCD720B5     SpansSection     0xEDE8ADA9
```

It is a pure address book — ids → (archive, offset, size). **There is no digest,
signature or checksum section**, so the index format cannot carry a content hash even in
principle. This is the same 6-section shape the sibling SM2 uses, where
`translation_manager/spiderman2_mod.py` already ships a working index-redirect deploy
(append archive + rewrite `SizesSection`/`ArchivesSection`).

---

## 7. Authenticode — and why it *confirms* the verdict

```
Status        : Valid
StatusMessage : Signature verified.
Signer        : CN=Sony Interactive Entertainment LLC, O=Sony Interactive Entertainment LLC, ...
```

`Spider-Man.exe` is the **unmodified retail Sony binary** (cert dir 9,144 B at
0x73B2400). The crack is entirely in `steam_api64.dll` (FLT Steam-emu). Two consequences:

1. The DRM posture measured above **is the retail posture** — not a repack artifact.
   The retail Sony/Nixxes PC port genuinely ships without Denuvo.
2. The game boots with a substituted `steam_api64.dll` and an untouched exe, i.e. it
   performs no self-verification of its own module set.

---

## 8. Baseline is proven pristine

`_Redist/fitgirl.md5` is a **vendor manifest** of 54 entries covering every file we would
ever touch (`toc`, `dag`, `g00s000`–`g00s033`, `a00s034.us`, the exe, the DLLs).

```
vendor manifest: OK=54  MISMATCH=0  MISSING=0
```

Per [[verify-artifact-against-vendor-manifest]] this is the right starting point: any
future "does a modified archive load?" experiment begins from a **byte-verified clean**
install, so a failure can never be blamed on a pre-existing corrupt file.

⚠️ **Note for a future session:** modifying any archive will make `fitgirl.md5`/QuickSFV
report a mismatch. That is the **repack's** verification tool, **not a game gate** —
do not misread a QuickSFV failure as an in-game integrity error.

---

## 9. Comparison against the project's calibrated priors

| title | SHA256 | integrity | tamper | outcome |
|---|---:|---:|---:|---|
| AC Black Flag Resynced | 143 | 5 | 11 | 🔴 **BLOCKED** by a content-hash gate |
| Corsair Cove (UE5) | 136 | 4 | 0 | 🟢 clean (stock UE crypto strings) |
| Crimson Desert | 23 | 2 | 1 | 🟢 clean |
| AC Shadows | 11 | – | 3 | 🟢 mods load (live Nexus scene) |
| **Spider-Man Remastered** | **2** | **4** | **0** | 🟢 **cleanest measured** |

MSMR has the **lowest `SHA256` count of any title screened in this project**, and unlike
every entry above, each of its hits has been positively attributed to a non-integrity
subsystem.

---

## 10. Empirical corroboration (the strongest signal there is)

Per the playbook, a live third-party mod scene beats any static analysis:

- `dat1lib` — the library this repo already vendors at
  `games/spiderman2/tools/ALERT` — **explicitly declares `VERSION_MSMR = 202200`**.
- **Overstrike**, built on dat1lib, was originally written *for* Marvel's Spider-Man
  Remastered; MSMR has the largest modding scene of the three Insomniac PC ports.
- This repo's own `translation_manager/spiderman2_mod.py` performs the identical
  index-redirect deploy on the **sibling** title (same 6-section toc), and that mod is
  shipped and published. MSMR is the *older, less protected* title in that family.

---

## 11. One caveat (disclosed, not a blocker)

`_SSE Fix/peterpider.dll` **is genuinely packed**: sections `RIN0` (376 KB, RWX,
`RawSize=0`) and `RIN1` (entropy **7.98**, RWX, holds the entry point), **no `.reloc`**.

It is, however, **third-party, opt-in and currently inactive**:
- root `amd_ags_x64.dll` md5 `00d9c1f1485c9c965c53f1aa5448412b` **matches the vendor
  manifest** → it is the original AMD DLL, not the fix's proxy;
- `peterpider.dll` is **absent from the game root**.

It is a community CPU-instruction-set workaround, not game DRM. Flagged as a
supply-chain observation only. Scans of the real game modules — `gattaca.dll`,
`crs-client.dll`, `steam_api64.dll` — returned **0 packer / 0 anti-cheat** and are all
ordinary unpacked PEs.

---

## 12. Verdict

**🟢 GREEN.** Modified asset archives are expected to load. There is no Denuvo, no
VMProtect, no anti-cheat, no packing, no content hashing capability, no digest section
in the container, and a mature third-party modding ecosystem that already writes these
exact archives.

**There is nothing here to defeat — and defeating an integrity or anti-tamper mechanism
is explicitly OUT OF SCOPE for this project regardless.** Had this screen come back
🔴 (as AC Black Flag Resynced did), the correct response would have been to document the
wall and stop, not to work around it.

### Residual unknown (honest)
Static analysis cannot exclude a **hand-rolled** hash implemented inline (a CRC/FNV loop
compiled into `.text` would emit no API string). Two things make that very unlikely and
both are cheap to settle later:
- the `toc` has no field to *store* such a digest (§6);
- the definitive test is empirical and belongs to the deploy gate — a single
  index-redirect proof build, which the sibling SM2 applier already performs successfully
  on the same engine.

Note also that the engine's own use of **crc64 for asset-path ids** is *addressing*, not
verification — do not mistake it for an integrity mechanism.
