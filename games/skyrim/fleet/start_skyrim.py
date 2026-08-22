import os, subprocess, sys

machines = [
    {"name": "desktop", "dir": "C:/skyrimw", "ssh": None},
    {"name": "laptop", "dir": "C:/Users/Nehoray_Cohen/Projects/skyrim_worker", "ssh": "10.0.0.49", "port": 22, "user": "Nehoray_Cohen"},
    {"name": "vm4", "dir": "C:/skyrimw", "ssh": "10.0.0.49", "port": 2225, "user": "vboxuser"},
    {"name": "vm5", "dir": "C:/skyrimw", "ssh": "10.0.0.49", "port": 2226, "user": "vboxuser"},
    {"name": "vm", "dir": "C:/skyrimw", "ssh": "127.0.0.1", "port": 2222, "user": "vboxuser"},
    {"name": "vm2", "dir": "C:/skyrimw", "ssh": "127.0.0.1", "port": 2223, "user": "vboxuser"},
    {"name": "vm3", "dir": "C:/skyrimw", "ssh": "127.0.0.1", "port": 2224, "user": "vboxuser"}
]

key_path = os.path.expanduser("~/.ssh/id_ed25519")
ssho = ["-i", key_path, "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]

for m in machines:
    print(f"Starting {m['name']}...")
    is_local = (m["ssh"] is None)
    
    cmd = "schtasks /run /tn SkyrimMP"
    if is_local:
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["ssh"] + ssho + ["-p", str(m["port"]), f"{m['user']}@{m['ssh']}", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("Started all streams.")
