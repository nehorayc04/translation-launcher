import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))

machines = [
    {"name": "desktop", "dir": "C:/skyrimw", "ssh": None},
    {"name": "laptop", "dir": "C:/Users/Nehoray_Cohen/Projects/skyrim_worker", "ssh": "10.0.0.49", "port": 22, "user": "Nehoray_Cohen"},
    {"name": "vm4", "dir": "C:/skyrimw", "ssh": "10.0.0.49", "port": 2225, "user": "vboxuser"},
    {"name": "vm5", "dir": "C:/skyrimw", "ssh": "10.0.0.49", "port": 2226, "user": "vboxuser"},
    {"name": "vm", "dir": "C:/skyrimw", "ssh": "127.0.0.1", "port": 2222, "user": "vboxuser"},
    {"name": "vm2", "dir": "C:/skyrimw", "ssh": "127.0.0.1", "port": 2223, "user": "vboxuser"},
    {"name": "vm3", "dir": "C:/skyrimw", "ssh": "127.0.0.1", "port": 2224, "user": "vboxuser"}
]

files_to_copy = ["skyrim_nim.py", "fleet_providers.py", "brain_glossary.json"]

# Make sure we have fleet_providers.py
if not os.path.exists(os.path.join(HERE, "fleet_providers.py")):
    import shutil
    shutil.copy(os.path.join(HERE, "../../corsair_cove/fleet/fleet_providers.py"), os.path.join(HERE, "fleet_providers.py"))

key_path = os.path.expanduser("~/.ssh/id_ed25519")
ssho = ["-i", key_path, "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]

for m in machines:
    print(f"Deploying to {m['name']}...")
    is_local = (m["ssh"] is None)
    mdir = m["dir"]

    # 1. Create dir
    if is_local:
        os.makedirs(mdir, exist_ok=True)
    else:
        cmd = ["ssh"] + ssho + ["-p", str(m["port"]), f"{m['user']}@{m['ssh']}", f"cmd /c if not exist {mdir} mkdir {mdir}"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Copy base files
    for f in files_to_copy:
        src = os.path.join(HERE, f)
        if is_local:
            import shutil
            shutil.copy(src, os.path.join(mdir, f))
        else:
            cmd = ["scp"] + ssho + ["-P", str(m["port"]), src, f"{m['user']}@{m['ssh']}:{mdir}/{f}"]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 3. Copy shards
    for prov in ["groq", "sambanova", "nim"]:
        shard_src = os.path.join(HERE, "shards", f"corpus_{m['name']}_{prov}.json")
        if not os.path.exists(shard_src):
            print(f"  Missing {shard_src}")
            continue
        if is_local:
            shutil.copy(shard_src, os.path.join(mdir, f"corpus_{prov}.json"))
        else:
            cmd = ["scp"] + ssho + ["-P", str(m["port"]), shard_src, f"{m['user']}@{m['ssh']}:{mdir}/corpus_{prov}.json"]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 4. Generate and copy run3.bat
    py_path = r"C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe" if m["name"] in ("desktop", "laptop") else r"C:\Users\vboxuser\AppData\Local\Programs\Python\Python313\python.exe"
    if m["name"] in ("vm", "vm2", "vm3"): py_path = "python" # fallback if needed, but absolute is safer
    bat_content = f"@echo off\ncd /d {mdir}\n"
    for prov in ["groq", "sambanova", "nim"]:
        bat_content += f"start \"\" /B \"{py_path}\" -u skyrim_nim.py {prov} >> w_{prov}.log 2>&1\n"
    
    run3_src = os.path.join(HERE, f"run3_{m['name']}.bat")
    with open(run3_src, "w") as fh: fh.write(bat_content)

    if is_local:
        shutil.copy(run3_src, os.path.join(mdir, "run3.bat"))
    else:
        cmd = ["scp"] + ssho + ["-P", str(m["port"]), run3_src, f"{m['user']}@{m['ssh']}:{mdir}/run3.bat"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 5. Scheduled Tasks
    task_cmd = f"schtasks /create /tn SkyrimMP /tr \"cmd /c {mdir}\\run3.bat\" /sc minute /mo 5 /ru SYSTEM /rl HIGHEST /f"
    boot_cmd = f"schtasks /create /tn SkyrimMPBoot /tr \"cmd /c {mdir}\\run3.bat\" /sc onstart /ru SYSTEM /rl HIGHEST /f"
    
    if is_local:
        subprocess.run(task_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(boot_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["ssh"] + ssho + ["-p", str(m["port"]), f"{m['user']}@{m['ssh']}", task_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ssh"] + ssho + ["-p", str(m["port"]), f"{m['user']}@{m['ssh']}", boot_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("Deployed all.")
