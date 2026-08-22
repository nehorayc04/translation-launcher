$ErrorActionPreference = 'SilentlyContinue'
# Laptop PT self-heal: launch pt_nim.py if it isn't already running. Idempotent (guards duplicates).
# Runs as SYSTEM via schtasks (PTWorker every 5 min + PTWorkerBoot at startup). out.json = resumable.
# Matches ONLY 'pt_nim' so it never touches the co-running w3_nim laptop worker.
$PY   = 'C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
$WDIR = 'C:\Users\Nehoray_Cohen\Projects\pt_laptop_worker'
$run = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'pt_nim' }).ProcessId
if (-not $run) {
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine     = ('"' + $PY + '" -u "' + $WDIR + '\pt_nim.py"')
        CurrentDirectory = $WDIR
    } | Out-Null
    Add-Content -Path ($WDIR + '\selfheal.log') -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' relaunched pt_nim (was down)')
}
