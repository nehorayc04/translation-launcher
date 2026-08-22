$ErrorActionPreference = 'SilentlyContinue'
# Per-VM self-heal: launch w3_nim.py if it isn't already running. Idempotent (guards duplicates).
# Runs as SYSTEM via schtasks (W3Worker every 5 min + W3WorkerBoot at startup) => auto-resume after
# a crash OR a VM reboot, with NO dependency on the desktop's SSH heal. out.json = resumable state.
$PY   = 'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$WDIR = 'C:\w3w'
$run = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'w3_nim' }).ProcessId
if (-not $run) {
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine     = ('"' + $PY + '" -u "' + $WDIR + '\w3_nim.py"')
        CurrentDirectory = $WDIR
    } | Out-Null
    Add-Content -Path ($WDIR + '\selfheal.log') -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' relaunched w3_nim (was down)')
}
