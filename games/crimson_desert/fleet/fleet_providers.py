# -*- coding: utf-8 -*-
"""Multi-provider fleet adapter — NIM + Groq + SambaNova, all OpenAI-compatible.

Drop-in for a worker's chat(): rotates across providers (round-robin), puts a
provider in cooldown on 429/402/503, and ALWAYS sends a browser User-Agent
(Groq/Cerebras sit behind Cloudflare and 403 "error code: 1010" the default
Python-urllib UA — the same trap documented for the Supabase Management API).

keys.json lives next to the worker:
    {"nim": "nvapi-...", "groq": "gsk_...", "sambanova": "..."}
If keys.json is absent it falls back to key.txt (NIM only), so an un-migrated
stream keeps working on NIM alone.

High-quality models chosen 2026-07-20 (benchmarked on real EN->Hebrew):
    Groq       openai/gpt-oss-120b            ~1.0s  (120B, very fast)
    SambaNova  DeepSeek-V3.2                  ~3.0s  (top quality, most natural)
    NIM        meta/llama-3.1-70b-instruct    ~16s   (generous free quota, bulk)
Cerebras was dropped — it moved API access behind a payment method (402).
"""
import os, json, time, ssl, threading, urllib.request, urllib.error

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _build_ssl_ctx():
    # A plain ssl.create_default_context() falls back to the WINDOWS SYSTEM
    # root-CA store on this OS, and that store is populated lazily (Windows
    # AutoUpdate fetches a root on first-use, on demand) - so a VM that never
    # happened to hit sambanova.ai/nvidia.com before is missing exactly the
    # roots those chains need and every call dies with "self-signed
    # certificate in certificate chain" / "unable to get local issuer
    # certificate", forever, while groq (whose root WAS cached) works fine.
    # Found 2026-08-02: vm/vm2/vm3 all ship the IDENTICAL certifi bundle
    # (234354 B) but ssl.create_default_context() loaded 23/21/21 CAs off
    # Windows' own store respectively - pinning certifi's bundle explicitly
    # makes every machine trust the exact same, complete root set regardless
    # of what Windows has or hasn't auto-fetched.
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


_SSL = _build_ssl_ctx()

# order = preference: fast/high-quality first, slow-but-generous NIM last.
# 🔴 MEASURED 2026-08-10 on a worker box with a REAL 8-line batch of THIS corpus (never "hi" —
# a trivial prompt succeeds on a model that returns an empty `content` for a JSON task):
#   groq  gpt-oss-120b            3.5s  8/8   <- keep
#   samba DeepSeek-V3.2           HTTP 429 "Rate limit exceeded"      <- the SHIPPED default
#   samba DeepSeek-V3.1           HTTP 429 "experiencing high demand"
#   samba Meta-Llama-3.3-70B     10.5s  8/8   <- switched to this
#   nim   llama-3.1-70b          54.2s  8/8   <- too slow, its batches blew the timeout
#   nim   llama-3.3-70b          37.2s  8/8   <- switched to this
# Symptom before the switch: sambanova and nim logged `step1 fail (read operation timed out)`
# on EVERY batch (+0/N) while groq ran clean — 12 of 18 streams producing nothing.
# [[a-model-is-its-own-rate-bucket]]
PROVIDERS = [
    ("groq",      "https://api.groq.com/openai/v1",      "openai/gpt-oss-120b"),
    ("sambanova", "https://api.sambanova.ai/v1",         "Meta-Llama-3.3-70B-Instruct"),
    ("nim",       "https://integrate.api.nvidia.com/v1", "meta/llama-3.3-70b-instruct"),
]
# per-provider cooldown after a rate/quota error (seconds)
_COOLDOWN_S = 60
_COOL = {}  # provider -> unix-ts until which it is skipped


