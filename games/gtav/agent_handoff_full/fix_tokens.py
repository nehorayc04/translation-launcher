import json
with open('current_batch.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

d["Evade Epsilon's ~r~helicopter."] = "התחמק מ~r~מסוק האפסילון."
d["Evade Epsilon's ~r~security."] = "התחמק מ~r~אבטחת האפסילון."
d["Follow Epsilon's ~b~security."] = "עקוב אחרי ה~b~אבטחת האפסילון."

with open('current_batch.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=4)
