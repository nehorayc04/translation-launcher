import json

b = json.load(open('batch_part1.json', encoding='utf-8'))
keys = sorted(b.keys(), key=lambda x: int(x))

with open('translate_part1_template.py', 'w', encoding='utf-8') as f:
    f.write('# -*- coding: utf-8 -*-\n')
    f.write('part1 = {\n')
    for k in keys:
        comment = b[k].replace('\n', '\\n').replace('\r', '\\r')
        f.write(f'    "{k}": "",  # {comment}\n')
    f.write('}\n')
print("Template 1 created successfully.")
