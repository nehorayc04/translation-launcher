$ErrorActionPreference = 'SilentlyContinue'
# "New Era" line-by-line QA REVIEW worker self-heal: launch w3qa_nim.py if not running.
# Idempotent (guards duplicates). SYSTEM via W3qaWorker (5 min) + W3qaWorkerBoot (onstart).
# Matches ONLY 'w3qa' so it never touches another worker (w3_nim / w3ut_nim / pt_nim).
# out.json = resumable state; the worker itself is PID-lock singleton.
$PY   = 'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$WDIR = 'C:\w3qa'
$run = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'w3qa_nim' }).ProcessId
if (-not $run) {
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine     = ('"' + $PY + '" -u "' + $WDIR + '\w3qa_nim.py"')
        CurrentDirectory = $WDIR
    } | Out-Null
    Add-Content -Path ($WDIR + '\selfheal.log') -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' relaunched w3qa_nim (was down)')
}
