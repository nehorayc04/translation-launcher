@echo off
cd /d C:\fldw
set CC_BASE=https://pool.hebrew-translation-hub.com/cc
start "" /B "C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe" -u fl_worker.py groq >> w_groq.log 2>&1
start "" /B "C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe" -u fl_worker.py sambanova >> w_sambanova.log 2>&1
start "" /B "C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe" -u fl_worker.py nim >> w_nim.log 2>&1
