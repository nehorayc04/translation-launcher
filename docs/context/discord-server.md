# Discord server — Hebrew Translation Hub

The community Discord for the hub. Managed **programmatically via the Discord REST API**, not by
hand in the client.

## Access

| Item | Value |
|---|---|
| Guild (server) id | `1513628042390540358` |
| Bot | **HTH Manager** — application id `1535836175326122064` |
| Bot token | `C:\tmp\discord_token.txt` (one line, untracked, never paste in chat) |
| API base | `https://discord.com/api/v10`, header `Authorization: Bot <token>` |
| Bot permissions | Administrator (`permissions=8`), role must stay at the top of the role list |
| Working scripts | `C:\tmp\discord_*.py` + id map `C:\tmp\discord_ids.json` |

`discord_ids.json` holds `{roles, cats, chans}` name→id maps so later scripts can address
channels by key (`welcome`, `cat`, `wip`, `vote`, `bug_tr`, …) instead of re-resolving names.

## Structure (2026-08-21)

11 categories, 40 channels, **no voice channels** (deliberate — this is a work/support server).

```
📌 מידע            ברוכים-הבאים · חוקים · מפת-השרת · שאלות-נפוצות
📢 הכרזות          שחרורי-תרגומים · עדכוני-לאנצ'ר · עדכוני-אתר      (3 separate streams)
📚 קטלוג ומעקב     תרגומים-זמינים · בעבודה-עכשיו · מושהים-ובהמתנה · הצבעה-למשחק-הבא
🎮 משחקים · זמינים  one text channel per released game (10)
🚧 משחקים · בעבודה  one per actively-translating title (2)
🖥️ תוכנות · זמינות  signalrgb · virtualdj · borderless-gaming
🐛 דיווח באגים      forums: בתרגומים · באתר · בלאנצ'ר · הצעות-ושיפורים
🛠️ תמיכה           תמיכה-בהתקנה · בעיות-כלליות
🤝 קהילה           כללי · צילומי-מסך · אוף-טופיק
✍️ מתרגמים         תיאום-תרגום · מונחון · בקרת-איכות     (role-gated: ✍️ מתרגם)
🔒 צוות            צוות-כללי · לוגים                    (hidden)
```

Roles: `👑 מנהל` · `🛡️ מודרטור` · `✍️ מתרגם` · `🧪 בודק בטא` · `💎 תומך`.

## Design decisions

- **Bug reports are split by PRODUCT** (translation / website / launcher), not by game. Each is a
  forum with its own report template and status tags `חדש → אומת → בטיפול → תוקן`. The launcher
  forum names the log path `%USERPROFILE%\.translation_manager\launcher.log`.
- **Per-game channels mirror the LIVE catalog**, not the local repo state. Source of truth is
  `GET https://hebrew-translation-hub.com/api/games` (field `availability`:
  `available` / `in-progress` / `translating` / `coming-soon` / `paused` / `planned`, plus
  `isSoftware`). Only `available` + actively-translating titles get a channel; `paused` and
  `planned` are listed in the `⏸️ מושהים` / `🚧 בעבודה` info channels instead, so 50 catalog
  titles don't become 50 channels.
- **Game requests live on the website, not Discord.** `/vote` does authenticated voting plus
  "הוסיפו משחק להצבעה" (IGDB search, or manual name + cover upload). The old Discord request forum
  was deleted; `🗳️┃הצבעה-למשחק-הבא` is a read-only explainer that links to `/vote`.
- Every info channel and every game channel has **one pinned bot message** that is *replaced*
  (delete-then-post) on each sync, so content never accumulates duplicates.

## API gotchas hit while building this

- **Forums reject plain messages** (`50008 Cannot send messages in a non-text channel`). Create a
  post with `POST /channels/{id}/threads` + `{name, message:{content}}`.
- **Pinning a forum post** is not `PUT /pins/{id}` (returns `10008 Unknown Message`) — it's
  `PATCH /channels/{thread_id}` with `{"flags": 2}`.
- To edit a forum post's body later: `PATCH /channels/{thread_id}/messages/{thread_id}` — the
  starter message id equals the thread id.
- `GET /channels/{forum_id}/threads/active` 404s; use `GET /guilds/{guild}/threads/active` and
  filter by `parent_id`.
- **Channel names are sanitized by Discord** — apostrophes are stripped
  (`עדכוני-לאנצ'ר` → `עדכוני-לאנצר`). Don't rely on the name you sent for later lookups.
- Forum↔text conversion is impossible via API; changing a channel's type means delete + recreate.
- `permission_overwrites` values are **strings**, and `type: 0` = role, `1` = member.

## Re-running

Scripts are idempotent by name: they PATCH an existing channel/role of the same name instead of
creating a duplicate. To resync content after a catalog change, re-pull `/api/games` and re-run
`discord_sync2.py` (info channels), `discord_sync3.py` (FAQ + forums), `discord_sync4.py`
(per-game pins).
