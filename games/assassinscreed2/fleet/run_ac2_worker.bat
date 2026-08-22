@echo off
cd /d "%~dp0desktop_worker"
"C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe" -u ac2_nim.py >> C:\tmp\ac2_desktop_worker.log 2>&1
