import json, os, re, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
EN = json.load(open(os.path.join(HERE,"to_translate.json"), encoding="utf-8"))
TOK = r"\[\[S:[^\]]*\]\]|\[\[D:[^\]]*\]\]|\[/?style[^\]]*\]|\[/?i\]|\[Icons:[^\]]*\]|\[[A-Za-z][^\]]*Button\]|%d|%s|\\n|\\p"
new = {}
for i in range(1,5):
    new.update(json.load(open(os.path.join(HERE,f"trans_part_{i}.json"), encoding="utf-8")))
bad = [k for k,v in new.items() if k in EN and re.findall(TOK,EN[k]) != re.findall(TOK,v)]
if bad:
    for k in bad:
        en_tags = [t.encode('ascii', errors='ignore').decode('ascii') for t in re.findall(TOK, EN[k])]
        he_tags = [t.encode('ascii', errors='ignore').decode('ascii') for t in re.findall(TOK, new[k])]
        print(f"TAG MISMATCH {k} | EN: {en_tags} | HE: {he_tags}")
    raise SystemExit(f"{len(bad)} tag mismatches — fix those ids and rerun")
heb = json.load(open(os.path.join(HERE,"hebrew.json"), encoding="utf-8"))
heb.update(new)
fd, tmp = tempfile.mkstemp(dir=HERE, suffix=".tmp")
with os.fdopen(fd,"w",encoding="utf-8") as f:
    json.dump(heb, f, ensure_ascii=False, indent=1)
os.replace(tmp, os.path.join(HERE,"hebrew.json"))
print(f"merged {len(new)} | hebrew.json total {len(heb)}")
