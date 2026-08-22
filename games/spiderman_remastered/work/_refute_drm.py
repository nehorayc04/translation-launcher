"""INDEPENDENT adversarial re-check of the MSMR DRM gate.
Written from scratch; does NOT read the prior agent's scripts or report.
READ-ONLY on the game folder.
"""
import os, sys, math, hashlib, struct, json, re

GAME = r"D:\Games\Spider-man Remastered"
EXE  = os.path.join(GAME, "Spider-Man.exe")

def enc_all(s):
    """Return the byte forms we search for."""
    return [("utf8", s.encode("utf-8")), ("utf16le", s.encode("utf-16-le"))]

def count_occ(data, needle):
    """Exact non-overlapping occurrence count."""
    n = 0; i = 0
    while True:
        i = data.find(needle, i)
        if i < 0: break
        n += 1; i += 1     # overlapping-safe (count all start positions)
    return n

def entropy(b):
    if not b: return 0.0
    f = [0]*256
    for x in b: f[x] += 1
    n = len(b); e = 0.0
    for c in f:
        if c:
            p = c/n
            e -= p*math.log2(p)
    return e

def main():
    data = open(EXE, "rb").read()
    print(f"EXE size = {len(data):,}")
    print(f"md5      = {hashlib.md5(data).hexdigest()}")
    print(f"sha256   = {hashlib.sha256(data).hexdigest()}")
    print()

    # ---------- KNOWN-POSITIVE CONTROLS (prove the scanner works) ----------
    print("=== CONTROL (must be > 0) ===")
    for s in ["Insomniac", "Spider-Man", "steam_api64", "bcrypt", "Havok", "NGX"]:
        row = []
        for lbl, nb in enc_all(s):
            row.append(f"{lbl}={count_occ(data, nb)}")
        print(f"  {s:20s} {' '.join(row)}")
    print()

    # ---------- PACKER / DRM ----------
    print("=== PACKER / DRM needles ===")
    packers = ["Denuvo","denuvo","DENUVO","VMProtect","vmprotect","VMPROTECT",
               ".vmp0",".vmp1",".vmp2",".xtls","Themida","themida","WinLicense",
               "UPX0","UPX1","UPX!","Enigma","ASProtect","SecuROM","SafeDisc",
               "Arxan","arxan","Irdeto","StarForce","Obsidium","PELock",
               "Codemeter","CodeMeter","HASP","Sentinel","Tages","Uplay","uplay",
               "EOSSDK","EpicGames"]
    hits_pack = {}
    for s in packers:
        tot = 0; det = []
        for lbl, nb in enc_all(s):
            c = count_occ(data, nb); tot += c
            if c: det.append(f"{lbl}={c}")
        if tot: hits_pack[s] = det
    print("  NONZERO:", hits_pack if hits_pack else "(none)")
    print()

    # ---------- ANTI-CHEAT ----------
    print("=== ANTI-CHEAT needles ===")
    ac = ["EasyAntiCheat","easyanticheat","EAC_","BattlEye","battleye","BEClient",
          "BEService","Denuvo Anti-Cheat","nProtect","GameGuard","Vanguard",
          "vgk.sys","anticheat","AntiCheat","Anti-Cheat","PunkBuster","Xigncode"]
    hits_ac = {}
    for s in ac:
        tot=0; det=[]
        for lbl, nb in enc_all(s):
            c = count_occ(data, nb); tot += c
            if c: det.append(f"{lbl}={c}")
        if tot: hits_ac[s] = det
    print("  NONZERO:", hits_ac if hits_ac else "(none)")
    print()

    # ---------- INTEGRITY / HASH strings ----------
    print("=== INTEGRITY / HASH needles (exact counts) ===")
    integ = ["SHA256","sha256","SHA-256","Sha256","SHA1","sha1","MD5","md5","Md5",
             "CRC32","crc32","Crc32","crc","checksum","Checksum","CHECKSUM",
             "tamper","Tamper","TAMPER","integrity","Integrity","INTEGRITY",
             "WinVerifyTrust","CertVerify","Authenticode","signature","Signature",
             "SIGNATURE","verify","Verify","hash","Hash","HASH","digest","Digest",
             "corrupt","Corrupt","CORRUPT","modified","Modified","cheat","Cheat"]
    for s in integ:
        row = []
        for lbl, nb in enc_all(s):
            row.append(f"{lbl}={count_occ(data, nb)}")
        print(f"  {s:16s} {' '.join(row)}")
    print()

    # ---------- CRYPTO API NAMES ----------
    print("=== CRYPTO API symbol names (ascii only, import/GetProcAddress names) ===")
    apis = ["BCryptOpenAlgorithmProvider","BCryptCloseAlgorithmProvider","BCryptGenRandom",
            "BCryptCreateHash","BCryptHashData","BCryptFinishHash","BCryptDestroyHash",
            "BCryptGetProperty","BCryptSetProperty",
            "CryptAcquireContext","CryptCreateHash","CryptHashData","CryptGetHashParam",
            "CryptCATAdminCalcHashFromFileHandle","CertGetCertificateChain",
            "WinVerifyTrust","CryptVerifySignature","CryptDeriveKey",
            "SHA256_Init","SHA256_Update","SHA256_Final","MD5_Init","EVP_Digest",
            "crc32_z","adler32","XXH64","xxhash","CityHash","MurmurHash"]
    for s in apis:
        c = count_occ(data, s.encode())
        print(f"  {'*' if c else ' '} {s:38s} {c}")
    print()

if __name__ == "__main__":
    main()
