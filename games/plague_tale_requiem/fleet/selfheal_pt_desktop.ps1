$ErrorActionPreference = 'SilentlyContinue'
# Desktop PT self-heal: launch the desktop_worker pt_nim.py if it isn't already running. Idempotent.
# Runs via schtasks (PTDeskWorker every 5 min + PTDeskWorkerBoot at logon). Matches ONLY the desktop
# pt_nim (CommandLine contains 'desktop_worker') so it never touches a VM's remote worker or w3_nim.
$PY   = 'C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
$WDIR = 'C:\Users\Nehoray_Cohen\Projects\Game translator\games\plague_tale_requiem\fleet\desktop_worker'
$VBS  = 'C:\Users\Nehoray_Cohen\Projects\Game translator\games\plague_tale_requiem\fleet\hidden.vbs'
$run = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'plague_tale_requiem\\fleet\\desktop_worker' -or $_.CommandLine -match 'desktop_worker.*pt_nim' }).ProcessId
if (-not $run) {
    # write a tiny run.bat once, launch it hidden via wscript so no cmd window pops
    $bat = Join-Path $WDIR 'run_pt.bat'
    Set-Content -Path $bat -Value ('@echo off' + "`r`n" + '"' + $PY + '" -u "' + $WDIR + '\pt_nim.py"') -Encoding ascii
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine     = ('wscript.exe "' + $VBS + '" "' + $bat + '"')
        CurrentDirectory = $WDIR
    } | Out-Null
    Add-Content -Path ($WDIR + '\selfheal.log') -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' relaunched desktop pt_nim (was down)')
}