def load_keys(here):
    """{provider: [key, ...]}. keys.json wins; key.txt supplies nim only; env overrides.

    🔑 A PROVIDER MAY CARRY A LIST OF KEYS (ported from the RDR2 adapter, 2026-08-09). One
    key per provider is what capped this machine: with 9 clients (3 workers + 6 drain slots)
    on 3 keys, batches came back with ZERO ids — not rejected, simply never answered. The
    shared pool holds 10 keys per provider and the seven machines use one each, so three per
    provider sit unused; handing them to the box that needs them multiplies its headroom
    without touching any other machine's key. A bare string still works.
    """
    keys = {}
    kj = os.path.join(here, "keys.json")
    if os.path.exists(kj):
        try:
            d = json.load(open(kj, encoding="utf-8"))
            for p in ("nim", "groq", "sambanova"):
                v = d.get(p)
                if not v:
                    continue
                keys[p] = ([str(x).strip() for x in v if str(x).strip()]
                           if isinstance(v, list) else [str(v).strip()])
        except Exception:
            pass
    if "nim" not in keys:
        for kt in (os.path.join(here, "key.txt"), r"C:\w3w\key.txt", r"C:\ptw\key.txt"):
            if os.path.exists(kt):
                for l in open(kt, encoding="utf-8"):
                    l = l.strip()
                    if l.startswith("nvapi-"):
                        keys["nim"] = [l]
                        break
            if "nim" in keys:
                break
    for env, p in (("NVIDIA_API_KEY", "nim"), ("GROQ_API_KEY", "groq"),
                   ("SAMBANOVA_API_KEY", "sambanova")):
        v = os.environ.get(env, "").strip()
        if v:
            keys[p] = [v]
    return keys


def _one_blocking(base, model, key, sysmsg, usermsg, timeout, max_tokens):
    payload = {"model": model, "temperature": 0.2, "max_tokens": max_tokens,
               "messages": [{"role": "system", "content": sysmsg},
                            {"role": "user", "content": usermsg}]}
    req = urllib.request.Request(
        base + "/chat/completions", data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": _UA})
    body = urllib.request.urlopen(req, timeout=timeout, context=_SSL).read().decode()
    return json.loads(body)["choices"][0]["message"]["content"]


def _one(base, model, key, sysmsg, usermsg, timeout, max_tokens):
    # HARD wall-clock wrapper. `urlopen(..., timeout=)` only bounds connect()/recv() -
    # the DNS lookup (socket.getaddrinfo, done via the C resolver BEFORE any socket
    # exists) is NOT covered by that timeout at all. A resolver hiccup at the exact
    # moment a call starts can leave the whole thread blocked in a syscall for many
    # minutes with near-zero CPU - measured live on 2026-08-03 (two corsair-cove
    # streams stuck 6-7 min, 0.25-0.39s total CPU, current DNS to the same hosts
    # answered in well under a second from the same machines seconds later - i.e. a
    # transient resolver stall that the per-call timeout could never see). Running
    # the real call on a daemon thread and joining with a hard deadline makes EVERY
    # stage (DNS, connect, TLS, read) bounded, not just the parts urlopen covers.
    # The abandoned thread is left to finish/die on its own (daemon => doesn't block
    # process exit); it never touches shared state beyond the box passed to it.
    box = {}

    def _run():
        try:
            box["ok"] = _one_blocking(base, model, key, sysmsg, usermsg, timeout, max_tokens)
        except Exception as e:
            box["err"] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout + 15)  # a few seconds of slack over the socket-level timeout
    if t.is_alive():
        raise TimeoutError(f"hard wall-clock timeout ({timeout + 15}s) - likely a stuck DNS lookup")
    if "err" in box:
        raise box["err"]
    return box["ok"]


