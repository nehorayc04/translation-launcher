"""
submit_defender_fp.py — prep a Windows Defender FALSE-POSITIVE submission for the
launcher installer, to reduce/clear the Defender heuristic flag on the UNSIGNED
Inno Setup installer (the same false positive that labels the winget PR
`Validation-Defender-Error`).

STANDING RULE (user 2026-07-12): run this after EVERY launcher build/publish.

Microsoft's WDSI portal (https://www.microsoft.com/en-us/wdsi/filesubmission)
requires an interactive Microsoft-account sign-in — there is NO anonymous public
API — so full hands-off automation is impossible. This script does EVERYTHING
that can be automated:
  * finds the newest installer (Output\\TranslationManager-Setup-*.exe, or --file)
  * computes its SHA-256 (so you can confirm it matches the published asset)
  * opens the WDSI submission portal in the browser
  * opens the folder with the installer selected (ready to drag/upload)
  * prints the exact form values to paste

You then: sign in → role "Software developer" → upload the exe → paste the values
below → set "I believe this file should NOT be detected" → submit. ~30 seconds.

Usage:
    python submit_defender_fp.py                 # newest installer in Output\\
    python submit_defender_fp.py --file <path>   # a specific installer
    python submit_defender_fp.py --no-open       # just print (no browser/explorer)
"""
import argparse
import glob
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root (this script lives in scripts/)
WDSI_URL = "https://www.microsoft.com/en-us/wdsi/filesubmission"

# The steady facts about this product — pasted into the WDSI form fields.
PRODUCT = "Translation Manager (Hebrew Game Translation Hub launcher)"
PUBLISHER = "Nehoray Cohen"
HOMEPAGE = "https://hebrew-translation-hub.com"
JUSTIFICATION = (
    "This is a legitimate, open desktop application: a free Hebrew game-"
    "localization launcher. The installer is an UNSIGNED Inno Setup package, "
    "which triggers a Windows Defender heuristic FALSE POSITIVE. It contains no "
    "malware. The same publisher/package (Nehoray.TranslationManager) is already "
    "accepted in winget. Please reclassify as clean."
)


def newest_installer():
    hits = sorted(
        glob.glob(os.path.join(HERE, "Output", "TranslationManager-Setup-*.exe")),
        key=os.path.getmtime,
    )
    return hits[-1] if hits else None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="installer path (default: newest in Output\\)")
    ap.add_argument("--no-open", action="store_true", help="don't open browser/explorer")
    args = ap.parse_args()

    exe = args.file or newest_installer()
    if not exe or not os.path.isfile(exe):
        print("ERROR: no installer found. Build first (build_exe.bat -> ISCC), "
              "or pass --file <path>.")
        sys.exit(1)

    digest = sha256(exe)
    size = os.path.getsize(exe)

    print("=" * 70)
    print("Windows Defender FALSE-POSITIVE submission — prepared values")
    print("=" * 70)
    print(f"File        : {exe}")
    print(f"Size        : {size:,} bytes")
    print(f"SHA-256     : {digest}")
    print("-" * 70)
    print("Paste into the WDSI form (role = 'Software developer'):")
    print(f"  Product name   : {PRODUCT}")
    print(f"  Publisher      : {PUBLISHER}")
    print(f"  Homepage       : {HOMEPAGE}")
    print(f"  Detection name : (leave blank / whatever Defender shows)")
    print(f"  Your assessment: This file should NOT be detected (false positive)")
    print(f"  Comments       :\n    {JUSTIFICATION}")
    print("=" * 70)

    if args.no_open:
        return
    try:
        os.startfile(WDSI_URL)  # noqa: S606 (Windows only)
    except Exception as e:
        print(f"(couldn't open the portal automatically: {e} — go to {WDSI_URL})")
    try:
        subprocess.Popen(["explorer", "/select,", os.path.abspath(exe)])
    except Exception:
        pass
    print("\nNext: sign in -> Software developer -> upload the exe above -> paste "
          "the values -> submit.")


if __name__ == "__main__":
    main()
