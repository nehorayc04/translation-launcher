import json

for i in range(1, 5):
    b = json.load(open(f'batch_part{i}.json', encoding='utf-8'))
    keys = sorted(b.keys(), key=lambda x: int(x))
    with open(f'translate_part{i}_template.py', 'w', encoding='utf-8') as f:
        f.write('# -*- coding: utf-8 -*-\n')
        f.write(f'part{i} = {{\n')
        for k in keys:
            comment = b[k].replace('\n', '\\n').replace('\r', '\\r')
            # Escape double quotes in comment to avoid script issues, and wrap safely
            comment_escaped = comment.replace('\\', '\\\\').replace('"', '\\"')
            f.write(f'    "{k}": "",  # {comment_escaped}\n')
        f.write('}\n')
    print(f"Template {i} created successfully with {len(keys)} keys.")
