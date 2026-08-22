@echo off
cd /d %~dp0
start "" /B "C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe" -u skyrim_nim.py groq >> w_groq.log 2>&1
start "" /B "C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe" -u skyrim_nim.py sambanova >> w_sambanova.log 2>&1
start "" /B "C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe" -u skyrim_nim.py nim >> w_nim.log 2>&1
