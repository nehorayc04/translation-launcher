# -*- coding: utf-8 -*-
"""Fleet data collection for the dashboard — local banks + live remote probes.

Two clocks, deliberately separate, because they answer different questions:
  * LOCAL  (fast)  — the banks on this machine: what has actually been BANKED per stream, plus the
                     pull/pusher state. Cheap, so it can refresh every few seconds.
  * REMOTE (slow)  — one ssh per machine: is the pinned worker ALIVE, when did its out file last
                     move, what does its log tail say (429 / traceback / ALL DONE), free disk.

The remote probe sends PowerShell as -EncodedCommand (UTF-16LE base64). That is not a style choice:
plain ssh host "powershell ... C:/dir" silently LOSES its path argument (it lists the home dir
instead) and any nested quote turns into a different command. Encoding removes the whole class.

Every number the UI shows carries its own AGE, so a stale probe can never be presented as live.
"""
from __future__ import annotations

import base64
import glob
import io
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

CREATE_NO_WINDOW = 0x08000000          # standing rule: never flash a console window

SSH_CANDIDATES = [
    r"C:\Program Files\Git\usr\bin\ssh.exe",
    r"C:\Windows\System32\OpenSSH\ssh.exe",
    "ssh",
]
def _real_home() -> str:
    """The REAL user profile, not %USERPROFILE%.

    This tool is developed inside an Antigravity profile whose USERPROFILE/APPDATA are REDIRECTED,
    so os.path.expanduser("~") returns the sandboxed AntigravityProfiles path and the ssh key
    "does not exist" — the dashboard then dropped -i and every remote probe failed with nothing but
    ssh's banner on stderr. FOLDERID_Profile reads the token/registry and is right in both worlds.
    """
    try:
        import ctypes
        import ctypes.wintypes as wt
        import uuid

        class _G(ctypes.Structure):
            _fields_ = [("d1", wt.DWORD), ("d2", wt.WORD), ("d3", wt.WORD),
                        ("d4", ctypes.c_byte * 8)]

        g = uuid.UUID("5E6C858F-0E22-4760-9AFE-EA3317B67173")          # FOLDERID_Profile
        gs = _G(g.fields[0], g.fields[1], g.fields[2], (ctypes.c_byte * 8)(*g.bytes[8:]))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(gs), 0, None,
                                                      ctypes.byref(out)) == 0 and out.value:
            return out.value
    except Exception:
        pass
    return os.path.expanduser("~")


def _find_key() -> str:
    for h in (_real_home(), os.path.expanduser("~")):
        p = os.path.join(h, ".ssh", "id_ed25519")
        if os.path.exists(p):
            return p
    return os.path.join(_real_home(), ".ssh", "id_ed25519")


KEY = _find_key()


def _ssh_exe() -> str:
    for c in SSH_CANDIDATES:
        if os.path.sep in c and os.path.exists(c):
            return c
    return "ssh"                        # PATH fallback (may not exist under a service context)


