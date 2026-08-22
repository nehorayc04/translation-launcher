import os
HERE = os.path.dirname(os.path.abspath(__file__))
worker_path = os.path.join(HERE, "skyrim_nim.py")

with open(worker_path, "r", encoding="utf-8") as f:
    code = f.read()

# Fix glossary loading
old_gloss = """_GLOSS = {}
try:
    _reg = json.load(open(os.path.join(HERE, "brain_glossary.json"), encoding="utf-8"))
    for _term, _t in (_reg.get("terms") or {}).items():
        if _term and isinstance(_t, dict) and _t.get("he"):
            _GLOSS[_term] = _t["he"]
except Exception as _e:
    print("[gloss] none:", _e, flush=True)"""

new_gloss = """_GLOSS = {}
try:
    _reg = json.load(open(os.path.join(HERE, "brain_glossary.json"), encoding="utf-8"))
    if isinstance(_reg, dict): _reg = _reg.get("entries", [])
    for item in _reg:
        if isinstance(item, dict) and item.get("term") and item.get("he"):
            _GLOSS[item["term"]] = item["he"]
except Exception as _e:
    print("[gloss] none:", _e, flush=True)"""

code = code.replace(old_gloss, new_gloss)

with open(worker_path, "w", encoding="utf-8") as f:
    f.write(code)

print("Patched skyrim_nim.py")
