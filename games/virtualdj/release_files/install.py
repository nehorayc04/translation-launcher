# -*- coding: utf-8 -*-
r"""VirtualDJ Hebrew — local mod installer.

Drops the Hebrew language file into %LOCALAPPDATA%\VirtualDJ\Languages\Arabic.xml
(overrides the Arabic slot embedded in the exe). Backs up any existing Arabic.xml
to Arabic.xml.he_backup on first install.

  python install.py           # install (backup-then-copy)
  python install.py --revert  # restore the pre-install Arabic.xml (or remove ours)

Activation in VirtualDJ: Settings -> Options -> language = العربية (Arabic).
The whole UI then shows Hebrew (English VO/brand names stay as-is).
"""
import os, sys, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "Arabic.xml"
LANG = Path(os.environ["LOCALAPPDATA"]) / "VirtualDJ" / "Languages"
DEST = LANG / "Arabic.xml"
BACKUP = LANG / "Arabic.xml.he_backup"


def install():
    LANG.mkdir(parents=True, exist_ok=True)
    if DEST.exists() and not BACKUP.exists():
        shutil.copy(DEST, BACKUP)
        print(f"backed up existing -> {BACKUP}")
    shutil.copy(SRC, DEST)
    print(f"installed -> {DEST}")
    print("Now (re)start VirtualDJ and set the language to العربية (Arabic).")


def revert():
    if BACKUP.exists():
        shutil.copy(BACKUP, DEST)
        print(f"restored original -> {DEST}")
    elif DEST.exists():
        DEST.unlink()
        print(f"removed {DEST} (back to embedded Arabic)")
    else:
        print("nothing to revert")


if __name__ == "__main__":
    (revert if "--revert" in sys.argv else install)()
