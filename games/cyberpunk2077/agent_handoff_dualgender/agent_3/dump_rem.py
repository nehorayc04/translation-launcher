import json
d = json.load(open('current_batch.json', encoding='utf-8'))
out = []
for k, v in d.items():
    en = v.get('en', '')
    fem = v['he_female']
    out.append(k.split('|')[-1] + '\nEN: ' + en + '\nHE: ' + fem + '\n')

with open('remaining.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
