# -*- coding: utf-8 -*-
"""
context_review.py — the "text + screenshot" review gallery for gender/number decisions.

Ties the three pieces together:
  gender_filter  → WHICH lines carry a gender/number choice a screenshot could resolve
  the spine      → the LIVE Hebrew (femaleVariant / maleVariant) for each such line
  frame_match    → the in-game FRAME where that line appears (when a capture session ran)

Emits ONE self-contained HTML page (RTL, no external assets) listing every
fixed-referent ambiguous line with: the English source, the live Hebrew female+male
variants, the gender axes, the secondaryKey scene-hint, an explicit Hebrew gender
question, and — where a captured frame matched — the embedded screenshot. Lines with
no frame yet show a "play to capture" placeholder, so the same page fills in as the
user plays with game_visual_logger.py running.

Player-dependent lines (V is "you"/"I") are shown SEPARATELY and marked "engine
resolves — fill both variants, no screenshot": exactly the distinction from
gender_filter. The page's real ROI is the FIXED-referent set (NPC / group / device).

CLI
---
  python context_review.py                       # build gallery from current data
  python context_review.py --subs 800            # + include N subtitle ambiguous lines
  python context_review.py --out review.html
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import gender_filter as GF  # noqa: E402

RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
SPINE = {"base": os.path.join(RES, "localization_translated.json"),
         "dlc": os.path.join(RES, "dlc_ep1_translated.json")}
FIXED_REF = os.path.join(HERE, "cp2077_fixed_referent.jsonl")
MATCH_OUT = os.path.join(ROOT, "_archive", "visual_logs", "frame_matches.jsonl")
DEFAULT_OUT = os.path.join(HERE, "gender_context_review.html")

AXIS_HE = {
    GF.AXIS_ADDRESSEE: "פנייה (אתה/את/אתם)",
    GF.AXIS_SPEAKER:   "מדבר על עצמו (מוכן/מוכנה)",
    GF.AXIS_REFERENT:  "רפרנט (זכר/נקבה)",
    GF.AXIS_NUMBER:    "מספר (יחיד/רבים)",
}
Q_HE = {
    GF.AXIS_ADDRESSEE: "למי פונים? זכר / נקבה / רבים",
    GF.AXIS_SPEAKER:   "מי מדבר? זכר / נקבה",
    GF.AXIS_REFERENT:  "על מי מדובר? זכר / נקבה",
    GF.AXIS_NUMBER:    "יחיד או רבים?",
}


def _ekey(e: dict) -> str:
    return e.get("primaryKey") or e.get("stringId") or e.get("secondaryKey") or ""


def load_spine_index() -> dict:
    """{(src, section, key): {he_f, he_m, sk}}."""
    idx = {}
    for src, path in SPINE.items():
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        for sec, lst in data.items():
            if not isinstance(lst, list):
                continue
            for e in lst:
                if isinstance(e, dict):
                    idx[(src, sec, _ekey(e))] = {
                        "he_f": e.get("femaleVariant") or "",
                        "he_m": e.get("maleVariant") or "",
                        "sk": e.get("secondaryKey", ""),
                    }
    return idx


def load_frames() -> dict:
    """{(src_or_none, section, key): [frame records]} from a capture session."""
    out = {}
    if not os.path.exists(MATCH_OUT):
        return out
    with open(MATCH_OUT, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            sec = r.get("section", "")
            src = sec.split(":", 1)[0] if ":" in sec else None
            secn = sec.split(":", 1)[1] if ":" in sec else sec
            out.setdefault((src, secn, r.get("key", "")), []).append(r)
    return out


def _frame_data_uri(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            b = f.read()
        ext = "jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "png"
        return f"data:image/{ext};base64,{base64.b64encode(b).decode()}"
    except OSError:
        return None


def build_records(include_subs: int) -> tuple[list, list, dict]:
    """Return (fixed_referent_records, player_dependent_records, stats)."""
    idx = load_spine_index()
    frames = load_frames()
    fixed, player = [], []
    stats = {"onscreens_amb": 0, "subs_scanned": 0, "subs_amb": 0, "with_frame": 0}

    def attach_frame(rec, src, sec, key):
        fkey = (src, sec, key)
        fr = frames.get(fkey) or frames.get((None, sec, key))
        if fr:
            best = max(fr, key=lambda x: x.get("ratio", 0))
            uri = _frame_data_uri(best["frame_path"])
            if uri:
                rec["frame"] = uri
                rec["frame_ts"] = best.get("ts", "")
                stats["with_frame"] += 1

    # 1) onscreens fixed-referent set (already classified) -> live spine Hebrew
    if os.path.exists(FIXED_REF):
        with open(FIXED_REF, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                sec = d["section"]
                key = str(d.get("pk") or d.get("secondaryKey") or "")
                live = idx.get(("base", sec, key)) or idx.get(("dlc", sec, key)) or {}
                stats["onscreens_amb"] += 1
                rec = {
                    "scope": "onscreen", "section": sec, "key": key,
                    "en": d.get("en", ""), "sk": d.get("secondaryKey", ""),
                    "axes": d.get("axes", []), "conf": d.get("conf", "low"),
                    "he_f": live.get("he_f", d.get("he", "")),
                    "he_m": live.get("he_m", ""),
                }
                attach_frame(rec, "base", sec, key)
                fixed.append(rec)

    # 2) optional subtitle ambiguous set: classify secondaryKey (the English source)
    if include_subs:
        want = include_subs
        for (src, sec, key), v in idx.items():
            if "subtitle" not in sec:
                continue
            en = v["sk"]
            if not en or len(en) < 3:
                continue
            stats["subs_scanned"] += 1
            verd = GF.classify(en)
            if not verd.ambiguous:
                continue
            stats["subs_amb"] += 1
            rec = {
                "scope": "subtitle", "section": sec, "key": key,
                "en": en, "sk": key, "axes": verd.axes,
                "conf": verd.confidence,
                "he_f": v["he_f"], "he_m": v["he_m"],
                "player_dependent": verd.player_dependent,
            }
            attach_frame(rec, src, sec, key)
            (player if verd.player_dependent else fixed).append(rec)
            if verd.player_dependent:
                continue
            want -= 1
            if want <= 0:
                break

    # frame-first, then by confidence
    order = {"high": 0, "med": 1, "low": 2}
    fixed.sort(key=lambda r: (0 if r.get("frame") else 1, order.get(r["conf"], 3)))
    return fixed, player, stats


# ── HTML ────────────────────────────────────────────────────────────────────
def _e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def _card(r: dict) -> str:
    axes = " · ".join(AXIS_HE.get(a, a) for a in r.get("axes", [])) or "—"
    q = " / ".join(dict.fromkeys(Q_HE.get(a, "") for a in r.get("axes", []) if a)) or ""
    diff = "שונה ✓" if (r["he_m"] and r["he_m"] != r["he_f"]) else "זהה ⚠"
    if r.get("frame"):
        media = (f'<div class="shot"><img src="{r["frame"]}" alt="frame" loading="lazy">'
                 f'<span class="ts">{html.escape(str(r.get("frame_ts","")))}</span></div>')
    else:
        media = ('<div class="shot noshot"><span>אין תמונה עדיין</span>'
                 '<small>הרץ game_visual_logger תוך כדי משחק</small></div>')
    return f"""
