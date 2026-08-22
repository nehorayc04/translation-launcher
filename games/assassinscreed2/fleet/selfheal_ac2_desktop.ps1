$ErrorActionPreference = 'SilentlyContinue'
# Desktop (local) AC2 stream self-heal — MULTI-PROVIDER: 3 parallel workers (groq / sambanova /
# nim), each pinned to one provider and translating a disjoint 1/3 of the slice (md5 % 3).
# Registered as AC2Desktop (every 5 min) + AC2DesktopBoot.
# Matches ONLY 'ac2_nim.py <provider>' so it never touches a co-running pt_nim / w3_nim worker,
# and monitors each of the 3 provider workers independently.
$FLEET = 'C:\Users\Nehoray_Cohen\Projects\Game translator\games\assassinscreed2\fleet'
$WDIR = $FLEET + '\desktop_worker'
foreach ($p in @('groq', 'sambanova', 'nim')) {
    $run = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
            Where-Object { $_.CommandLine -match ('ac2_nim\.py ' + $p) }).ProcessId
    if (-not $run) {
        # Relaunch WINDOWLESS via wscript + hidden.vbs + the per-provider .bat (the .bat cd's to
        # desktop_worker, sets the provider arg, and >>-redirects stdout to a per-provider log).
        Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
            CommandLine      = ('wscript.exe "' + $FLEET + '\hidden.vbs" "' + $FLEET + '\run_ac2_' + $p + '.bat"')
            CurrentDirectory = $FLEET
        } | Out-Null
        Add-Content -Path ($WDIR + '\selfheal.log') -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' relaunched ac2_nim ' + $p + ' (was down)')
    }
}
