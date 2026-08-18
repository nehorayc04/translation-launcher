## 🎛 orchestration/ — the control plane (READ FIRST, 2026-06-29)

A top-level management layer above every game + every profile, so the solo dev
(Nahorai) drives the whole multi-agent operation from ONE place instead of
hand-writing instructions to each agent in each profile. Full docs:
`orchestration/README.md`. **The operating charter is `orchestration/DOCTRINE.md`
(READ FIRST) — finish to the end, full power on hard problems, cut fast on dead-ends/
trivia, no weak shortcuts, double-check everything (never trust an agent's "done"),
elite model per role.** Decisions (user, AskUserQuestion):

- **Brain = a single MAX Claude Code session.** It holds all state, generates all
  agent instructions, routes tasks. PRO + Google/Antigravity agents only execute.
- **Delivery = one-liner file pointer.** The brain writes the full instruction to a
  repo file; the user pastes ONE line per agent (`קרא <file> ובצע`). Requires the
  same repo folder open in each Antigravity profile.
- **Roles:** MAX = orchestrate + heavy launcher/site work · PRO = overflow when MAX
  quota hits (via `orchestration/HANDOFF.md`) · 3-5 Google agents = parallel
  translate/QA (interchangeable slots, `N` per task).
- **Full-auto with 3 hard gates.** Auto without asking: instruction generation,
  output merge + structural QA, shared-rule updates, board refresh. **Requires
  explicit user OK:** (1) publishing a mod (GitHub/Worker/site), (2) shipping the
  launcher (rebuild + `publish_release`), (3) deleting/overwriting real game files.
- **Initiative = propose + wait.** Each session, read the board and propose the best
  next step; wait for approval before acting.
- **Command vocabulary** (`orchestration/COMMANDS.md`): `מצב/status`,
  `תרגם/translate <game> <N>`, `בקר/qa <game> <N>`, `מזג/merge <game>`,
  `בנה/build`, `פרסם/publish` 🔒, `שגר לאנצ'ר` 🔒, `כלל/rule "<text>"`,
  `חדש/new <game>`, `המשך/continue` (PRO).
- **Files:** `MISSION.md` (the board the user opens — auto-generated, never edit by
  hand) · `state.json` (source of truth) · `RULES.md` (shared cross-game rules +
  per-game pointers + a changelog; a new universal rule is appended here AND applied
  to future handoffs) · `HANDOFF.md` (MAX→PRO handoff) · `orchestrate.py`
  (`board`/`status`/`set`/`dispatch`/`clear-dispatch`). Regenerate the board:
  `python orchestration/orchestrate.py board`.

When the user gives a short command in any MAX/PRO session in this repo, treat it as
an orchestration command, act per the gates above, then `orchestrate.py board`.

---


