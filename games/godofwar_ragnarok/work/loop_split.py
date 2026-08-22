import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
batch = json.load(open(os.path.join(HERE,"current_batch.json"), encoding="utf-8"))
keys = sorted(batch.keys(), key=int)
size = (len(keys)+3)//4
for i in range(4):
    part = {k: batch[k] for k in keys[i*size:(i+1)*size]}
    json.dump(part, open(os.path.join(HERE,f"batch_part{i+1}.json"),"w",encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"batch_part{i+1}.json: {len(part)} strings")
