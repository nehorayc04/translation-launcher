import json, os
cfg_path = r"C:\Users\Nehoray_Cohen\Projects\Game translator\tools\fleet_dashboard\fleet_config.json"
cfg = json.load(open(cfg_path, encoding="utf-8"))

machines = [
    {"name": "desktop", "kind": "local", "dir": "C:/skyrimw"},
    {"name": "laptop", "kind": "ssh", "host": "10.0.0.49", "lan": "10.0.0.49", "port": 22, "user": "Nehoray_Cohen", "dir": "C:/Users/Nehoray_Cohen/Projects/skyrim_worker"},
    {"name": "vm4", "kind": "ssh", "host": "10.0.0.49", "lan": "10.0.0.49", "port": 2225, "user": "vboxuser", "dir": "C:/skyrimw"},
    {"name": "vm5", "kind": "ssh", "host": "10.0.0.49", "lan": "10.0.0.49", "port": 2226, "user": "vboxuser", "dir": "C:/skyrimw"},
    {"name": "vm", "kind": "ssh", "host": "127.0.0.1", "lan": "127.0.0.1", "port": 2222, "user": "vboxuser", "dir": "C:/skyrimw"},
    {"name": "vm2", "kind": "ssh", "host": "127.0.0.1", "lan": "127.0.0.1", "port": 2223, "user": "vboxuser", "dir": "C:/skyrimw"},
    {"name": "vm3", "kind": "ssh", "host": "127.0.0.1", "lan": "127.0.0.1", "port": 2224, "user": "vboxuser", "dir": "C:/skyrimw"}
]

skyrim_game = {
    "id": "skyrim",
    "title": "Skyrim Anniversary Edition — תרגום עידן חדש 2",
    "corpus_total": 99876,
    "fleet_dir": "games/skyrim/fleet",
    "bank_glob": "out_*.json",
    "shard_dir": "games/skyrim/fleet/shards",
    "pull_log": "C:/tmp/skyrim_pull.log",
    "pull_cadence_minutes": 5,
    "pusher_match": "skyrim_progress",
    "worker": "skyrim_nim",
    "task": "SkyrimMP",
    "pull_script": "pull_skyrim.sh",
    "machines": machines
}

for g in cfg["games"]:
    if g["id"] in ("rdr2", "corsair-cove"):
        g["machines"] = []

if not any(g["id"] == "skyrim" for g in cfg["games"]):
    cfg["games"].append(skyrim_game)
else:
    for g in cfg["games"]:
        if g["id"] == "skyrim":
            g.update(skyrim_game)

json.dump(cfg, open(cfg_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# Clean stream_ids.json
ids_path = r"C:\Users\Nehoray_Cohen\AppData\Local\FleetDash\stream_ids.json"
if os.path.exists(ids_path):
    ids = json.load(open(ids_path, encoding="utf-8"))
    new_ids = {}
    for k, v in ids.items():
        if k.startswith("rdr2") or k.startswith("corsair-cove") or k.startswith("skyrim"):
            pass # drop old rdr2/cc/skyrim
        else:
            new_ids[k] = v
    json.dump(new_ids, open(ids_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
