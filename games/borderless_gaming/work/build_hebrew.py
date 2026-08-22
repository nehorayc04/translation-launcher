"""Build + deploy the full Hebrew language file.

    python work/build_hebrew.py            # build only -> out/he-IL.json
    python work/build_hebrew.py --deploy   # build, deploy, set the app language
    python work/build_hebrew.py --revert   # remove it, language back to ""

Deploys to the app's USER languages folder, so the Steam install stays pristine
and "Verify integrity of game files" can never revert the translation.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bg_lang as B  # noqa: E402
from build_menu_proof import USER_LANGS, EN, target  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent.parent
SETTINGS = USER_LANGS.parent / "settings.json"


def qa() -> None:
    """Never build past a failing QA gate."""
    r = subprocess.run([sys.executable, str(HERE / "work" / "qa_scan.py")],
                       capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip())
    if r.returncode != 0:
        sys.exit("QA failed - not building.")


def set_language(code: str) -> None:
    try:
        data = json.loads(SETTINGS.read_text("utf-8"))
        data["language"] = code
        SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8", newline="\r\n")
        print(f"settings.json language -> {code!r}")
    except Exception as exc:
        print(f"(could not set language: {exc})")


def build() -> Path:
    qa()
    heb = json.loads((HERE / "hebrew.json").read_text("utf-8"))
    doc = B.build_hebrew(EN, heb)
    out = HERE / "out"
    out.mkdir(exist_ok=True)
    path = out / "he-IL.json"
    B.dump(doc, path)

    flat = B.flatten(doc)
    assert set(flat) == set(B.flatten(B.load(EN))), "key set drifted"
    left = sum(1 for k, v in flat.items() if v == B.flatten(B.load(EN))[k])
    print(f"built {path}  ({len(flat)} keys, {len(flat) - left} translated, "
          f"{left} intentionally left Latin)")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()

    if a.revert:
        if target().exists():
            target().unlink()
            print(f"removed {target()}")
        set_language("")
        return 0

    path = build()
    if a.deploy:
        USER_LANGS.mkdir(parents=True, exist_ok=True)
        target().write_bytes(path.read_bytes())
        set_language("he-IL")
        print(f"deployed -> {target()}")
        print("Restart Borderless Gaming (tray -> Exit) to see it in Hebrew.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
