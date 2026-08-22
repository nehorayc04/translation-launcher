$ErrorActionPreference = 'SilentlyContinue'
# Per-VM self-heal: launch ac2_nim.py if it isn't already running. Idempotent (guards duplicates).
# Runs as SYSTEM via schtasks (AC2Worker every 5 min + AC2WorkerBoot at startup) => auto-resume
# after a crash OR a VM reboot. out.json = the resumable state.
# Matches ONLY 'ac2_nim' so it never touches a co-running pt_nim / w3_nim worker.
$PY   = 'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
if (-not (Test-Path $PY)) { $PY = 'C:\Users\vboxuser\AppData\Local\Python\bin\python.exe' }
$WDIR = 'C:\ac2w'
$run = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'ac2_nim' }).ProcessId
if (-not $run) {
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine      = ('"' + $PY + '" -u "' + $WDIR + '\ac2_nim.py"')
        CurrentDirectory = $WDIR
    } | Out-Null
    Add-Content -Path ($WDIR + '\selfheal.log') -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' relaunched ac2_nim (was down)')
}
