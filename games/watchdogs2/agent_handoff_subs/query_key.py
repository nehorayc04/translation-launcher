import json
to = json.load(open("to_translate.json", encoding="utf-8"))
print("684415" in to)
if "684415" in to:
    print(to["684415"])
