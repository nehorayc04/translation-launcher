@echo off
REM Register per-VM auto-resume: W3Worker (every 5 min self-heal) + W3WorkerBoot (at startup), as SYSTEM.
schtasks /Create /TN W3Worker     /TR "powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\w3w\selfheal.ps1" /SC MINUTE /MO 5 /RU SYSTEM /RL HIGHEST /F
schtasks /Create /TN W3WorkerBoot /TR "powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\w3w\selfheal.ps1" /SC ONSTART            /RU SYSTEM /RL HIGHEST /F
schtasks /Query  /TN W3Worker     /FO LIST | findstr /I "TaskName Status"
schtasks /Query  /TN W3WorkerBoot /FO LIST | findstr /I "TaskName Status"
