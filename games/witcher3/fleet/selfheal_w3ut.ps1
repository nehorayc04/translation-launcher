$ErrorActionPreference = 'SilentlyContinue'
# vm5 "New Era" TRANSLATE+multi-lang-gender worker self-heal: launch w3ut_nim.py if not running.
# Idempotent (guards duplicates). SYSTEM via W3utWorker (5 min) + W3utWorkerBoot (onstart). Matches
# ONLY 'w3ut' so it never touches any other worker (w3_nim / pt_nim). out.json = resumable state.
$PY   = 'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$WDIR = 'C:\w3ut'
$run = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'w3ut_nim' }).ProcessId
if (-not $run) {
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine     = ('"' + $PY + '" -u "' + $WDIR + '\w3ut_nim.py"')
        CurrentDirectory = $WDIR
    } | Out-Null
    Add-Content -Path ($WDIR + '\selfheal.log') -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' relaunched w3ut_nim (was down)')
}
