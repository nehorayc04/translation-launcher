# ac2_ctl.ps1 - control the AC2 provider workers on THIS machine.
#   list    : show the live ac2_nim workers
#   kill    : stop ONLY ac2_nim workers (never another game's worker) + clear stale locks
#   ensure  : relaunch any missing provider (idempotent; safe to run on a timer)
#   restart : kill + ensure
#
# Runs on the VM (C:\ac2w, launched via the AC2MP scheduled task -> run3.bat) and on the
# desktop (fleet\desktop_worker, launched via run_ac2_<prov>.bat). A worker is matched by
# its command line, so a co-resident w3/pt worker is never touched.
param([string]$Action = "list")

$ErrorActionPreference = "SilentlyContinue"
$PROVIDERS = @('groq', 'sambanova', 'nim')

# --- machine layout: VM (C:\ac2w) or desktop (fleet\desktop_worker) -----------------
if (Test-Path 'C:\ac2w\ac2_nim.py') {
    $DIR = 'C:\ac2w'; $MODE = 'vm'
} else {
    $DIR = Join-Path $PSScriptRoot 'desktop_worker'; $MODE = 'desktop'
}

function Get-Workers {
    Get-CimInstance Win32_Process -Filter "name='python.exe'" |
        Where-Object { $_.CommandLine -match 'ac2_nim' }
}

function Get-Provider($cmdline) {
    foreach ($p in $PROVIDERS) { if ($cmdline -match "ac2_nim\.py\s+$p\b") { return $p } }
    return 'default'
}

switch ($Action) {

    'list' {
        $w = @(Get-Workers)
        foreach ($p in $w) { "{0,-8} pid {1}" -f (Get-Provider $p.CommandLine), $p.ProcessId }
        "count={0} mode={1} dir={2}" -f $w.Count, $MODE, $DIR
    }

    'kill' {
        foreach ($p in @(Get-Workers)) {
            Stop-Process -Id $p.ProcessId -Force
            "killed {0} ({1})" -f $p.ProcessId, (Get-Provider $p.CommandLine)
        }
        Start-Sleep -Seconds 2
        # a lock left by a killed worker would block its replacement forever
        Remove-Item (Join-Path $DIR 'worker*.lock') -Force
        "locks cleared"
    }

    'ensure' {
        # Relaunch only the providers that are NOT running. The worker's own singleton
        # lock makes a redundant launch harmless, but skipping saves the spawn.
        $live = @{}
        foreach ($p in @(Get-Workers)) { $live[(Get-Provider $p.CommandLine)] = $true }
        $missing = @($PROVIDERS | Where-Object { -not $live.ContainsKey($_) })
        if (-not $missing.Count) { "all {0} providers already alive" -f $PROVIDERS.Count; break }
        # a stale lock from a killed worker blocks its replacement forever
        foreach ($prov in $missing) { Remove-Item (Join-Path $DIR "worker_$prov.lock") -Force }
        if ($MODE -eq 'vm') {
            # Reuse run3.bat - the ONLY launcher proven to survive in session 0
            # (bat + start /B). It starts all three; the ones already running exit
            # immediately on their singleton lock, so this is idempotent.
            Start-Process cmd.exe -ArgumentList '/c', (Join-Path $DIR 'run3.bat') -WindowStyle Hidden
        } else {
            foreach ($prov in $missing) {
                $bat = Join-Path $PSScriptRoot "run_ac2_$prov.bat"
                $vbs = Join-Path $PSScriptRoot 'hidden.vbs'
                if ((Test-Path $vbs) -and (Test-Path $bat)) {
                    Start-Process wscript.exe -ArgumentList "`"$vbs`"", "`"$bat`"" -WindowStyle Hidden
                }
            }
        }
        "started: {0}" -f ($missing -join ', ')
    }

    'restart' {
        & $PSCommandPath kill
        & $PSCommandPath ensure
    }

    default { "usage: ac2_ctl.ps1 list|kill|ensure|restart" }
}
