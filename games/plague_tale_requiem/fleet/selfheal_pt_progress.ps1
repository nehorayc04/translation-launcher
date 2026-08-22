$ErrorActionPreference = 'SilentlyContinue'
$PY   = 'C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe'
$WDIR = 'C:\Users\Nehoray_Cohen\Projects\Game translator\games\plague_tale_requiem\fleet'
$VBS  = 'C:\Users\Nehoray_Cohen\Projects\Game translator\games\plague_tale_requiem\fleet\hidden.vbs'
$run = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'pt_progress' }).ProcessId
if (-not $run) {
    $bat = Join-Path $WDIR 'run_pt_progress.bat'
    Set-Content -Path $bat -Value ('@echo off' + "`r`n" + '"' + $PY + '" -u "' + $WDIR + '\pt_progress.py"') -Encoding ascii
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine=('wscript.exe "' + $VBS + '" "' + $bat + '"'); CurrentDirectory=$WDIR } | Out-Null
}
