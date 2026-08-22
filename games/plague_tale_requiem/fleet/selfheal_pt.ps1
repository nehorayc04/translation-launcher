$ErrorActionPreference = 'SilentlyContinue'
# Per-VM self-heal: launch pt_nim.py if it isn't already running. Idempotent (guards duplicates).
# Runs as SYSTEM via schtasks (PTWorker every 5 min + PTWorkerBoot at startup) => auto-resume after
# a crash OR a VM reboot, with NO dependency on the desktop's SSH heal. out.json = resumable state.
# Matches ONLY 'pt_nim' so it never touches a co-running w3_nim worker.
$PY   = 'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$WDIR = 'C:\ptw'
$run = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'pt_nim' }).ProcessId
if (-not $run) {
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine     = ('"' + $PY + '" -u "' + $WDIR + '\pt_nim.py"')
        CurrentDirectory = $WDIR
    } | Out-Null
    Add-Content -Path ($WDIR + '\selfheal.log') -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' relaunched pt_nim (was down)')
}
