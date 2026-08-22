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

# We pull keys from their rdr2/cc directories on the SAME machine to C:/skyrimw
source_dirs = {
    "desktop": "C:/ccw",
    "laptop": "C:/Users/Nehoray_Cohen/Projects/rdr2_worker",
    "vm4": "C:/rdr2w",
    "vm5": "C:/rdr2w",
    "vm": "C:/ccw",
    "vm2": "C:/ccw",
    "vm3": "C:/ccw"
}

key_path = os.path.expanduser("~/.ssh/id_ed25519")
ssho = ["-i", key_path, "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]

for m in machines:
    print(f"Deploying fixed worker and keys to {m['name']}...")
    is_local = (m["ssh"] is None)
    mdir = m["dir"]
    src_dir = source_dirs[m["name"]]

    # Copy fixed worker
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skyrim_nim.py")
    if is_local:
        import shutil
        shutil.copy(src, os.path.join(mdir, "skyrim_nim.py"))
        try: shutil.copy(os.path.join(src_dir, "keys.json"), os.path.join(mdir, "keys.json"))
        except Exception: pass
    else:
        cmd = ["scp"] + ssho + ["-P", str(m["port"]), src, f"{m['user']}@{m['ssh']}:{mdir}/skyrim_nim.py"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Copy keys locally on the remote machine
        cmd = ["ssh"] + ssho + ["-p", str(m["port"]), f"{m['user']}@{m['ssh']}", f"cmd /c copy {src_dir.replace('/','\\\\')}\\keys.json {mdir.replace('/','\\\\')}\\keys.json"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # restart workers
    cmd = "schtasks /run /tn SkyrimMP"
    if is_local:
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["ssh"] + ssho + ["-p", str(m["port"]), f"{m['user']}@{m['ssh']}", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("Redeployed all.")
