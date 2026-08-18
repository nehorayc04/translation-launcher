## 🔒 IRON RULE — the plain hyphen `-`, NEVER a long dash `—` (user, 2026-08-02)

**"כלל ברזל לכל התרגומים עכשיו ובעתיד תמיד להשתמש ב `-` ולא ב `—`"** — every game, every
surface, every future target. It is deterministic with exactly one right answer, so it lives in
the **BUILD PIPELINE**, never in a style guide: a rule written only in a document WILL be
violated (an LLM emits an em dash by reflex, and so does a human copy-editing Hebrew).
Same reasoning as the SignalRGB lesson — when a defect class recurs, move the fix into the
pipeline. Memory [[iron-rule-plain-hyphen]].

**Already wired — do NOT re-derive, just reuse:**
| Layer | What |
|---|---|
| `universal/text_norm.py` | `normalize_dashes` / `has_long_dash` / `scan`. Replaces U+2010 2011 2012 2013 2014 2015 2212 2E3A 2E3B FE58 FE63 FF0D. selftest 10/10 |
| all 17 `games/*/{work,tools}/*_rtl.py` | an appended `_iron_rule()` wrapper on the public entry (`to_visual`/`to_logical`/`to_stored`) = the LAST gate before storage. Verified 0 leaks on all 17 |
| `universal/brain_universal.json` | repair `iron-rule-plain-hyphen` + rule `iron-rule-dash`, for games with no `_rtl.py` |
| `universal/dash_sweep.py` | the retroactive catch-up for corpora translated before the rule (dry-run by default, `--apply` backs up, `--check-tokens` audits) |

- **🔴 ONE-FOR-ONE, never a run-collapse.** `——` → `--`. A repeated dash is usually a decorative
  rule the translator drew on purpose (`—— רמות ——` heads a VirtualDJ section) and collapsing it
  silently redesigns the UI. The rule is about WHICH character, not how many. (U+2E3A/2E3B are
  single codepoints, so they still become exactly one hyphen.)
- **🔴 U+05BE HEBREW MAQAF (`בין־לאומי`) IS NOT A LONG DASH** — deliberately not in the class. If
  it ever *looks* wrong that is a FONT decision per game (Witcher 3 notes), not this rule.
- **🔴 VALUES ONLY, NEVER KEYS.** Several corpora are keyed by the ENGLISH SOURCE STRING
  (`gtav/agent_handoff_full/reuse_he.json`, every md5(EN)-keyed pool) — rewriting a key orphans
  that line from the build and it silently ships English. `dash_sweep` copies keys verbatim
  (guard-tested).
- **Retroactive sweep DONE (2026-08-02): 5,145 of 431,903 values across 11 shipped corpora** —
  anno1800 2,304 · gowr 1,433 · witcher3 1,207 · gtav 99 · wd2 39 · pt 27 · ac2 20 · r&c 13 ·
  vdj 3. Verified path-for-path vs the backups: **0 keys added/removed/renamed, 0 drift beyond
  the dash**. ⚠️ **A corpus change is invisible in-game until that game is RE-BAKED** — the sweep
  touches the source of truth only and never deploys.
- ⚠️ Wiring it in makes any selftest whose EXPECTED string hardcodes a `—` start failing — that is
  a **stale expectation, not a regression** (hit on rdr2 + acmirage/acvalhalla). Confirm the case
  literally contains a long dash before suspecting the transform.


