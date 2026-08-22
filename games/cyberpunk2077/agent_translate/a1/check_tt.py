import json
# Read to_translate and get exact values for rejected keys
tt = json.load(open("to_translate.json", encoding="utf-8"))
keys = ["onscreens/onscreens.json|20139","onscreens/onscreens.json|22030","onscreens/onscreens.json|27491","onscreens/onscreens.json|43811","onscreens/onscreens_final.json|44006","onscreens/onscreens_final.json|49902","onscreens/onscreens_final.json|49942","onscreens/onscreens_final.json|71918","onscreens/onscreens_final.json|77696","onscreens/onscreens_final.json|78393"]
for k in keys:
    v = tt.get(k, "NOT FOUND")
    print(f"{k}: {repr(v)}")
