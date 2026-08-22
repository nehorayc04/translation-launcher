@echo off
cd /d C:\sm2qa
start "" /B "C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe" -u sm2qa_nim.py groq >> w_groq.log 2>&1
start "" /B "C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe" -u sm2qa_nim.py sambanova >> w_sambanova.log 2>&1
start "" /B "C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe" -u sm2qa_nim.py nim >> w_nim.log 2>&1
