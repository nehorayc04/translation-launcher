"""OPERATOR — seed a game's corpus into the Turso cc queue (one game at a time;
finish it, then seed the next). Idempotent (ON CONFLICT DO NOTHING), fast
(multi-row INSERT). Input JSON, either:
  {"game":"skyrim","sys":"<prompt>","items":{"<string_key>":"<src panel>", ...}}
      (exactly cc_corpus.build_items output + a game name), OR
  [{"game":..,"target":..,"sys":..,"src":..}, ...]
Usage: python cc_seed.py corpus.json --game skyrim [--limit N]"""
import argparse, json, os, time
import turso_client as tc

COLS = ["id", "game", "target", "sys", "src", "status", "created_at", "updated_at"]
ROWS_PER_STMT, STMTS_PER_PIPE = 150, 8


def _rows(data, game):
    now = int(time.time())
    if isinstance(data, dict) and "items" in data:
        sysmsg = data.get("sys", "")
        g = game or data.get("game", "")
        if not g:
            raise SystemExit("no game (pass --game or put 'game' in the file)")
        for target, src in data["items"].items():
            yield (f"{g}|{target}", g, str(target), sysmsg, str(src), "open", now, now)
    else:  # list of row dicts
        for r in data:
            g = game or r.get("game", "")
            target = str(r["target"])
            yield (f"{g}|{target}", g, target, r.get("sys", ""), str(r["src"]), "open", now, now)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--game", default="")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    data = json.load(open(a.corpus, encoding="utf-8"))
    rows = list(_rows(data, a.game))
    if a.limit:
        rows = rows[: a.limit]
    # de-dup by id (a re-extract can repeat a key)
    seen, uniq = set(), []
    for r in rows:
        if r[0] not in seen:
            seen.add(r[0]); uniq.append(r)
    print(f"seeding {len(uniq):,} lines (game={a.game or '(from file)'})")
    ph = "(" + ",".join("?" * len(COLS)) + ")"
    done = 0
    for i in range(0, len(uniq), ROWS_PER_STMT * STMTS_PER_PIPE):
        chunk = uniq[i : i + ROWS_PER_STMT * STMTS_PER_PIPE]
        stmts = []
        for j in range(0, len(chunk), ROWS_PER_STMT):
            grp = chunk[j : j + ROWS_PER_STMT]
            sql = (f"INSERT INTO cc_lines({','.join(COLS)}) VALUES "
                   + ",".join([ph] * len(grp)) + " ON CONFLICT(id) DO NOTHING")
            stmts.append((sql, [v for row in grp for v in row]))
        tc.run(stmts)
        done += len(chunk)
        print(f"  {done:,}/{len(uniq):,}")
    st = tc.run([("SELECT COUNT(*) AS n FROM cc_lines WHERE game=? AND collected=0", [a.game or uniq[0][1]])])[0]["rows"][0]["n"]
    print(f"done. {st:,} live (uncollected) lines for this game in the queue.")


if __name__ == "__main__":
    main()
