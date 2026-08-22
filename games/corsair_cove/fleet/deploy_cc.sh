#!/bin/bash
# Deploy the Corsair Cove fleet to streams 13-21 = vm / vm2 / vm3 (local VirtualBox,
# 127.0.0.1:2222-4), 3 pinned providers each.
#
# Rules this encodes, each learned the hard way:
#   * a worker launched over ssh DIES with the session — only a `.bat` run by the machine's own
#     SYSTEM scheduled task persists in session 0. So we scp files and then run the TASK.
#   * `start "" /B` inside that .bat is what actually detaches the 3 provider workers, and the
#     `>> w_<prov>.log 2>&1` gives each a real stdout (a console-less SYSTEM process has a broken
#     one, and sys.stdout.reconfigure can crash on it).
#   * keys are per-MACHINE (each VM has its own provider accounts) and come from the shared
#     secrets file — they are NEVER committed. Pass KEYDIR=<dir holding keys_<machine>.json>.
#
#   KEYDIR=/path/to/scratch bash deploy_cc.sh            deploy all three
#   KEYDIR=... bash deploy_cc.sh vm2                     one machine
set -u
FLEET="$(cd "$(dirname "$0")" && pwd)"
KEY=~/.ssh/id_ed25519
U=vboxuser
H=127.0.0.1
RD="C:/ccw"
SSHO="-i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=25"
KEYDIR="${KEYDIR:-}"

port_of() { case "$1" in vm) echo 2222;; vm2) echo 2223;; vm3) echo 2224;; *) echo "";; esac; }

MACHINES="${*:-vm vm2 vm3}"
for M in $MACHINES; do
  P=$(port_of "$M")
  [ -z "$P" ] && { echo "!! unknown machine $M"; continue; }
  echo "=== $M (port $P) ==="

  ssh $SSHO -p "$P" "$U@$H" "cmd /c if not exist C:\\ccw mkdir C:\\ccw" >/dev/null 2>&1

  # worker + adapter + glossary + launcher
  for f in cc_nim.py fleet_providers.py name_registry.json; do
    scp $SSHO -P "$P" "$FLEET/$f" "$U@$H:$RD/$f" >/dev/null 2>&1 \
      && echo "  -> $f" || echo "  !! FAILED $f"
  done
  if [ -f "$KEYDIR/run3.bat" ]; then
    scp $SSHO -P "$P" "$KEYDIR/run3.bat" "$U@$H:$RD/run3.bat" >/dev/null 2>&1 && echo "  -> run3.bat"
  fi

  # this machine's three DISJOINT per-provider shards
  for prov in groq sambanova nim; do
    src="$FLEET/shards/corpus_${M}_${prov}.json"
    [ -f "$src" ] || { echo "  !! missing shard $src"; continue; }
    scp $SSHO -P "$P" "$src" "$U@$H:$RD/corpus_${prov}.json" >/dev/null 2>&1 \
      && echo "  -> corpus_${prov}.json ($(wc -c <"$src") B)" || echo "  !! FAILED corpus_${prov}"
  done

  # per-machine provider keys (never in the repo)
  if [ -n "$KEYDIR" ] && [ -f "$KEYDIR/keys_${M}.json" ]; then
    scp $SSHO -P "$P" "$KEYDIR/keys_${M}.json" "$U@$H:$RD/keys.json" >/dev/null 2>&1 \
      && echo "  -> keys.json" || echo "  !! FAILED keys.json"
  else
    echo "  !! no keys_${M}.json in KEYDIR — worker will have no providers"
  fi

  # SYSTEM tasks: CcMP re-launches every 5 min (the singleton lock makes that idempotent and
  # is what heals a dead provider stream), CcMPBoot brings the machine back after a reboot.
  ssh $SSHO -p "$P" "$U@$H" \
    "schtasks /create /tn CcMP /tr \"cmd /c C:\\ccw\\run3.bat\" /sc minute /mo 5 /ru SYSTEM /rl HIGHEST /f" >/dev/null 2>&1 \
    && echo "  -> task CcMP (every 5 min)" || echo "  !! task CcMP FAILED"
  ssh $SSHO -p "$P" "$U@$H" \
    "schtasks /create /tn CcMPBoot /tr \"cmd /c C:\\ccw\\run3.bat\" /sc onstart /ru SYSTEM /rl HIGHEST /f" >/dev/null 2>&1 \
    && echo "  -> task CcMPBoot (on start)" || echo "  !! task CcMPBoot FAILED"
done
echo
echo "start them with:  bash $(basename "$0" .sh | sed 's/deploy/start/').sh   (or: schtasks /run /tn CcMP)"