<div class="card {'has' if r.get('frame') else 'no'}">
  {media}
  <div class="body">
    <div class="scope">{_e(r['scope'])} · {_e(r['conf'])}</div>
    <div class="en" dir="ltr">{_e(r['en'])}</div>
    <div class="axes">{_e(axes)}</div>
    <div class="he"><b>נ׳</b> {_e(r['he_f'])}</div>
    <div class="he"><b>ז׳</b> {_e(r['he_m'] or '—')} <i class="tag">{diff}</i></div>
    <div class="q">{_e(q)}</div>
    <div class="sk" dir="ltr">{_e(r.get('sk',''))}</div>
  </div>
</div>"""


def build_html(fixed: list, player: list, stats: dict) -> str:
    cards = "\n".join(_card(r) for r in fixed)
    pcount = len(player)
    return f"""<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>הקשר מגדרי — טקסט + תמונה</title>
<style>
:root{{color-scheme:dark light}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:'Segoe UI',system-ui,sans-serif;direction:rtl;
  background:#0b0b14;color:#e8e8f0}}
header{{position:sticky;top:0;z-index:5;padding:14px 20px;background:#12121f;
  border-bottom:1px solid #262640;box-shadow:0 2px 12px #0008}}
h1{{margin:0 0 4px;font-size:19px}}
.sub{{color:#9a9ac0;font-size:13px}}
.stats{{display:flex;gap:14px;flex-wrap:wrap;margin-top:8px}}
.stat{{background:#1a1a2e;border:1px solid #2a2a46;border-radius:9px;padding:6px 12px;font-size:13px}}
.stat b{{color:#7ce7d0;font-size:16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
  gap:14px;padding:18px}}
.card{{background:#14141f;border:1px solid #26263f;border-radius:12px;overflow:hidden;
  display:flex;flex-direction:column}}
.card.has{{border-color:#2c6}}
.shot{{aspect-ratio:16/9;background:#000;position:relative;display:flex;
  align-items:center;justify-content:center}}
.shot img{{width:100%;height:100%;object-fit:cover}}
.shot .ts{{position:absolute;bottom:4px;inset-inline-start:6px;font-size:10px;
  background:#000a;padding:1px 6px;border-radius:5px;color:#bbb}}
.noshot{{flex-direction:column;color:#55557a;gap:4px;background:#101019}}
.noshot small{{font-size:10px;color:#3d3d5c}}
.body{{padding:11px 13px;display:flex;flex-direction:column;gap:6px}}
.scope{{font-size:11px;color:#8a8ab0;text-transform:uppercase;letter-spacing:.5px}}
.en{{font-size:13px;color:#cfcfe8;background:#0e0e18;border-radius:6px;padding:5px 8px}}
.axes{{font-size:12px;color:#e0a86a}}
.he{{font-size:15px;line-height:1.5}}
.he b{{color:#7ce7d0;font-size:12px;margin-inline-end:4px}}
.tag{{font-size:11px;color:#9a9ac0;font-style:normal}}
.q{{font-size:12px;color:#c98bd8;font-weight:600}}
.sk{{font-size:10px;color:#50506e;word-break:break-all}}
.note{{margin:12px 18px;padding:11px 14px;background:#141422;border:1px solid #2a2a46;
  border-radius:10px;font-size:13px;color:#b8b8d8;line-height:1.6}}
</style>
<header>
  <h1>הקשר מגדרי — טקסט + תמונה (Cyberpunk 2077)</h1>
  <div class="sub">שורות שדורשות הכרעת מגדר/מספר בעברית — עם התרגום החי (נ׳/ז׳) והתמונה מהמשחק כשנלכדה</div>
  <div class="stats">
    <div class="stat"><b>{len(fixed):,}</b> רפרנט קבוע (צריך הקשר)</div>
    <div class="stat"><b>{stats['with_frame']:,}</b> עם תמונה</div>
    <div class="stat"><b>{pcount:,}</b> תלוי-שחקן (המנוע פותר)</div>
    <div class="stat"><b>{stats['onscreens_amb']:,}</b> onscreens · <b>{stats['subs_amb']:,}</b> כתוביות</div>
  </div>
</header>
<div class="note">
  <b>רפרנט קבוע</b> = NPC / קבוצה / התקן — המגדר קבוע בעולם, לא תלוי בבחירת V, ולכן
  <b>תמונת ההקשר עוזרת להכריע</b> (מי מדובר, זכר/נקבה/רבים). <b>תלוי-שחקן</b> (V = "אתה"/"אני")
  נפתר ע״י מילוי שני הווריאנטים והמנוע בוחר — בלי תמונה. כשמריצים
  <code>game_visual_logger.py</code> תוך כדי משחק ואז <code>frame_match.py index</code>,
  הכרטיסים מתמלאים בצילום המסך המתאים אוטומטית.
</div>
<div class="grid">
{cards}
</div>"""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="context_review")
    p.add_argument("--subs", type=int, default=600,
                   help="also classify up to N subtitle lines (0=onscreens only)")
    p.add_argument("--out", default=DEFAULT_OUT)
    a = p.parse_args(argv)
    fixed, player, stats = build_records(a.subs)
    htmlp = build_html(fixed, player, stats)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(htmlp)
    print(f"[✓] {a.out}")
    print(f"    fixed-referent (need context): {len(fixed):,}")
    print(f"    player-dependent (engine-resolved): {len(player):,}")
    print(f"    with a captured frame: {stats['with_frame']:,}")
    print(f"    onscreens ambiguous {stats['onscreens_amb']:,} · "
          f"subtitles scanned {stats['subs_scanned']:,} → ambiguous {stats['subs_amb']:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
