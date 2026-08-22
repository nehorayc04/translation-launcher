<#
  Registers Big Launch as a Windows "home app", so it appears in
  Settings > Gaming > XBOX mode > "בחר אפליקציית בית" alongside XBOX itself.

  ONLY Big Launch. The regular launcher is a windowed desktop app - a home app is
  what the full-screen experience boots INTO and drives with a pad, and offering a
  mouse-first window there would be an entry that looks wrong the moment it opens.

  Loose registration (-Register on the manifest) is the developer-mode path: no
  .msix is built and nothing is signed, so the Windows SDK is not needed. The
  package carries no files of its own - -ExternalLocation points it at the real
  install folder, and the exe named in the manifest is resolved from there.

  Re-running is safe. Pass -Unregister to take the entry back out.
#>
param(
  [string] $InstallDir = 'C:\Program Files\Translation Manager',
  [switch] $Unregister
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$Name   = 'HebrewTranslationHub.BigLaunch'
$Folder = 'biglaunch'
$Exe    = 'BigLaunch.exe'

$full = Get-AppxPackage | Where-Object Name -eq $Name
if ($Unregister) {
  if ($full) { Remove-AppxPackage -Package $full.PackageFullName; "removed $Name" }
  else       { "not registered: $Name" }
  return
}

# 🔴 VERIFY THE TARGET EXISTS BEFORE REGISTERING. A sparse package whose
# executable is missing still registers happily and still shows up in the picker -
# it just does nothing when chosen, which reads as "the home app is broken"
# rather than "the shell is not installed".
$exe = Join-Path $InstallDir $Exe
if (-not (Test-Path $exe)) { "skipped - no $exe"; return }

# 🔴 THE DESCRIPTOR AND THE TILE ART ARE READ FROM THE EXTERNAL LOCATION, NOT FROM
# THE PACKAGE FOLDER. Both were proven the hard way:
#   * the .sccd - deployment searches "<ExternalLocation>\*.sccd" (the deployment
#     log says exactly that; the PowerShell error only says "cannot find the file
#     specified" and names no file at all);
#   * Assets\ - with the folder present the picker shows the real logo, and with
#     the SAME package re-registered after renaming it away, it falls back to the
#     generic placeholder. One variable, both directions.
# Writing into Program Files needs elevation, so an unelevated run can only
# proceed once the files are already there (the installer puts them there).
$needs = @{
  'CustomCapability.SCCD' = Join-Path $here "$Folder\CustomCapability.SCCD"
  'Assets'                = Join-Path $here "$Folder\Assets"
}
foreach ($rel in $needs.Keys) {
  $dst = Join-Path $InstallDir $rel
  if (-not (Test-Path $dst)) { Copy-Item $needs[$rel] $dst -Recurse -Force }
}

$manifest = Join-Path $here "$Folder\AppxManifest.xml"

# 🔴 A RE-REGISTER DOES NOT RELOCATE THE PACKAGE. Registering the same identity
# from a different folder reports success and leaves InstallLocation pointing at
# the OLD one - so running this from the install folder after a first run from the
# source tree silently keeps the app tied to the source tree, and moving that
# folder later breaks the home-app entry. Only a remove actually moves it.
if ($full -and $full.InstallLocation -and
    $full.InstallLocation -ne (Split-Path -Parent $manifest)) {
  Remove-AppxPackage -Package $full.PackageFullName
}

# 🔴 A FAILED REGISTRATION IS NOT A FAILED INSTALL. The descriptor is the
# development form, which Windows only honours while the machine is developer-
# unlocked; on an ordinary machine this throws, and it must stay a missing
# home-app entry rather than an installer that reports failure over an extra.
try {
  Add-AppxPackage -Register $manifest -ExternalLocation $InstallDir -ErrorAction Stop
  "registered $Name -> $exe"
} catch {
  "FAILED $Name`: $($_.Exception.Message)"
}
