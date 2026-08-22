import os

script_path = r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\corsair_cove\fleet\cc_progress.py"
with open(script_path, "r", encoding="utf-8") as f:
    code = f.read()

code = code.replace("cc_progress_hist.json", "skyrim_progress_hist.json")

with open(r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\skyrim\fleet\skyrim_progress.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Created skyrim_progress.py")