class Fleet:
    """Rotates the available providers. `complete()` returns the raw content string;
    the caller keeps its own JSON parsing (so it's a true drop-in for chat())."""

    def __init__(self, keys, only=None):
        # normalise to lists so a bare-string keys.json keeps working
        self.keys = {p: (v if isinstance(v, list) else [v]) for p, v in (keys or {}).items()}
        self.avail = [(p, b, m) for (p, b, m) in PROVIDERS if self.keys.get(p)]
        if only:
            self.avail = [(p, b, m) for (p, b, m) in self.avail if p == only]
        self.i = 0
        self.ki = {p: 0 for p in self.keys}      # per-provider key cursor
        if not self.avail:
            raise RuntimeError(f"no key for provider(s) {only or 'any'} (need keys.json or key.txt)")

    def provider_names(self):
        return [f"{p}x{len(self.keys[p])}" if len(self.keys[p]) > 1 else p
                for (p, _, _) in self.avail]

    def nkeys(self):
        return sum(len(self.keys[p]) for (p, _, _) in self.avail)

    def _pick(self):
        """Return (provider, base, model, key) — cooling is per (provider, KEY).

        Cooling the whole PROVIDER on one 429 throws away the other keys it holds, which is
        the entire point of having them: with 4 groq keys, one rate-limited key must cost the
        next call nothing.
        """
        n = len(self.avail)
        now = time.time()
        for _ in range(n):
            p, b, m = self.avail[self.i % n]
            self.i += 1
            ks = self.keys[p]
            for _ in range(len(ks)):
                k = ks[self.ki[p] % len(ks)]
                self.ki[p] += 1
                if _COOL.get((p, k), 0) <= now:
                    return p, b, m, k
        # every key of every provider is cooling -> take the one that frees up soonest
        cands = [(p, b, m, k) for (p, b, m) in self.avail for k in self.keys[p]]
        p, b, m, k = min(cands, key=lambda x: _COOL.get((x[0], x[3]), 0))
        time.sleep(min(15.0, max(0.0, _COOL.get((p, k), 0) - now)) + 0.3)
        return p, b, m, k

    def complete(self, sysmsg, usermsg, retries=4, timeout=120, max_tokens=2500,
                 max_attempts=None):
        # FAIL-FAST: a pinned single-provider worker (self.avail has exactly ONE entry,
        # which is every stream in this fleet) gains NOTHING from cycling providers, so
        # `max(retries, len(avail))` used to mean up to 4 FULL-timeout attempts against
        # the same slow/throttled key - up to ~4x the per-call timeout before giving up
        # on one batch. A timeout/network error is a HARD signal exactly like a 429 (the
        # endpoint is not answering right now), so it now earns the SAME cooldown instead
        # of a bare 1s sleep-and-hammer-again. With one provider this caps a doomed batch
        # at ONE real attempt + one short-cooldown retry, not four long ones.
        last = None
        # with several KEYS the old "1 provider => 2 attempts" cap threw the extra keys
        # away: a 429 on key 1 must be able to fall through to key 2 in the same call.
        attempts = max(retries, len(self.avail), min(self.nkeys(), 4))
        # 🔴 A CALLER THAT RETRIES THE WHOLE BATCH LATER MUST BE ABLE TO CAP THIS. The floor
        # above (never fewer than one attempt per provider) is right for a worker whose batch
        # is served once, but it lets ONE doomed batch burn 4 x (timeout + 15 s) — measured
        # ~21 min of dead air on a drain slot, which reads as a hang. The drain re-serves
        # everything it missed on the next pass, so a single fast failure is strictly better.
        if max_attempts:
            attempts = min(attempts, max_attempts)
        for _ in range(attempts):
            p, b, m, k = self._pick()
            try:
                return _one(b, m, k, sysmsg, usermsg, timeout, max_tokens)
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (429, 402, 503):
                    _COOL[(p, k)] = time.time() + _COOLDOWN_S
                else:
                    time.sleep(1)
            except Exception as e:
                # timeout / URLError / connection reset - the endpoint didn't answer.
                # Blameless like a 429, and just as likely to still be slow on an
                # immediate retry - cool it down instead of hammering it again.
                last = e
                _COOL[(p, k)] = time.time() + _COOLDOWN_S
        if last:
            raise last
        return ""


if __name__ == "__main__":
    # self-test against a keys.json in the cwd (or key.txt)
    import re, sys
    here = os.path.dirname(os.path.abspath(sys.argv[1])) if len(sys.argv) > 1 else "."
    f = Fleet(load_keys(here if len(sys.argv) > 1 else "."))
    print("providers:", f.provider_names())
    SYS = ("Professional game translator, English to Hebrew. Natural Hebrew, no niqqud, "
           "keep [A] tokens exact. Return ONLY JSON {id:hebrew}.")
    src = {"1": "Save and quit", "2": "Press [A] to open the map."}
    for n in range(len(f.provider_names()) + 1):
        t0 = time.time()
        raw = f.complete(SYS, "Translate to Hebrew, JSON {id:hebrew}:\n" + json.dumps(src, ensure_ascii=False))
        m = re.search(r'\{.*\}', raw, re.S)
        out = json.loads(m.group(0)) if m else {}
        print(f"  call {n+1}: {time.time()-t0:4.1f}s  {out}")