def _run(cmd: list[str], timeout: int) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW)
        out = (p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")
        return p.returncode, out
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:                                          # missing ssh.exe, etc.
        return 125, f"{type(e).__name__}: {e}"


def powershell(script: str, timeout: int = 60) -> tuple[int, str]:
    b = base64.b64encode(script.encode("utf-16-le")).decode()
    return _run(["powershell.exe", "-NoProfile", "-EncodedCommand", b], timeout)


def _json_slice(text: str):
    """The remote may prepend an ssh banner/warning — take the outermost JSON object."""
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(text[i:j + 1])
    except Exception:
        return None


# --------------------------------------------------------------------------- remote probe

_PROBE = r"""
$ErrorActionPreference='SilentlyContinue'; $ProgressPreference='SilentlyContinue'
# 🔴 Force UTF-8 out. Windows PowerShell writes stdout in the console codepage and BEST-FIT-MAPS a
# smart quote to a plain ASCII quote: the workers' logs contain an em-dash that Get-Content reads as
# cp1252 U+201D, and on the way out it became a bare `"` INSIDE the JSON string — every probe came
# back as unparseable JSON while ssh reported success. The tail is also flattened to printable ASCII
# below, so no codepage anywhere in the chain can corrupt the payload.
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}
$dir='%DIR%'; $worker='%WORKER%'; $provs=@(%PROVS%); $zpat='%ZPAT%'
$procs = @(Get-CimInstance Win32_Process -Filter "name='python.exe'")
$res = @{}
foreach ($p in $provs) {
  $m = @($procs | Where-Object { $_.CommandLine -match ($worker + '\.py ' + $p) })
  $o = Join-Path $dir ("out_" + $p + ".json"); $l = Join-Path $dir ("w_" + $p + ".log")
  $c = Join-Path $dir ("corpus_" + $p + ".json")
  $oi = Get-Item $o; $ci = Get-Item $c
  # [string] is load-bearing: Get-Content returns strings DECORATED with note properties
  # (PSPath/PSDrive/PSProvider/...), and ConvertTo-Json serialises every one of them — the probe
  # came back as 449 KB of provider metadata that would not parse, instead of six log lines.
  $tail = @()
  if (Test-Path $l) {
    $tail = @(Get-Content $l -Tail 6 |
              ForEach-Object { ([string]$_) -replace '[^ -~]', '~' } |
              Where-Object { $_ -ne '' })
  }
  $res[$p] = @{
    alive   = $m.Count
    pid     = if ($m.Count) { $m[0].ProcessId } else { 0 }
    started = if ($m.Count) { $m[0].CreationDate.ToString('yyyy-MM-dd HH:mm:ss') } else { '' }
    out_age = if ($oi) { [int]((Get-Date) - $oi.LastWriteTime).TotalSeconds } else { -1 }
    out_size= if ($oi) { $oi.Length } else { 0 }
    corpus  = if ($ci) { $ci.Length } else { 0 }
    tail    = $tail
  }
}
$legacy = @($procs | Where-Object { $_.CommandLine -match ($worker + '\.py *$') }).Count
$zomb   = @($procs | Where-Object { $_.CommandLine -match $zpat } | ForEach-Object { $_.CommandLine })
$free = 0.0
try { $free = [math]::Round((Get-PSDrive C).Free / 1GB, 1) } catch {}
$t = Get-ScheduledTask -TaskName '%TASK%'
@{ ok=$true; providers=$res; legacy=$legacy; zombies=$zomb; free_gb=$free
   task=if ($t) { $t.State.ToString() } else { 'missing' }
   now=(Get-Date).ToString('HH:mm:ss') } | ConvertTo-Json -Depth 6 -Compress
"""


def _probe_script(machine: dict, game: dict, cfg: dict) -> str:
    provs = ",".join(f"'{p}'" for p in cfg["providers"])
    return (_PROBE.replace("%DIR%", machine["dir"])
            .replace("%WORKER%", game["worker"])
            .replace("%PROVS%", provs)
            .replace("%TASK%", game["task"])
            .replace("%ZPAT%", "|".join(cfg["zombie_patterns"])))


def _ssh_probe_once(machine: dict, host: str, script: str) -> tuple[int, str]:
    b = base64.b64encode(script.encode("utf-16-le")).decode()
    # ConnectTimeout is deliberately generous: a healthy guest running 3 LLM workers has been
    # measured answering only after >10s, and calling that "hung" is how a watchdog ends up
    # hard-power-cycling a working VM (which then NUL-truncates its out files).
    args = [_ssh_exe(), "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=45", "-p", str(machine["port"])]
    if os.path.exists(KEY):
        args += ["-i", KEY]
    args += [f"{machine['user']}@{host}",
             f"powershell -NoProfile -EncodedCommand {b}"]
    return _run(args, timeout=110)


def probe_machine(machine: dict, game: dict, cfg: dict) -> dict:
    """Returns the machine's live state. `ok=False` + `error` when the probe itself failed."""
    script = _probe_script(machine, game, cfg)
    if machine["kind"] == "local":
        rc, out = powershell(script, timeout=60)
    else:
        rc, out = _ssh_probe_once(machine, machine["host"], script)
        # The monitoring path (Tailscale) is a DIFFERENT link than the workers' own internet
        # access to the pool server -- a VPN drop only breaks THIS health check, not translation
        # itself. But since the same physical machine is also reachable over the plain LAN, a
        # failed/timed-out Tailscale hop retries once over `lan` before giving up, so a VPN
        # blip doesn't paint a live stream red.
        lan = machine.get("lan")
        if _json_slice(out) is None and lan and lan != machine["host"]:
            rc2, out2 = _ssh_probe_once(machine, lan, script)
            if _json_slice(out2) is not None:
                rc, out = rc2, out2
    data = _json_slice(out)
    if data is None:
        if rc == 124:
            reason = "ssh timeout / no answer"
        elif "{" in out:
            reason = "the machine answered but its JSON did not parse (codepage/output corruption)"
        else:
            reason = (out.strip().splitlines() or ["no output"])[-1]
        return {"ok": False, "error": reason[:200], "rc": rc, "raw_len": len(out)}
    data["ok"] = True
    return data


def probe_all(cfg: dict) -> dict:
    """All machines of all games in parallel — the slowest single probe sets the wall time."""
    jobs = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for g in cfg["games"]:
            for m in g["machines"]:
                jobs.append(((g["id"], m["name"]), ex.submit(probe_machine, m, g, cfg)))
        out = {}
        for key, fut in jobs:
            try:
                out[key] = fut.result()
            except Exception as e:
                out[key] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return out


BASH_CANDIDATES = ["C:/Program Files/Git/bin/bash.exe", "C:/Program Files/Git/usr/bin/bash.exe"]


def run_pull(cfg: dict, game: dict) -> str:
    """Fire this game's pull script, detached.

    The banks — and therefore the per-stream progress AND the sample feed — only move when a merge
    runs. CP2077 merges every 3 min but Witcher 3 only every 20, so an on-demand merge is a real
    need rather than a convenience.
    """
    bash = next((b for b in BASH_CANDIDATES if os.path.exists(b)), None)
    if not bash:
        return "לא נמצא bash.exe של Git"
    script = game.get("pull_script")
    if not script:
        return "לא הוגדר pull_script"
    fleet = os.path.join(cfg["repo"], game["fleet_dir"]).replace("\\", "/")
    lock = "/c/tmp/" + ("w3qa" if game["id"] == "witcher3" else "cpqa") + "_pull.lock"
    cmd = f"rm -f {lock}; cd '{fleet}' && bash {script} >> /c/tmp/dash_pull.log 2>&1"
    try:
        subprocess.Popen([bash, "-lc", cmd], creationflags=CREATE_NO_WINDOW,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"מיזוג {game['id']} הופעל ברקע — הנתונים יתעדכנו בעוד דקה"
    except Exception as e:
        return f"הפעלת המיזוג נכשלה: {type(e).__name__}"


# --------------------------------------------------------------------------- local state

class _JsonCache:
    """Parse a JSON file only when its mtime moved — the banks are 1-2 MB each, x21."""

    def __init__(self):
        self._c: dict[str, tuple[float, object]] = {}

    def keys_of(self, path: str) -> set | None:
        try:
            mt = os.path.getmtime(path)
        except OSError:
            return None
        hit = self._c.get(path)
        if hit and hit[0] == mt:
            return hit[1]
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
            val = set(d) if isinstance(d, dict) else set(map(str, d))
        except Exception:
            val = None                      # a NUL-truncated bank -> health check reports it
        self._c[path] = (mt, val)
        return val

    def dict_of(self, path: str) -> dict | None:
        try:
            mt = os.path.getmtime(path)
        except OSError:
            return None
        k = path + "#d"
        hit = self._c.get(k)
        if hit and hit[0] == mt:
            return hit[1]
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
            val = d if isinstance(d, dict) else None
        except Exception:
            val = None
        self._c[k] = (mt, val)
        return val


CACHE = _JsonCache()


def _plain_lines(v) -> list[str]:
    """Log tails must be plain strings — see the [string] note in the probe script."""
    if not v:
        return []
    if isinstance(v, str):
        v = [v]
    out = []
    for x in v:
        out.append(str(x.get("value", "")) if isinstance(x, dict) else str(x))
    return out


def bank_path(cfg: dict, game: dict, machine: dict, prov: str) -> str:
    root = os.path.join(cfg["repo"], game["fleet_dir"], "banks")
    if game["id"] == "witcher3":
        return os.path.join(root, f"qa_out_{machine['bank_index']}_{prov}.json")
    return os.path.join(root, f"out_{machine['name']}_{prov}.json")


def shard_path(cfg: dict, game: dict, machine: dict, prov: str) -> str:
    return os.path.join(cfg["repo"], game["shard_dir"], f"corpus_{machine['name']}_{prov}.json")


def local_processes(cfg: dict) -> dict:
    """One WMI call for this desktop: pinned workers, pushers, legacy + zombie forms."""
    zpat = "|".join(cfg["zombie_patterns"])
    script = (
        "$ProgressPreference='SilentlyContinue';"
        "$p=@(Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | %{$_.CommandLine});"
        "@{ all=$p;"
        f" zombies=@($p | ?{{$_ -match '{zpat}'}});"
        " pushers=@($p | ?{$_ -match '_progress'}) } | ConvertTo-Json -Depth 4 -Compress"
    )
    rc, out = powershell(script, timeout=40)
    d = _json_slice(out) or {}
    all_cmds = d.get("all") or []
    if isinstance(all_cmds, str):
        all_cmds = [all_cmds]
    for k in ("zombies", "pushers"):
        v = d.get(k) or []
        d[k] = [v] if isinstance(v, str) else v
    d["all"] = all_cmds
    return d


def vbox_running(cfg: dict) -> set[str]:
    vb = cfg.get("vbox", "")
    if not vb or not os.path.exists(vb):
        return set()
    rc, out = _run([vb, "list", "runningvms"], timeout=25)
    return {ln.split('"')[1] for ln in out.splitlines() if '"' in ln}


def tail_file(path: str, lines: int = 3) -> list[str]:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 8192))
            data = fh.read().decode("utf-8", "replace")
        return [x for x in data.splitlines() if x.strip()][-lines:]
    except Exception:
        return []


