# restart_translation.ps1
# Emergency restart for cp2077_fix_missing_translations.py
# Usage: Right-click -> "Run with PowerShell"  OR  pwsh -File restart_translation.ps1

$PY   = "C:\Users\nc528\AppData\Local\Programs\Python\Python313\python.exe"
$DIR  = "C:\Users\nc528\סקריפטים\תרגום משחקים"
$LOG  = "$DIR\fix_missing_translations.log"
$SCRIPT = "cp2077_fix_missing_translations.py"
$LM_URL = "http://127.0.0.1:1234/v1/models"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CP2077 Translation — Emergency Restart" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Kill all zombie processes ────────────────────────────────────────
Write-Host "[1/3] Killing zombie processes..." -ForegroundColor Yellow

$zombies = Get-WmiObject Win32_Process |
    Where-Object { $_.CommandLine -like "*$SCRIPT*" }

if ($zombies) {
    foreach ($z in $zombies) {
        try {
            Stop-Process -Id $z.ProcessId -Force -ErrorAction Stop
            Write-Host "      Killed PID $($z.ProcessId)" -ForegroundColor DarkGray
        } catch {
            Write-Host "      Could not kill PID $($z.ProcessId): $_" -ForegroundColor DarkRed
        }
    }
    Write-Host "      Done. Waiting 3s for LM Studio to settle..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 3
} else {
    Write-Host "      No zombie processes found." -ForegroundColor DarkGray
}

# ── Step 2: Ping LM Studio ───────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/3] Checking LM Studio ($LM_URL)..." -ForegroundColor Yellow

try {
    $resp = Invoke-RestMethod -Uri $LM_URL -Method Get -TimeoutSec 5 -ErrorAction Stop
    $models = $resp.data | ForEach-Object { $_.id }
    Write-Host "      LM Studio is ALIVE" -ForegroundColor Green
    Write-Host "      Loaded model(s): $($models -join ', ')" -ForegroundColor DarkGray
} catch {
    Write-Host ""
    Write-Host "  !! LM Studio is NOT responding !!" -ForegroundColor Red
    Write-Host "     Please start LM Studio, load your model, and re-run this script." -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Step 3: Launch single clean instance ────────────────────────────────────
Write-Host ""
Write-Host "[3/3] Starting translation (appending to log)..." -ForegroundColor Yellow

$proc = Start-Process "cmd.exe" `
    -ArgumentList "/c `"$PY -u $SCRIPT >> `"$LOG`" 2>&1`"" `
    -WorkingDirectory $DIR `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Seconds 2

if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) {
    Write-Host "      Launched PID $($proc.Id) — running in background." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Log file:  $LOG" -ForegroundColor Cyan
    Write-Host "  Monitor:   python cp2077_monitor.py" -ForegroundColor Cyan
} else {
    Write-Host "      Process exited immediately — check the log for errors:" -ForegroundColor Red
    Write-Host "      $LOG" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
