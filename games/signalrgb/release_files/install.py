# -*- coding: utf-8 -*-
"""SignalRGB Hebrew translation — installer.

    python install.py            install (Hebrew)
    python install.py --revert   restore the original English/Arabic

Close SignalRGB first (Quit from the tray).  Everything is reversible, and a
pristine copy of every file we touch is kept OUTSIDE the app folder
(%LOCALAPPDATA%\\WhirlwindFX\\SignalRgb\\hebrew_backup), so a SignalRGB update —
which replaces the app folder — is handled by simply re-running this installer.

Four surfaces are translated:
  1. the app UI          — the embedded .qm inside SignalRgb.exe (delta-0 patch)
  2. the language picker  — the exe's own native-name literal ("العربية" -> "עברית")
  3. the Macros page      — the loose Macroscripts\\*.js metadata
  4. every device page    — the 400+ device plugin labels (install + CDN cache)
plus the UI language is set to the (hijacked) Arabic slot in the registry.
"""
from __future__ import annotations
import os, sys, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import patch_exe as P
import macro_scripts as MS
import build_macros as BM
import build_plugins as BP

HERE = os.path.dirname(os.path.abspath(__file__))


def _exe():
    try:
        return P.find_exe()
    except SystemExit as e:
        print(e)
        sys.exit(1)


def deploy():
    exe = _exe()
    if P.is_running():
        print("note: SignalRGB is running — patching in place; RESTART it to see "
              "the change.")

    # 1+2) exe UI slot (.qm) + the language-picker literal + UI/Locale = ar
    hebrew = json.load(open(os.path.join(HERE, "hebrew.json"), encoding="utf-8"))
    data = open(exe, "rb").read()
    off, size, kind = P.find_slot(data)
    pristine = P.ensure_backup(exe, data, off, size, kind=kind)
    # A compressed slot (SignalRGB 2.5.75+) may hold strings we have not
    # translated — drop those so Qt falls back to English, not Arabic.
    blob, n = P.build_hebrew_qm(pristine, hebrew, size, kind=kind,
                                drop_untranslated=(kind != "raw"))
    _, recs = P.apply_literals(data)
    if recs:
        json.dump(recs, open(P._literal_meta_path(), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    extra = [(r["offset"], r["dst"].encode("utf-8")
              + b"\0" * (r["span"] - len(r["dst"].encode("utf-8")))) for r in recs]
    P.write_slot(exe, off, size, blob, extra=extra)
    P.cmd_lang("ar")
    print("[1/4] UI (.qm)      : %d strings" % n)
    print("[2/4] language name : %s" % ("עברית" if recs else "(unchanged)"))

    # 3) Macros page — tolerant (patch what we know, leave the rest English)
    m_he = json.load(open(os.path.join(HERE, "macros_he.json"), encoding="utf-8"))
    m_root = BM.macro_root()
    total = 0
    for rel, text in BM.sync_backup(m_root).items():
        new, k = MS.patch(text, m_he)
        if k:
            open(os.path.join(m_root, rel.replace("/", os.sep)), "w",
                 encoding="utf-8", newline="").write(new)
            total += k
    print("[3/4] Macros        : %d labels" % total)

    # 4) device plugins (install folder + CDN cache) — label-only, tolerant
    p_he = json.load(open(os.path.join(HERE, "plugins_he.json"), encoding="utf-8"))
    pv = set(p_he.values())
    ptot = 0
    for tag, root in BP.roots():
        for rel, text in BP.sync_backup(tag, root, pv).items():
            new, k = MS.patch_labels_only(text, p_he)
            if k:
                open(os.path.join(root, rel), "w", encoding="utf-8",
                     newline="").write(new)
                ptot += k
    print("[4/4] device plugins: %d labels" % ptot)
    print("\nDONE — start SignalRGB (the language is already set to Hebrew).")


def revert():
    if P.is_running():
        print("Close SignalRGB from the tray first, then re-run --revert.")
        return
    P.cmd_revert()          # exe slot + literals
    P.cmd_lang("clear")     # UI language back to the system default
    BM.cmd_revert()         # Macroscripts
    BP.cmd_revert()         # device plugins
    print("\nReverted — SignalRGB is back to its original state.")


if __name__ == "__main__":
    (revert if "--revert" in sys.argv else deploy)()
