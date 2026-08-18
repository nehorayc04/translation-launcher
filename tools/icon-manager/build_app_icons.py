# Reads the frontend icon INVENTORY (produced by the icon-inventory workflow) and
# emits app_icons.json = a new "app" group for icon-manager.html, so EVERY
# user-facing app icon becomes a configurable slot.
#
# Component icons (UiIcons.* / NavIcons.*) are ALREADY configurable elsewhere
# (NavIcons → the "קיימים" group; the UiIcons applied to button/header/badge slots
# → the "ללא אייקון"/optional group), so this only adds the icons that had NO
# customization option: the raw inline-<svg> glyphs (stat cards, view toggles,
# carousel arrows, drawer chevron, search…) + the EMOJI used as icons (▶ ⬆ ← ✓
# 🖥 ✨ 🔒 ↺ ↗ ▸ ▼ ⚠️ …). Converts JSX-SVG (strokeWidth={2}) → valid HTML SVG.
import json, re, os

HERE = os.path.dirname(os.path.abspath(__file__))
INV_OUT = os.environ.get("ICON_INVENTORY_FILE", "")
if not INV_OUT:
    # default: the workflow result file
    INV_OUT = (r"C:\Users\Nehoray_Cohen\AppData\Local\Temp\claude"
               r"\c--Users-Nehoray-Cohen-Projects-Game-translator"
               r"\e3f5c3b9-e948-4d52-888f-12c32af3deee\tasks\wzsqyc9hi.output")

raw = json.load(open(INV_OUT, encoding="utf-8"))
# unwrap {summary, result:{icons}} | {result:{icons}} | {icons} | [ ... ]
icons = raw
for key in ("result", "icons"):
    if isinstance(icons, dict) and key in icons:
        icons = icons[key]
if isinstance(icons, dict) and "icons" in icons:
    icons = icons["icons"]
assert isinstance(icons, list), "could not find the icons array in the inventory"

# ids already covered by another icon-manager group (don't duplicate them)
EXCLUDE_PREFIX = ("nav-", "titlebar-", "notif-", "controller-ps", "controller-xbox", "controller-generic")
EXCLUDE_ID = {"sidebar-lock", "sidebar-user-avatar"}  # == EXISTING auth-lock / avatar-user

def jsx_to_html(svg: str) -> str:
    s = svg
    s = re.sub(r"=\{\s*([0-9.]+)\s*\}", r'="\1"', s)          # width={13} -> width="13"
    for a, b in (("strokeWidth", "stroke-width"), ("strokeLinecap", "stroke-linecap"),
                 ("strokeLinejoin", "stroke-linejoin"), ("strokeMiterlimit", "stroke-miterlimit"),
                 ("fillRule", "fill-rule"), ("clipRule", "clip-rule"), ("strokeDasharray", "stroke-dasharray"),
                 ("strokeDashoffset", "stroke-dashoffset")):
        s = s.replace(a, b)
    s = re.sub(r"\s+aria-hidden\b", "", s)                     # drop the JSX aria-hidden flag
    return re.sub(r"\s+", " ", s).strip()

seen, out = set(), []
for ic in icons:
    if ic.get("source") not in ("inline-svg", "emoji"):
        continue                                              # component icons already covered
    iid = ic["id"]
    if iid in seen or iid in EXCLUDE_ID or any(iid.startswith(p) for p in EXCLUDE_PREFIX):
        continue
    seen.add(iid)
    svg = ic["svg"]
    out.append({
        "id": "app-" + iid,
        "name": ic.get("hebrewName", iid),
        "purpose": ic.get("purpose", ""),
        "location": ic.get("location", ""),
        "kind": ic.get("kind", ""),
        # inline-svg -> HTML svg; emoji -> the char itself (renders fine as innerHTML)
        "svg": jsx_to_html(svg) if ic["source"] == "inline-svg" else svg,
    })

out.sort(key=lambda x: (x["kind"], x["id"]))
json.dump(out, open(os.path.join(HERE, "app_icons.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("app_icons.json:", len(out), "new configurable slots (inline-svg + emoji)")
by_kind = {}
for x in out:
    by_kind[x["kind"]] = by_kind.get(x["kind"], 0) + 1
print("by kind:", by_kind)
