import json
import write_part1

part1_source = json.load(open("batch_part1.json", encoding="utf-8"))
keys = sorted(part1_source.keys(), key=lambda x: int(x))

existing = write_part1.part1

with open("write_part1_combined.py", "w", encoding="utf-8") as f:
    f.write("# -*- coding: utf-8 -*-\n")
    f.write("part1 = {\n")
    for k in keys:
        eng = part1_source[k]
        comment = eng.replace('\n', '\\n').replace('\r', '\\r').replace('\\', '\\\\').replace('"', '\\"')
        if k in existing:
            val = existing[k].replace('"', '\\"')
            f.write(f'    "{k}": "{val}",  # {comment}\n')
        else:
            f.write(f'    "{k}": "",  # {comment}\n')
    f.write("}\n\n")
    f.write('import json\n')
    f.write('with open("trans_part_1.json", "w", encoding="utf-8") as f:\n')
    f.write('    json.dump(part1, f, ensure_ascii=False, indent=4)\n')
    f.write('print("Part 1 written successfully.")\n')

print("Combined script written to write_part1_combined.py")
