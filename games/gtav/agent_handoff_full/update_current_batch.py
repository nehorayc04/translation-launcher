import json
import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
batch_path = os.path.join(HERE, "current_batch.json")

if os.path.exists(batch_path):
    with open(batch_path, "r", encoding="utf-8") as f:
        batch = json.load(f)
else:
    batch = {}

t_files = glob.glob(os.path.join(HERE, "t*.json")) + glob.glob(os.path.join(HERE, "b*.json"))
for t_file in t_files:
    with open(t_file, "r", encoding="utf-8") as f:
        try:
            t_data = json.load(f)
            for k, v in t_data.items():
                if k in batch:
                    batch[k] = v
        except json.JSONDecodeError as e:
            print(f"Error reading {t_file}: {e}")

with open(batch_path, "w", encoding="utf-8") as f:
    json.dump(batch, f, ensure_ascii=False, indent=4)

print(f"Updated current_batch.json with translations from {len(t_files)} files.")
