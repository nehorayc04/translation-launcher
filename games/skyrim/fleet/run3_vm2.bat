@echo off
cd /d %~dp0
start "" /B "C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe" -u skyrim_nim.py groq >> w_groq.log 2>&1
start "" /B "C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe" -u skyrim_nim.py sambanova >> w_sambanova.log 2>&1
start "" /B "C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe" -u skyrim_nim.py nim >> w_nim.log 2>&1
