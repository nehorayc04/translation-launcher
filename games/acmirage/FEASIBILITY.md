# AC Mirage — FEASIBILITY (Phase 1, 2026-07-22)

## Verdict: 🟡 **GO-WITH-ONE-GATE**

Six of the seven Phase-1 gates are **closed and validated offline**. One gate is open and it is a
single in-game experiment, not a research project.

| # | Gate | Status |
|---|---|---|
| 0 | Container (scimitar **v29**) | 🟢 cracked + validated on 50 forges, `validate()==0` |
| 1 | Codec (CFD / Oodle) | 🟢 `acs_cfd.py` decodes unchanged |
| 2 | Text format + scope | 🟢 13,085 strings decoded (7,612 UI + 5,473 subtitles) |
| 3 | **Official Arabic slot** | 🟢 full UI + subtitles locale, **plus Arabic VO** |
| 4 | bidi mode | 🟢 **LOGICAL** — zero bidi code (0 presentation forms in 497k Arabic chars) |
| 5 | Identity round-trip (payload) | 🟢 semantic PASS 7,612/7,612 · 5,473/5,473 |
| 6 | Activation | 🟢 one registry string `…\Language = ar-AA` |
| 7 | **Which copy does the engine read?** | 🔴 **THE GATE** — the base forge is plaintext, the title-update forge holds the same IDs **encrypted** |
| 8 | Font has Hebrew? | 🟡 unknown — the menu proof answers it together with #7 |

## Why this is a strong target

- **A free, public tool already supports the whole container.** AnvilToolkit **v1.3.4** (no
  donation/Discord gate) implements `Game.Mirage` with **both `Deserialize29` and `Serialize29`**,
  and lists `Game.Mirage` in `LocalizationPackage.SupportedGames`. That is precisely the gate that
  killed AC Shadows (v42 repacker was donation-gated) and AC Black Flag Resynced (v50, no tool).
  We do not depend on it — everything above is pure Python — but it is a proven fallback repacker.
- **Arabic is first-class here.** Mirage is set in 9th-century Baghdad and ships full **Arabic
  voice-over** plus Arabic UI + subtitles. The RTL pipeline is not a stub locale, it is a headline
  feature — the strongest Arabic-slot position of any game in this project.
- **The scope is small.** 13,085 lines / ~800k chars. A single-pass New-Era translation, no fleet.
- **All 14 languages sit in one forge**, so the New-Era gender/context panel is free: every line
  has ar + fr + ru + es + it + pl + de + pt parallels at the same id.
- No loose files to fight, no anti-cheat, single-player.

## The one gate, stated precisely

`DataPC_patch_01.forge` (title update) contains the **same 28 LocalizationPackage resource IDs** as
`DataPC.forge`, ~22 % larger, with `name_len & 0x40000000` set = **encrypted with a 16-byte block
cipher whose key is inside the VMProtect-packed exe**. Per the base+patch rule
(CLAUDE.md §8e) the patch normally shadows the base. So:

- **If the engine reads the base for a given string** → we translate the base forge and ship. Done.
- **If the patch shadows it** → our base edit is invisible, and the answer is to write a
  **plaintext (flag-cleared)** package into the patch slot. This is *not* breaking the encryption:
  the flag is per-resource and the base forge proves the engine reads flag-0 objects natively.
  Worst case, remove the patch's loc entry so the base wins.

**Both branches are decided by ONE screenshot.** Put a pure-Latin marker (`ZZ-MIRAGE-OK-ZZ`) plus
a few Hebrew strings on main-menu keys in the base forge's Arabic package, set
`…\Language = ar-AA`, launch:

| what you see | what it proves |
|---|---|
| marker renders | the base wins → the encrypted patch is irrelevant for text |
| Hebrew renders clean | the shipped font covers Hebrew → **zero font work** |
| Hebrew renders as tofu | font gate opens (font not yet located — see RECON §5) |
| nothing changes | the patch shadows → switch to the plaintext-in-patch deploy |

Everything untranslated stays Arabic, so a partial proof degrades gracefully.

## Risks, honestly

1. **Patch shadowing (the gate above).** Medium. Two fallbacks, both plausible.
2. **Font.** Unknown until the proof. Mirage's UI *must* carry an Arabic-capable face; whether it
   also carries Hebrew is exactly what killed AC Unity. If it does not, the font becomes its own
   sub-project — and unlike Unity we would at least know the text pipeline works end to end.
3. **DLC text is 100 % encrypted** (`dlc_2\DataPC_2_dlc.forge`, Valley of Memory). Even in the best
   case the DLC is likely out of scope — ship the base game, document the limit.
4. **Payload growth** (~1.7–2×) from the single-char fragment dictionary. Mitigated by
   append-relocate deploy (size may grow) and by the AC-Unity minimal-rebuild trick.
5. **Denuvo / VMProtect** on the exe. Irrelevant for asset forges in every AC analysed here, but the
   Black Flag Resynced precedent (SHA-256 content integrity) means a modified forge could still be
   rejected — the proof also settles this.

## Next step

Build the write path (`acu_deploy.py`'s append-relocate + `acs_cfd` re-encode with **Mermaid**, per
the AC Shadows codec lesson), then ship the marker/Hebrew menu proof described above.

## מסמכים קשורים
- באותה תיקייה: [[games/acmirage/PIPELINE|PIPELINE]], [[games/acmirage/RECON|RECON]], [[games/acmirage/REPORT_HE|REPORT_HE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acmirage|CLAUDE_INDEX_games]]
