r"""
VirtualDJ Hebrew menu-proof (Phase-1 step 5).

Builds an Arabic-slot Hebrew language file: takes the shipped Arabic.xml
skeleton, overrides a handful of HIGH-VISIBILITY UI strings (browser column
headers + browser root folders) with Hebrew + ONE Latin marker, and deploys
it to %LOCALAPPDATA%\VirtualDJ\Languages\Arabic.xml (overrides the embedded
copy). Everything else stays Arabic so the UI is coherent RTL and the Hebrew
proof strings stand out.

Proves at once:
  * the folder Arabic.xml OVERRIDES the embedded one (Latin marker appears)
  * bidi/RTL mode (Hebrew reads correct direction vs reversed)
  * the skin font renders Hebrew (no tofu)

Activation: VirtualDJ is already set to language=Arabic (settings.xml). Just
(re)start VirtualDJ; the marker + Hebrew appear in the browser column headers
and the left folder tree.

  python build_menu_proof.py --deploy    # write + backup
  python build_menu_proof.py --revert    # restore original
  python build_menu_proof.py             # just build to work/_proof_Arabic.xml
"""
import os
import sys
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(GAME / "tools"))
import vdj_lang  # noqa: E402

ARABIC_SKELETON = GAME / "extract" / "langs_orig" / "Arabic.xml"
BUILT = HERE / "_proof_Arabic.xml"

LANG_DIR = Path(os.environ["LOCALAPPDATA"]) / "VirtualDJ" / "Languages"
DEPLOY = LANG_DIR / "Arabic.xml"
BACKUP = LANG_DIR / "Arabic.xml.he_backup"

# High-visibility proof strings. ONE Latin marker proves load+override
# (font-independent); the rest are Hebrew to test RTL + font coverage.
PROOF = {
    "RootElements/Sampler":    "ZZ-VDJ-OK-ZZ",   # Latin marker
    # browser column headers (shown the instant VirtualDJ opens)
    "Columns/Title":           "כותרת",          # כותרת
    "Columns/Artist":          "אמן",                      # אמן
    "Columns/Length":          "אורך",                # אורך
    "Columns/Key":             "מפתח",                # מפתח
    "Columns/Genre":           "סגנון",          # סגנון
    "Columns/Year":            "שנה",                      # שנה
    "Columns/Comment":         "הערה",                # הערה
    "Columns/Rating":          "דירוג",          # דירוג
    # browser root folders (left tree)
    "RootElements/LocalMusic": "מוזיקה מקומית",  # מוזיקה מקומית
    "RootElements/MyLists":    "הרשימות שלי",              # הרשימות שלי
    "RootElements/MyMusic":    "המוזיקה שלי",              # המוזיקה שלי
    "RootElements/History":    "היסטוריה",                          # היסטוריה
    "RootElements/Desktop":    "שולחן עבודה",              # שולחן עבודה
    "RootElements/Crates":     "ארגזים",                                      # ארגזים
}


def build():
    arabic = ARABIC_SKELETON.read_bytes()
    # keep lang="Arabic" iso="ar" so the RTL locale is selected as-is
    out = vdj_lang.build_hebrew(arabic, PROOF)
    BUILT.write_bytes(out)
    # sanity: re-parse and confirm our overrides landed
    _, secs = vdj_lang.parse(out)
    flat = vdj_lang.flatten(secs)
    bad = [k for k, v in PROOF.items() if flat.get(k) != v]
    print(f"built {BUILT}  ({len(out)} bytes, {len(flat)} entries)  "
          f"overrides OK={len(PROOF)-len(bad)}/{len(PROOF)}")
    if bad:
        print("  MISSING:", bad)
        sys.exit(1)
    return out


def deploy():
    build()
    LANG_DIR.mkdir(parents=True, exist_ok=True)
    if DEPLOY.exists() and not BACKUP.exists():
        shutil.copy2(DEPLOY, BACKUP)
        print(f"backed up existing -> {BACKUP}")
    shutil.copy2(BUILT, DEPLOY)
    print(f"deployed -> {DEPLOY}")
    print("Now (re)start VirtualDJ (language is already Arabic). Look at the "
          "browser column headers + left folder tree: 'ZZ-VDJ-OK-ZZ' (marker) "
          "+ Hebrew words should appear.")


def revert():
    if BACKUP.exists():
        shutil.copy2(BACKUP, DEPLOY)
        BACKUP.unlink()
        print(f"restored original {DEPLOY} from backup")
    elif DEPLOY.exists():
        DEPLOY.unlink()
        print(f"removed {DEPLOY} (no backup -> back to embedded Arabic)")
    else:
        print("nothing to revert")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--deploy":
        deploy()
    elif arg == "--revert":
        revert()
    else:
        build()
