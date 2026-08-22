import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
src = json.load(open(os.path.join(HERE, "to_translate.json"), encoding="utf-8"))
he = json.load(open(os.path.join(HERE, "hebrew.json"), encoding="utf-8"))
skip = set(json.load(open(os.path.join(HERE, "skip.json"), encoding="utf-8")))

todo = {k: src[k] for k in src if k not in he and k not in skip}
with open(os.path.join(HERE, "remaining_todo.json"), "w", encoding="utf-8") as f:
    json.dump(todo, f, indent=1, ensure_ascii=False)
print(f"Wrote {len(todo)} keys to remaining_todo.json")
