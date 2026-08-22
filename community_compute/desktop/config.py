# -*- coding: utf-8 -*-
"""Baked constants for the desktop worker.

SUPABASE_URL + ANON_KEY are the project's PUBLIC values (the anon key already
ships in the website + launcher — it is safe to embed; RLS + the SECURITY
DEFINER RPCs are the real gate). APP_SECRET is a soft gate against random spam;
it is discoverable in a distributed binary, so the true protections are the
lease-based queue + the QA gate on returned translations — never trust it as a
hard secret.
"""

APP_NAME = "מחשוב קהילתי"          # brand shown in the app
APP_VERSION = "1.0.3"

# v1.0.1 — the control plane is its OWN Turso queue behind the Worker's
# secret-gated /cc/* routes, SEPARATE from the site's Supabase (so the volunteer
# fleet can never break the site's login again). CC_SECRET is a soft anti-spam
# gate (discoverable in any distributed binary); the real protections are the
# per-worker lease, the max_inflight cap, the block switch, and the QA gate.
#
# v1.0.3 — Turso itself now hard-blocks reads (plan quota exceeded), so the
# Worker/Turso route above is DEAD; the queue moved to the self-hosted server
# on the Home Assistant machine (same secrets, byte-compatible /cc/* contract,
# reached via a Cloudflare Tunnel). CC_BASE_ALT below still lets a running
# volunteer point elsewhere without a rebuild.
CC_BASE = "https://pool.hebrew-translation-hub.com/cc"
CC_SECRET = "bff947baf4b340ec303dbabd377dd7aaa9f10ebc143ece3e"

# Legacy Supabase constants — kept only so an older module import cannot break;
# the control plane no longer uses them.
SUPABASE_URL = "https://mfudkftrluabqlrpkvtj.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_zq_z7pF4EwWH4HHzsYm6pQ_RAm7oc2x"
APP_SECRET = "cc_06950e1d42d186525b087a400bc522460ae3034fae0c75d4"

# the 3 supported free providers — label, keystore id, and where to get a key
PROVIDERS = [
    ("Groq",      "groq",      "console.groq.com/keys"),
    ("SambaNova", "sambanova", "cloud.sambanova.ai"),
    ("NVIDIA NIM", "nim",      "build.nvidia.com"),
]

# worker loop tuning — LINE model (v1.0.2).
# The CLAIM size is NOT here on purpose: the server sends its own `batch_size`
# on every reply, so the operator retunes the whole fleet without a rebuild.
PREFETCH_LINES = 20        # refill the local buffer once it drops below this
TRANSLATE_SLICE = 8        # lines handed to the providers per translate call
POLL_IDLE_S = 6            # wait between loops when idle / offline (backoff up to POLL_MAX_S)
POLL_MAX_S = 60

# Alternate control plane. Empty = use CC_BASE above. Settable in-app (Settings →
# server) so the SELF-HOSTED pool can be pointed at without shipping a new build —
# the one thing a live `config` reply cannot carry is its own address.
CC_BASE_ALT = ""