def file_age(path: str) -> float:
    try:
        return time.time() - os.path.getmtime(path)
    except OSError:
        return -1.0


# --------------------------------------------------------------------------- rate history

def _state_root() -> str:
    r"""%LOCALAPPDATA%\FleetDash — resolved from the REAL profile, not the environment.

    🔴 When this tool is launched from the Antigravity IDE, LOCALAPPDATA (and ~) point at a
    sandbox profile, while the user's own double-click gets the real one. That split means the
    same app reads two different prefs/stream-id files depending on who started it — the stream
    numbers I quote would not be the numbers the user sees. FOLDERID_Profile reads the token, so
    both runs agree.
    """
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 40, None, 0, buf) == 0 and buf.value:
            return os.path.join(buf.value, "AppData", "Local", "FleetDash")
    except Exception:
        pass
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "FleetDash")


def _hist_path() -> str:
    root = _state_root()
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, "history.json")


def load_history() -> dict:
    try:
        with open(_hist_path(), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_history(h: dict) -> None:
    try:
        tmp = _hist_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(h, fh)
        os.replace(tmp, _hist_path())
    except Exception:
        pass


# A single stream cannot plausibly gain more than this many "done" lines in one minute (batches
# cap at ~20-50 and take real seconds each) — a jump past it inside a short window is a SOURCE
# glitch (observed on the self-hosted pool: `cc_workers.done` intermittently reads back roughly
# double its true value for a tick, then reverts), not real throughput. Rejecting it here keeps
# one bad poll from producing an impossible rate like "1088/min" on the streams table.
_MAX_PLAUSIBLE_PER_MIN = 300


def push_history(h: dict, key: str, value: int, keep_minutes: int = 180) -> None:
    now = time.time()
    ser = h.setdefault(key, [])
    # ":community:devN" is a RANK slot (devices sorted by last_seen, N = position), not a
    # stable per-device identity — the underlying physical device behind "dev1" can change
    # between two ticks, so its "done" is allowed to jump either way. Neither guard below
    # applies to it; both would misread a legitimate slot handover as a glitch.
    is_rank_slot = ":community:dev" in key
    if ser:
        pt, pv = ser[-1]
        if not is_rank_slot:
            dt_min = (now - pt) / 60.0
            # Only guard SHORT windows — a big jump after a real idle gap (a stream that was
            # throttled for an hour and just cleared a backlog) is legitimate and must not be
            # silently dropped.
            if dt_min < 3.0 and dt_min > 0 and abs(value - pv) / dt_min > _MAX_PLAUSIBLE_PER_MIN:
                return                                # glitchy point — never enters history
            # `done` is a server-enforced monotonic counter (UPDATE ... SET done=done+?), so it
            # can NEVER legitimately go below the highest value already recorded for this
            # stream — even after a long idle gap (unlike a rate spike, a drop has no legitimate
            # explanation). Caught live: laptop:groq read 482, then 27 minutes later read 0 —
            # well past the short-window rate guard above, but impossible under the counter's
            # own contract.
            if value < max(v for _, v in ser):
                return
        if pv != value:
            ser.append([now, value])
    else:
        ser.append([now, value])
    cut = now - keep_minutes * 60
    h[key] = [p for p in ser if p[0] >= cut][-400:]


def rate_per_min(h: dict, key: str, window_minutes: int) -> float | None:
    """Lines/minute over the window. None when there is not enough history to be honest."""
    ser = h.get(key) or []
    if len(ser) < 2:
        return None
    cut = time.time() - window_minutes * 60
    pts = [p for p in ser if p[0] >= cut] or ser[-2:]
    if len(pts) < 2:
        return None
    dt = (pts[-1][0] - pts[0][0]) / 60.0
    if dt < 0.5:
        return None
    return max(0.0, (pts[-1][1] - pts[0][1]) / dt)


# --------------------------------------------------------------------------- snapshot

def _ids_path() -> str:
    return os.path.join(os.path.dirname(_hist_path()), "stream_ids.json")


def stream_ids(cfg: dict) -> dict:
    """Stable per-stream NUMBER, so a stream can be named "#7" instead of game·machine·provider.

    It is a persisted registry, not a row index: filtering, sorting or hiding a game never moves a
    number, and a number is never reused. First run seeds 1..N in config order (games → machines →
    providers); a machine added later simply takes the next free number.
    """
    path = _ids_path()
    ids: dict = {}
    try:
        with io.open(path, encoding="utf-8") as fh:
            ids = json.load(fh)
    except Exception:
        ids = {}
    nxt = max(ids.values(), default=0) + 1
    changed = False
    for g in cfg["games"]:
        for m in g["machines"]:
            for p in cfg["providers"]:
                k = f"{g['id']}:{m['name']}:{p}"
                if k not in ids:
                    ids[k] = nxt
                    nxt += 1
                    changed = True
    if changed:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with io.open(tmp, "w", encoding="utf-8") as fh:
                json.dump(ids, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, path)
        except Exception:
            pass
    return ids


# --------------------------------------------------------------------------- community compute
# Some games are translated by VOLUNTEER PHONES (BYOK), not the NIM fleet — no banks, no VMs.
# The source is the community control plane -- Turso (libSQL), reached ONLY through the mod
# Worker's secret-gated /cc/* routes (NOT the site's Supabase; that pool was retired 2026-xx after
# it filled Supabase's free tier and nearly broke login -- see community_compute/control_plane/
# turso/README.md). Each game is surfaced with one stream per ACTIVE device so it sits in the same
# fleet table. Marked cc=True so health.py skips its NIM-fleet rules (no "pull frozen" / "worker
# dead" false findings).
#
# 🔴 THE GAME IS DISCOVERED, NEVER HARDCODED. `/cc/detail` returns one row per game that still has
# open+claimed lines; a finished game (0 remaining) simply drops off the board on its own.
#
# דור 3 (תשתית): Turso now hard-blocks ALL reads on this DB (plan quota), so the old
# Worker/Turso route above is DEAD - it returns nothing, which is exactly what made the
# WHOLE fleet read as "3.6 hours stale / stuck" here even while every stream was genuinely
# producing on the self-hosted server. The dashboard was quietly polling a corpse.
# The self-hosted server uses a SEPARATE admin secret from the worker secret (CC_SECRET) -
# this constant is CC_ADMIN_SECRET on the server's .env, not CC_SECRET. Left carrying the OLD
# Cloudflare-Worker-era value once, every /cc/detail call 401'd -> the dashboard fell back to
# its zero-defaults for EVERY pool stream (remaining "0/0", every row flagged "not reporting" /
# stale) even though the fleet was genuinely healthy - the exact same "false stuck fleet" shape
# as the dead-URL bug above, just one field over.
_CC_BASE = os.environ.get("CC_BASE") or "https://pool.hebrew-translation-hub.com/cc"
_CC_ADMIN_SECRET = os.environ.get("CC_ADMIN_SECRET") or "1c8089923916f19e3e2ec025945b693e147b90f8ab7e6788"
# display names; an unknown game falls back to its own id, so a new seed still renders correctly
_CC_TITLES = {
    "hogwarts": "הוגוורטס לגאסי · קהילה",
    "ratchet-rift-apart": "רצ'ט אנד קלאנק · קהילה",
    "crimson-desert": "Crimson Desert · קהילה",
}


def _cc_detail(ttl: float = 10.0):
    """ONE /cc/detail per tick, shared by the pool-mode fleet loop and collect_cc.

    Both need the same snapshot; without the cache a pool-mode game would cost two
    round trips per refresh and the two halves of the board could disagree (the
    fleet row built from one snapshot, the volunteer rows from another taken a
    second later).
    """
    now = time.time()
    if _CC_CACHE["data"] is not None and now - _CC_CACHE["t"] < ttl:
        return _CC_CACHE["data"]
    d = _cc_call("detail")
    if isinstance(d, dict):
        _CC_CACHE["data"], _CC_CACHE["t"] = d, now
    return _CC_CACHE["data"]


def pool_wid(machine: dict, prov: str, prefix: str = "cd") -> str:
    """The pool worker id a fleet machine enrols under: <prefix>-<COMPUTERNAME>-<provider>.

    `cc_worker.py` builds it from CD_MACHINE/COMPUTERNAME, which is NOT the short name
    this config uses (the guest called `vm2` reports WIN11-VM-2), so the mapping is
    pinned per machine as `pool_id` instead of being guessed from `name`.

    `prefix` defaults to "cd" (crimson-desert's cc_worker.py, unchanged) — a second
    pool-mode game on the SAME machines (e.g. 007's fl_worker.py, worker id "fl-...")
    sets its own `worker_prefix` in fleet_config.json so its streams resolve too,
    instead of permanently reading pool_missing=True.
    """
    return f"{prefix}-{machine.get('pool_id') or machine['name']}-{prov}".lower()


_CC_CACHE: dict = {"t": 0.0, "data": None}


def _cc_call(op: str, timeout: int = 15, tries: int = 3):
    """POST to a /cc/* admin route (x-cc-secret: CC_ADMIN_SECRET). RETRIES on purpose: a single
    transient failure would make every community row VANISH from the board -- a disappearance
    reads as "the fleet stopped", which is worse than a stale number."""
    import urllib.request
    body = json.dumps({}).encode("utf-8")
    for i in range(max(1, tries)):
        req = urllib.request.Request(
            _CC_BASE + "/" + op, body,
            {"x-cc-secret": _CC_ADMIN_SECRET, "Content-Type": "application/json",
             "User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception:
            if i + 1 < max(1, tries):
                time.sleep(1.0 + i)
    return None


def _cc_ids(game: str, n: int) -> dict:
    """Stable numbers for a community game's device streams, in the same persisted registry."""
    path = _ids_path()
    ids: dict = {}
    try:
        with io.open(path, encoding="utf-8") as fh:
            ids = json.load(fh)
    except Exception:
        ids = {}
    nxt = max(ids.values(), default=0) + 1
    changed = False
    for k in range(n):
        key = f"{game}:community:dev{k + 1}"
        if key not in ids:
            ids[key] = nxt; nxt += 1; changed = True
    if changed:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with io.open(tmp, "w", encoding="utf-8") as fh:
                json.dump(ids, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, path)
        except Exception:
            pass
    return ids


def collect_cc(hist: dict, win: int, owned: set | None = None):
    """[(game, streams), ...] for every ACTIVE community-compute game, or None if unreachable.

    The control plane can hold several seeds at once (a finished one still sits in cc_lines
    until its results are collected), so this returns a LIST and skips any game with no work
    left — otherwise a completed run keeps a stale row on the board and its finished lines get
    added to the live game's totals.

    `owned` = pool ids a POOL-MODE fleet game already renders. Those are skipped here or the
    same queue would appear twice: once as the fleet row (with its own machines) and once as a
    community row, double-counting every line in the totals.
    """
    detail = _cc_detail()
    if not isinstance(detail, dict):
        return None
    games = detail.get("games") or []
    all_workers = detail.get("workers") or []
    if not isinstance(games, list) or not isinstance(all_workers, list):
        return None
    out = []
    for g in games:
        gid = str(g.get("game") or "").strip()
        if gid in (owned or set()):
            continue
        gopen = int(g.get("open", 0)); gclaimed = int(g.get("claimed", 0)); gdone = int(g.get("done", 0))
        if not gid or (gopen + gclaimed) <= 0:
            continue                       # finished seed — off the board
        title = _CC_TITLES.get(gid, gid + " · קהילה")
        total = gopen + gclaimed + gdone
        # DISTINCT key namespace: the main VM-fleet loop pushes its own (much larger) aggregate
        # done-count under f"game:{gid}" for this SAME game id -- sharing that key interleaved two
        # unrelated series into one history, and whenever a community-sized point landed right
        # after a VM-fleet-sized point the delta read as a decrease -> rate clamped to a false 0.
        push_history(hist, f"cc-game:{gid}", gdone)
        grate = rate_per_min(hist, f"cc-game:{gid}", win) or 0.0   # None on the first tick
        # Which active devices belong to THIS game. cc_workers has no persistent per-worker game
        # column -- a worker's "game" here is inferred from its CURRENTLY-claimed batch, which is
        # empty for a device that just submitted and hasn't claimed its next batch yet (a normal,
        # frequent moment). That made a perfectly healthy 2nd device flicker out of the table. Only
        # ONE game is ever seeded at a time in practice, so when that's the case every active device
        # unambiguously belongs to it; the claim-based join is kept only as a fallback for the rare
        # moment several games are live at once, where a momentarily-idle device can be missed.
        gworkers = sorted(
            all_workers if len(games) == 1
            else [w for w in all_workers if str(w.get("game") or "") == gid],
            key=lambda w: -int(w.get("last_seen", 0) or 0))
        n = len(gworkers)
        ids = _cc_ids(gid, max(n, 1))
        per = max(n, 1)
        streams = []
        for k, w in enumerate(gworkers):
            key = f"{gid}:community:dev{k + 1}"
            plat = str(w.get("platform") or "").strip() or "מכשיר"
            streams.append({
                "num": ids.get(key, 0),
                "game": gid, "game_title": title,
                "machine": f"{plat} {k + 1}", "provider": "community",
                # remaining is the SHARED pool's open+claimed (all devices draw from one queue,
                # not a private shard) -- 0 here is what health.py reads as "finished" and mislabels
                # a still-working device "סיים" the moment the game itself still has work open.
                "shard": total // per, "done": int(w.get("done", 0) or 0), "remaining": gopen + gclaimed,
                "rate": grate / per, "alive": 1, "pid": 0, "started": "",
                "out_age": 0.0, "corpus_bytes": 0, "tail": [], "probe_ok": True,
                "probe_error": "", "kind": "community",
            })
        out.append(({
            "merge_age": 0.0, "cc": True,
            "id": gid, "title": title, "total": total, "done": gdone,
            "worker": "", "task": "", "remaining": gopen + gclaimed, "rate": grate,
            "rows": gdone, "dupes": 0, "corrupt": [],
            "pull_age": 0.0, "pull_tail": "", "pull_cadence": 1,
            "pusher_match": "cc_progress.py", "streams": streams, "machines": [],
        }, streams))
    return out or None


def collect(cfg: dict, remote: dict | None, hist: dict) -> dict:
    """Build the full snapshot the UI renders. `remote` may be None/partial (first tick)."""
    remote = remote or {}
    snap = {"t": time.time(), "games": [], "local": local_processes(cfg),
            "vbox": vbox_running(cfg), "streams": []}
    win = cfg["refresh"]["rate_window_minutes"]
    ids = stream_ids(cfg)

    owned_pools: set[str] = set()
    for g in cfg["games"]:
        pool = g.get("pool")
        wprefix = g.get("worker_prefix", "cd")
        banks_dir = os.path.join(cfg["repo"], g["fleet_dir"], "banks")
        union: set[str] = set()
        rows = 0
        corrupt: list[str] = []
        # In POOL MODE there are no local banks at all — every answer goes straight to the
        # queue — so parsing them would report 0 done and a permanently "frozen merge".
        if not pool:
            for f in glob.glob(os.path.join(banks_dir, g["bank_glob"])):
                k = CACHE.keys_of(f)
                if k is None:
                    corrupt.append(os.path.basename(f))
                    continue
                union |= k
                rows += len(k)

        gtot = g["corpus_total"]
        prow: dict = {}
        wmap: dict = {}
        pool_open = pool_claimed = pool_done = 0
        if pool:
            owned_pools.add(pool)
            det = _cc_detail() or {}
            prow = next((x for x in (det.get("games") or [])
                         if str(x.get("game") or "") == pool), {}) or {}
            wmap = {str(w.get("id") or "").lower(): w for w in (det.get("workers") or [])}
            pool_open = int(prow.get("open", 0) or 0)
            pool_claimed = int(prow.get("claimed", 0) or 0)
            pool_done = int(prow.get("done", 0) or 0)

        if pool:
            # The queue only holds what is still OUTSTANDING: the lines banked before the
            # migration are not in it. So progress is measured from the remainder (exact),
            # while the RATE rides the pool's own strictly-increasing done counter.
            gremaining = pool_open + pool_claimed
            gdone = max(0, gtot - gremaining)
            push_history(hist, f"pool:{pool}", pool_done)
            grate = rate_per_min(hist, f"pool:{pool}", win)
        else:
            gdone = len(union)
            gremaining = max(0, gtot - gdone)
            push_history(hist, f"game:{g['id']}", gdone)
            grate = rate_per_min(hist, f"game:{g['id']}", win)

        gstreams = []
        for m in g["machines"]:
            for p in cfg["providers"]:
                key = f"{g['id']}:{m['name']}:{p}"
                pr = (remote.get((g["id"], m["name"])) or {})
                pdat = ((pr.get("providers") or {}).get(p) or {}) if pr.get("ok") else {}
                if pool:
                    # done/claimed come from the pool's own per-worker row; liveness still
                    # comes from the ssh probe, which is the only thing that can tell a
                    # crashed worker from one that is merely being refused by its provider.
                    w = wmap.get(pool_wid(m, p, wprefix)) or {}
                    # The pool drops a worker from /cc/detail once it has been silent for a
                    # full lease (20 min). Absent + ALIVE is a real, otherwise-invisible
                    # failure: the process is up but it is not talking to the queue.
                    pool_missing = not w
                    done = int(w.get("done", 0) or 0)
                    shard_n = int(w.get("claimed", 0) or 0)   # what this stream holds RIGHT NOW
                    seen = int(w.get("last_seen", 0) or 0)
                    # out_age is "how long since this stream last talked to the pool" — the
                    # pool-mode equivalent of the out-file mtime the shard model watched.
                    out_age = max(0.0, time.time() - seen) if seen else -1.0
                    remaining = gremaining                    # one shared queue, not a private slice
                else:
                    sh = CACHE.keys_of(shard_path(cfg, g, m, p))
                    bk = CACHE.keys_of(bank_path(cfg, g, m, p))
                    shard_n = len(sh) if sh else 0
                    done = len(sh & bk) if (sh and bk) else 0
                    out_age = pdat.get("out_age", -1)
                    remaining = max(0, shard_n - done)
                    pool_missing = False
                push_history(hist, key, done)
                gstreams.append({
                    "num": ids.get(key, 0),
                    "game": g["id"], "game_title": g["title"], "machine": m["name"], "provider": p,
                    "shard": shard_n, "done": done, "remaining": remaining,
                    "rate": rate_per_min(hist, key, win),
                    "alive": pdat.get("alive", -1), "pid": pdat.get("pid", 0),
                    "started": pdat.get("started", ""),
                    "out_age": out_age, "corpus_bytes": pdat.get("corpus", 0),
                    "tail": _plain_lines(pdat.get("tail")),
                    "probe_ok": bool(pr.get("ok")), "probe_error": pr.get("error", ""),
                    "kind": m["kind"], "pool": bool(pool), "pool_missing": pool_missing,
                })
        if pool and g.get("community", True):
            # The volunteer phones draw from the SAME queue, so they belong in this game's row
            # rather than a separate "community" one - that is the whole point of one pool.
            # 🔴 A SECOND pool-mode game on the same cc_server (007) has NO volunteer client of
            # its own — every android device is a crimson-desert-only app — so `"community":
            # false` in that game's config keeps this block from ever running for it. Without
            # that flag a device with no CURRENTLY claimed line (op_detail only reports "game"
            # while one is held) has game=None and would show up under BOTH games' rows on
            # whichever tick catches it between batches.
            devs = [w for w in wmap.values()
                    if str(w.get("platform") or "") != "windows-fleet"
                    and w.get("game") in (pool, None)
                    and str(w.get("id") or "").lower() not in
                    {pool_wid(m, p, wprefix) for m in g["machines"] for p in cfg["providers"]}]
            devs.sort(key=lambda w: -int(w.get("last_seen", 0) or 0))
            dids = _cc_ids(pool, max(len(devs), 1))
            for k, w in enumerate(devs):
                dkey = f"{pool}:community:dev{k + 1}"
                push_history(hist, dkey, int(w.get("done", 0) or 0))
                seen = int(w.get("last_seen", 0) or 0)
                gstreams.append({
                    "num": dids.get(dkey, 0),
                    "game": g["id"], "game_title": g["title"],
                    "machine": f"{str(w.get('platform') or 'מכשיר')} {k + 1}",
                    "provider": "community",
                    "shard": int(w.get("claimed", 0) or 0), "done": int(w.get("done", 0) or 0),
                    "remaining": gremaining, "rate": rate_per_min(hist, dkey, win),
                    "alive": 1, "pid": 0, "started": "",
                    "out_age": max(0.0, time.time() - seen) if seen else -1.0,
                    "corpus_bytes": 0, "tail": [], "probe_ok": True, "probe_error": "",
                    "kind": "community", "pool": True,
                })
        snap["streams"] += gstreams

        # The pull's freshness is measured on what it PRODUCES (the newest bank file), not on a log
        # path — pull_w3qa.sh prints to stdout, so a missing log file is not a frozen merge.
        bank_files = [] if pool else glob.glob(os.path.join(banks_dir, g["bank_glob"]))
        newest = min([file_age(f) for f in bank_files] or [-1.0])
        pull_log = g["pull_log"]
        snap["games"].append({
            "merge_age": newest, "pool": pool or "",
            "pool_open": pool_open, "pool_claimed": pool_claimed, "pool_done": pool_done,
            "id": g["id"], "title": g["title"], "total": gtot, "done": gdone,
            # health.py names these in its findings ("run this task", "kill that worker form")
            "worker": g["worker"], "task": g["task"],
            "remaining": gremaining, "rate": grate,
            "rows": rows, "dupes": max(0, rows - gdone), "corrupt": corrupt,
            "pull_age": file_age(pull_log), "pull_tail": tail_file(pull_log, 2),
            "pull_cadence": g["pull_cadence_minutes"],
            "pusher_match": g["pusher_match"],
            "streams": gstreams,
            "machines": [{**m, "probe": remote.get((g["id"], m["name"]))} for m in g["machines"]],
        })

    # community-compute (volunteer phones) — appended so it sits in the same table. May be
    # SEVERAL games; each one that still has work gets its own entry. A pool-mode fleet game
    # already renders its own queue (fleet streams + that queue's volunteer devices), so its
    # id is excluded here to avoid a duplicate row with double-counted totals.
    for game, gstreams in (collect_cc(hist, win, owned_pools) or []):
        snap["streams"] += gstreams
        snap["games"].append(game)

    # grouped by game, ascending by each stream's own fixed number (#1-21+) — the persisted
    # registry hands each game a contiguous number block, so sorting on "num" alone groups by
    # game AND reads in ascending stream order everywhere this snapshot is rendered (the streams
    # table, the overview cards, once_text).
    snap["streams"].sort(key=lambda s: (s.get("num", 0), s["game"]))
    for g in snap["games"]:
        g["streams"].sort(key=lambda s: (s.get("num", 0), s["game"]))
    snap["games"].sort(key=lambda g: min((s.get("num", 0) for s in g["streams"]), default=0))
    return snap


# --------------------------------------------------------------------------- samples

def _bank_entry(v, src):
    """(iss, he_new) for a bank value, whichever KIND of fleet wrote it.

    🔴 A REVIEW fleet banks {id: {"he":…, "iss":…}} while a TRANSLATION fleet banks
    {id: "hebrew"} — a bare string. Assuming the review shape crashed the whole app with
    `'str' object has no attribute 'get'` the moment RDR2 (a translation run) appeared.
    A fresh translation has no "before", so it is labelled as new rather than as a fix.
    """
    if isinstance(v, dict):
        return v.get("iss", "?"), (v.get("he") or "")
    return ("new", str(v or ""))


def _pool_samples(g: dict, ids: dict, seen: dict, limit: int) -> list[dict]:
    """Newly-submitted lines for a POOL-MODE game, read from each worker's samples.jsonl.

    A pool client writes no bank, so the bank-diff the shard model used has nothing to
    read. `cc_worker.py` therefore appends {id, en, he} for every line it submits, and
    this tails those files. Only machines that are LOCAL are read here (an ssh read per
    tick would cost more than the feed is worth) — remote streams still show their state
    and their log tail in the streams table.
    """
    out: list[dict] = []
    for m in g["machines"]:
        if m.get("kind") != "local":
            continue
        path = os.path.join(m["dir"], "samples.jsonl")
        try:
            with io.open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()[-60:]
        except Exception:
            continue
        key = f"pool-samples:{g['id']}:{m['name']}"
        prev = seen.get(key)
        # Anchor on the last line we already emitted rather than on a COUNT: the file is
        # trimmed when it grows, and only its tail is read, so a count would silently
        # re-emit or skip lines every time either of those shifts.
        if prev is None:
            fresh = lines[-4:]          # seed, so the pane is useful on the first tick
        elif prev in lines:
            fresh = lines[lines.index(prev) + 1:][-12:]
        else:
            fresh = lines[-2:]          # trimmed past our anchor - resync on the newest
        seen[key] = lines[-1] if lines else prev
        for ln in fresh:
            try:
                r = json.loads(ln)
            except Exception:
                continue
            prov = str(r.get("prov") or "")
            out.append({
                "t": float(r.get("t") or time.time()),
                "num": ids.get(f"{g['id']}:{m['name']}:{prov}", 0),
                "game": g["id"], "machine": m["name"], "provider": prov,
                "id": str(r.get("id") or ""), "iss": "new",
                "en": str(r.get("en") or "")[:300], "he_old": "",
                "he_new": str(r.get("he") or "")[:300],
                "seed": prev is None,
            })
    return out[:limit]


def latest_samples(cfg: dict, _snap: dict, seen: dict, limit: int = 40) -> list[dict]:
    """Newly-banked lines since the previous tick, with their English + before/after Hebrew.

    The bank only stores {id: {he, iss}} — the ENGLISH and the ORIGINAL Hebrew live in the shard the
    stream is working on, which is why the reslice writes those shards to a stable path.
    """
    out = []
    ids = stream_ids(cfg)
    for g in cfg["games"]:
        if g.get("pool"):
            out += _pool_samples(g, ids, seen, limit)
            continue
        for m in g["machines"]:
            for p in cfg["providers"]:
                bp = bank_path(cfg, g, m, p)
                bd = CACHE.dict_of(bp)
                if not bd:
                    continue
                key = f"{g['id']}:{m['name']}:{p}"
                prev = seen.get(key)
                cur = set(bd)
                if prev is None:
                    seen[key] = cur
                    # Seed from the TAIL of the bank: a worker appends as it banks, and dicts keep
                    # insertion order, so the last keys are the newest reviewed lines. Without this
                    # the pane is blank until the next merge (20 min on Witcher 3).
                    sd0 = CACHE.dict_of(shard_path(cfg, g, m, p)) or {}
                    for k in list(bd)[-4:]:
                        src = sd0.get(k) or {}
                        iss, he_new = _bank_entry(bd.get(k), src)
                        out.append({"t": time.time(), "num": ids.get(f"{g['id']}:{m['name']}:{p}", 0),
                                    "game": g["id"], "machine": m["name"],
                                    "provider": p, "id": k, "iss": iss,
                                    "en": (src.get("en") or "")[:300],
                                    "he_old": (src.get("he") or "")[:300],
                                    "he_new": he_new[:300], "seed": True})
                    continue
                new = cur - prev
                seen[key] = cur
                if not new:
                    continue
                sd = CACHE.dict_of(shard_path(cfg, g, m, p)) or {}
                for k in list(new)[:12]:
                    src = sd.get(k) or {}
                    iss, he_new = _bank_entry(bd.get(k), src)
                    out.append({
                        "t": time.time(), "num": ids.get(f"{g['id']}:{m['name']}:{p}", 0),
                        "game": g["id"], "machine": m["name"], "provider": p,
                        "id": k, "iss": iss,
                        "en": (src.get("en") or "")[:300],
                        "he_old": (src.get("he") or "")[:300],
                        "he_new": he_new[:300],
                    })
    out.sort(key=lambda r: r["iss"] == "ok")            # show real fixes before plain "ok" rows
    return out[:limit]
