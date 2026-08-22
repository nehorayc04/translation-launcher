import json

b = json.load(open('batch_part4.json', encoding='utf-8'))
keys = sorted(b.keys(), key=lambda x: int(x))

with open('translate_part4_template.py', 'w', encoding='utf-8') as f:
    f.write('# -*- coding: utf-8 -*-\n')
    f.write('part4 = {\n')
    for k in keys:
        eng = b[k].replace('\\n', '\n').replace('\\', '\\\\').replace('"', '\\"')
        # Replace actual newlines in comment to avoid syntax errors
        comment = b[k].replace('\n', '\\n').replace('\r', '\\r')
        f.write(f'    "{k}": "",  # {comment}\n')
    f.write('}\n')
print("Template created successfully.")
