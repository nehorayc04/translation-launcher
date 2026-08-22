# Deploy an OFFLINE PACKAGE that was appended to this setup executable.
#
# The website can build a ONE-FILE offline installer: it takes the real launcher
# setup and appends the translations the visitor picked, as
#
#     [ setup .exe bytes ][ bundle .zip bytes ][ int64 zip length ][ 'TMOFFPK1' ]
#
# Appended bytes are inert for Inno Setup (it reads its own data by offsets from
# the header), so the file stays a perfectly normal installer for anyone who does
# not care about the payload. This script runs from [Run] AFTER the install and
# unpacks that payload into the launcher's offline store, so the user's whole
# flow is "download one file, run it" - no manual copying or extracting.
#
# It is a NO-OP (exit 0) when the trailer is absent, which is the case for every
# normally-published installer.
#
# Run as the ORIGINAL user (Inno's `runasoriginaluser`), NOT elevated: the store
# must land in the profile of the person who will actually run the launcher.
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string] $Setup,
  # Override only for testing; the launcher reads exactly this path.
  [string] $Dest = (Join-Path $env:USERPROFILE '.translation_manager\offline_bundle')
)

$ErrorActionPreference = 'Stop'
$MAGIC = [Text.Encoding]::ASCII.GetBytes('TMOFFPK1')
$TRAILER = 16          # int64 length + 8-byte magic

function Fail([string]$msg, [int]$code) { Write-Host "offline-bundle: $msg"; exit $code }

if (-not (Test-Path -LiteralPath $Setup)) { Fail "setup not found: $Setup" 0 }

$tmpZip = Join-Path $env:TEMP ("tm_offline_" + [guid]::NewGuid().ToString('N') + ".zip")
$fs = [IO.File]::OpenRead($Setup)
try {
  if ($fs.Length -lt ($TRAILER + 64)) { Fail 'file too small - no payload' 0 }

  # --- read the trailer -----------------------------------------------------
  [void]$fs.Seek(-$TRAILER, [IO.SeekOrigin]::End)
  $tr = New-Object byte[] $TRAILER
  if ($fs.Read($tr, 0, $TRAILER) -ne $TRAILER) { Fail 'short read' 0 }
  for ($i = 0; $i -lt 8; $i++) {
    if ($tr[8 + $i] -ne $MAGIC[$i]) { Fail 'no payload appended (normal installer)' 0 }
  }
  $len = [BitConverter]::ToInt64($tr, 0)
  if ($len -le 0 -or $len -gt ($fs.Length - $TRAILER)) { Fail "bad payload length: $len" 0 }

  # --- copy the payload out (streamed - the package can be hundreds of MB) ---
  [void]$fs.Seek($fs.Length - $TRAILER - $len, [IO.SeekOrigin]::Begin)
  $out = [IO.File]::Create($tmpZip)
  try {
    $buf = New-Object byte[] (1MB)
    $left = $len
    while ($left -gt 0) {
      $want = [Math]::Min([int64]$buf.Length, $left)
      $n = $fs.Read($buf, 0, [int]$want)
      if ($n -le 0) { break }
      $out.Write($buf, 0, $n)
      $left -= $n
    }
    if ($left -ne 0) { Fail 'payload truncated' 0 }
  } finally { $out.Dispose() }
} finally { $fs.Dispose() }

# --- expand into the launcher's offline store --------------------------------
# Never wipe the folder: a user may already carry a package for other games, and
# a per-file overwrite merges the two instead of destroying the older one.
try {
  New-Item -ItemType Directory -Force -Path $Dest | Out-Null
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $zip = [IO.Compression.ZipFile]::OpenRead($tmpZip)
  try {
    $root = [IO.Path]::GetFullPath($Dest)
    foreach ($e in $zip.Entries) {
      if (-not $e.Name) { continue }                       # directory entry
      $target = [IO.Path]::GetFullPath((Join-Path $root $e.FullName))
      # zip-slip guard: never let an entry escape the store
      if (-not $target.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { continue }
      New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null
      [IO.Compression.ZipFileExtensions]::ExtractToFile($e, $target, $true)
    }
  } finally { $zip.Dispose() }
  Write-Host "offline-bundle: deployed to $Dest"
} catch {
  Write-Host "offline-bundle: extract failed - $($_.Exception.Message)"
  exit 0            # never fail the install over the bonus payload
} finally {
  Remove-Item -LiteralPath $tmpZip -Force -ErrorAction SilentlyContinue
}
exit 0
