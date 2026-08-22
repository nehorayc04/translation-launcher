# AC2 `work/` — translation pipeline

See `../PIPELINE.md` for the full flow and `../FEASIBILITY.md` for the verdict.

## Present

- **`ac2_rtl.py`** — `to_visual(logical_he)`: logical Hebrew → visual RTL order
  for AC2's no-bidi engine (numbers/Latin/tokens kept forward, brackets mirrored,
  tags/placeholders preserved). Unit-tested (`python ac2_rtl.py` → ALL PASS).
  Run it exactly ONCE on each translated string at build time.

## To instantiate (copy the SM2 trio — Universal Playbook §3/§4/§6)

Copy `games/spiderman2/work/sm2_{translate,watchdog,progress}.py` and adapt:

- **`ac2_translate.py`** — EN→He LM translator. Input/output = the **XML that
  AnvilToolkit exports** from `LocalizationPackage_<slot>` (not a JSON spine).
  Keep the short strict system prompt; preserve every `[TOKEN]`/`{VALUE}`/`%s`/
  tag. After translating, pipe each value through `ac2_rtl.to_visual()`.
  `gameId="assassinscreed2"`, `total` = number of strings in the package.
- **`ac2_watchdog.py`** — same self-healing supervisor (kill-client → `unload
  --all` → probe → relaunch; UTF-8 children; hourly structural QA).
- **`ac2_progress.py`** — 60 s push to `/api/admin/progress`,
  `gameId="assassinscreed2"`.

## To build

- **`ac2_font.py`** — draw Hebrew glyphs into a DDS atlas exported from
  `DataPC_extra.forge` (`AC2Aaux_ProBold_Latin_1_MapDesc` etc.), keeping cell
  metrics; record the codepoint→cell map the loc encoder uses. DDS via the
  `texconv.exe` bundled with AnvilToolkit.

## AC2 / Ezio glossary (names stay Latin in prose)

Ezio · Auditore · Altaïr · Firenze · Venezia · Roma · Toscana · Monteriggioni ·
Mario · Claudia · Leonardo (da Vinci) · Templars (→ טמפלרים) · Assassins (→ מסדר
האסאסינים) · Animus · Abstergo · Desmond · Codex (→ קודקס). Keep brand/place names
Latin where the source is a proper noun (same name/code passthrough rule as the
other games — Playbook §7).
