import json
import re

batch = json.load(open("to_translate_batch.json", encoding="utf-8"))
suspicious = []
for guid, val in batch.items():
    # If the text is an internal name (like Hidden_GoulashUnlock, Palmier_ElephantPool, Angereb_MarketStalls01)
    if "_" in val or re.match(r"^[A-Za-z0-9_]+$", val):
        suspicious.append((guid, val))

print(f"Suspicious keys count: {len(suspicious)}")
for guid, val in suspicious:
    print(f"  {guid}: {val}")
