# relaunch.ps1 — start ONLY the RDR2 workers that are not already running.
#
# 🔴 Two things the old `run3.bat` got wrong, and both cost throughput silently:
#
# 1. IT RELAUNCHED UNCONDITIONALLY. The 5-minute heal task fired a fresh `start "" /B`
#    for all three providers whether or not a healthy worker was mid-batch. Measured on
#    the live fleet: workers were replaced at EXACTLY 04:16:02 and 04:21:02 — the task
#    boundaries — so every stream got ~5 minutes, finished ~2 batches, and then threw
#    away its in-flight work and re-did the whole pass setup. A heal must be a NO-OP
#    when the thing it heals is alive.
#
# 2. `start "" /B` ATTACHES THE CHILD TO THE TASK'S CONSOLE. When the task's cmd.exe
#    returns, that console goes away and the workers go with it. `Start-Process` creates
#    an independent process instead, so the worker outlives the task that started it.
#
# The per-provider liveness test matches the COMMAND LINE (a bare pid is not an identity —
# Windows recycles pids), and the whole script is idempotent: run it as often as you like.
param([string]$Dir = 'C:\rdrw', [string]$Py = '')

if (-not $Py) {
    foreach ($c in @(
        'C:\Users\vboxuser\AppData\Local\Python\pythoncore-3.14-64\python.exe',
        'C:\Users\Nehoray_Cohen\AppData\Local\Programs\Python\Python313\python.exe')) {
        if (Test-Path $c) { $Py = $c; break }
    }
}
if (-not $Py -or -not (Test-Path $Dir)) { exit 1 }

$live = @()
foreach ($p in (Get-CimInstance Win32_Process -Filter "name='python.exe'" -EA SilentlyContinue)) {
    if ($p.CommandLine -match 'rdr2_nim\.py\s+(\w+)') { $live += $Matches[1] }
}

$started = @()
foreach ($prov in 'groq', 'sambanova', 'nim') {
    if ($live -contains $prov) { continue }
    # cmd (without /B and without start) WAITS for python, so this cmd's lifetime IS the
    # worker's lifetime and the >> append keeps the log history the task-based form lost.
    Start-Process -FilePath 'cmd.exe' `
        -ArgumentList '/c', ('"' + $Py + '" -u rdr2_nim.py ' + $prov + ' >> w_' + $prov + '.log 2>&1') `
        -WorkingDirectory $Dir -WindowStyle Hidden | Out-Null
    $started += $prov
}
Write-Output ("live=" + ($live -join ',') + " started=" + ($started -join ','))
