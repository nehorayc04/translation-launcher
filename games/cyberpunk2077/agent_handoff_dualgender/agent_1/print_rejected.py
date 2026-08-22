import json

with open('current_batch.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

# we know which are rejected because they still have 'fixed_male': 'SKIP'
count = 0
for k, v in d.items():
    if v.get('fixed_male') == 'SKIP':
        print(f"KEY: {k}")
        print(f"HEB: {v['he_female']}")
        print("---")
        count += 1
print(f"Total rejected: {count}")
