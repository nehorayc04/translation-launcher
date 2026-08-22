import json, re

TOKEN = re.compile(
    r'\[CSS_[A-Z]+\]'
    r'|\[[A-Z][A-Za-z0-9_]*\]'
    r'|\{[^}]*\}'
    r'|%[0-9.]*[diufslxX]+|%%'
    r'|&#?[A-Za-z0-9]+;'
)

src = json.load(open("to_translate.json", encoding="utf-8"))

for filename in ["trans_part_3.json", "trans_part_4.json"]:
    d = json.load(open(filename, encoding="utf-8"))
    for k in ["607527", "607529", "658323"]:
        if k in d:
            en = src[k]
            he = d[k]
            print(f"ID: {k}")
            print(f"en: {en!r}")
            print(f"he: {he!r}")
            print(f"en tokens: {TOKEN.findall(en)}")
            print(f"he tokens: {TOKEN.findall(he)}")
            print(f"Equal? {TOKEN.findall(en) == TOKEN.findall(he)}")
            print("-" * 50)
