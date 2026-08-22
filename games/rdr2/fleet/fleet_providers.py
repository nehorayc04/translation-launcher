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
import os, json, time, ssl, urllib.request, urllib.error

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
# 🔑🔑 A MODEL IS ITS OWN RATE BUCKET — so a provider's model field is a LIST, and each
# machine picks a DIFFERENT entry (by hostname hash, or FLEET_MODEL_IDX). Seven machines all
# hammering one model share one quota and spend most of their calls in cooldown: measured on
# 2026-08-07, groq returned usable output on only **16 of 244 lines (6.6%)** while the very
# same model answered **8/8 in 1.2 s** when probed alone — it was never broken, just fully
# contended. Probing the alternatives showed each has its OWN headroom (groq
# llama-3.3-70b 3/3 @0.9s, gpt-oss-20b 3/3; sambanova V3.1 / Llama-3.3-70B / gemma-4-31B all
# 4/4 while V3.2 was 0/10). Spreading 7 streams over 3 buckets triples the ceiling for free.
# ⚠️ Quality note: every model listed here was checked on a REAL 8-line RDR2 batch and
# returned complete, well-formed Hebrew JSON — never add one that hasn't been.
PROVIDERS = [
    # ⛔ `openai/gpt-oss-20b` was here and was REMOVED after a 1 %-style spot-check: it answers
    # 8/8 and passes every structural guard, yet its Hebrew is WORD-BY-WORD garbage —
    # "A pelt from the Legendary Onyx Wolf" -> `אחד עור מ ה מפורסם אוניקס זאב`, with the
    # prefixes ה/מ/ל left standing as separate words. A JSON-shape probe cannot see that;
    # only reading the actual sentences can. 100 damaged lines were purged and re-queued.
    ("groq",      "https://api.groq.com/openai/v1",
     ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"]),
    # 🔴 SambaNova rate-limits PER MODEL, not per account. On 2026-08-07 every one of the ten
    # keys returned `429 Rate limit exceeded` for DeepSeek-V3.2 *simultaneously* — which reads
    # exactly like an exhausted account and had the seven sambanova streams producing ZERO for
    # hours. Probing the same keys against the provider's other models: V3.1 4/4, Llama-3.3-70B
    # 4/4, gemma-4-31B 4/4, gpt-oss-120b 1/4 (timeouts), MiniMax 402. So the account was fine
    # and only the most-contended model was capped. V3.1 is the direct sibling of V3.2 (same
    # family, same quality tier for EN->Hebrew), so it is the drop-in.
    # LESSON: when EVERY key of a provider 429s at once, list its models and probe the others
    # before concluding the provider is dead or the keys are spent.
    ("sambanova", "https://api.sambanova.ai/v1",
     ["DeepSeek-V3.1", "Meta-Llama-3.3-70B-Instruct", "gemma-4-31B-it"]),
    ("nim",       "https://integrate.api.nvidia.com/v1", "meta/llama-3.1-70b-instruct"),
]


def _model_for(model, provider):
    """Pick this MACHINE's model from a provider's list (a plain string stays as-is).

    Deterministic per host, so a restart keeps the same bucket and the spread is stable
    across the fleet without any central coordinator."""
    if isinstance(model, str):
        return model
    idx = os.environ.get("FLEET_MODEL_IDX", "").strip()
    if not idx.isdigit():
        # a hostname hash can pile several machines onto one bucket; `model_idx.txt` next to
        # this file lets the deploy assign the spread EXACTLY (7 machines -> 3/2/2).
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "model_idx.txt"), encoding="utf-8") as fh:
                idx = fh.read().strip()
        except Exception:
            idx = ""
    if idx.isdigit():
        return model[int(idx) % len(model)]
    import socket, zlib
    h = zlib.crc32((socket.gethostname() or "x").encode())
    return model[h % len(model)]
# 🔴 COOLDOWN LENGTH IS A THROUGHPUT KNOB, AND 60 s WAS COSTING MINUTES PER BATCH.
# Measured 2026-08-07: a desktop stream banked **1 line/minute** while its provider answered
# a probe in 1 s. The time was not spent working — it was spent SLEEPING. With 10 keys the
# adapter takes `min(4, nkeys)+1 = 5` attempts, and every attempt that found all keys cooling
# slept out the FULL remaining cooldown, so one throttled moment cost up to 5 minutes of dead
# air, twice over (pinned fleet, then the borrow fleet). Free-tier limits are per-MINUTE, so
# 20 s + a hard 3 s cap on any single wait keeps the rotation moving: a key that is still
# limited simply loses one cheap attempt instead of freezing the stream.
# ⚠️ 20 s was tried and made things WORSE: a short cooldown quadruples the request rate into
# an already-saturated pool, so every stream 429s faster. The cooldown is not just a wait —
# it is what PROTECTS the shared key pool. 60 s + a 10 s cap on any single sleep keeps a
# stream from freezing while still throttling the fleet's aggregate request rate.
_COOLDOWN_S = 60
_MAX_WAIT_S = 10.0
_COOL = {}  # provider -> unix-ts until which it is skipped


def load_keys(here):
    """{provider: key}. keys.json wins; key.txt supplies nim only; env overrides."""
    keys = {}
    kj = os.path.join(here, "keys.json")
    if os.path.exists(kj):
        try:
            d = json.load(open(kj, encoding="utf-8"))
            for p in ("nim", "groq", "sambanova"):
                v = d.get(p)
                if not v:
                    continue
                # 🔑 A PROVIDER MAY NOW CARRY A LIST OF KEYS. One key per machine made the
                # FASTEST provider the weakest: groq is tokens-per-minute capped, so a single
                # key 429s within a couple of batches and the stream stalls while nim (slow
                # but generous) carries the fleet. The pool holds 10 keys per provider and
                # only 7 were ever used; rotating all of them multiplies the headroom of
                # exactly the provider that needs it. A bare string still works.
                keys[p] = [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) \
                    else [str(v).strip()]
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


def _one(base, model, key, sysmsg, usermsg, timeout, max_tokens):
    payload = {"model": model, "temperature": 0.2, "max_tokens": max_tokens,
               "messages": [{"role": "system", "content": sysmsg},
                            {"role": "user", "content": usermsg}]}
    req = urllib.request.Request(
        base + "/chat/completions", data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": _UA})
    body = urllib.request.urlopen(req, timeout=timeout, context=_SSL).read().decode()
    return json.loads(body)["choices"][0]["message"]["content"]


class Fleet:
    """Rotates the available providers. `complete()` returns the raw content string;
    the caller keeps its own JSON parsing (so it's a true drop-in for chat())."""

    def __init__(self, keys, only=None):
        # normalise to {provider: [key, ...]} so a caller passing the old {provider: "key"}
        # shape keeps working unchanged
        self.keys = {p: (list(v) if isinstance(v, (list, tuple)) else [v])
                     for p, v in (keys or {}).items() if v}
        self.ki = {}                       # provider -> next key index (round-robin)
        # resolve each provider's model list to THIS machine's pick, once
        self.avail = [(p, b, _model_for(m, p)) for (p, b, m) in PROVIDERS if self.keys.get(p)]
        if only:
            self.avail = [(p, b, m) for (p, b, m) in self.avail if p == only]
        self.i = 0
        if not self.avail:
            raise RuntimeError(f"no key for provider(s) {only or 'any'} (need keys.json or key.txt)")

    def provider_names(self):
        return [p for (p, _, _) in self.avail]

    def _pick(self):
        n = len(self.avail)
        now = time.time()
        for _ in range(n):
            p, b, m = self.avail[self.i % n]
            self.i += 1
            if _COOL.get(p, 0) <= now:
                return p, b, m
        # everyone cooling -> take the one that frees up soonest, wait briefly
        p, b, m = min(self.avail, key=lambda x: _COOL.get(x[0], 0))
        time.sleep(min(_MAX_WAIT_S, max(0.0, _COOL.get(p, 0) - now)) + 0.3)
        return p, b, m

    def complete(self, sysmsg, usermsg, retries=4, timeout=120, max_tokens=2500):
        # FAIL-FAST: a pinned single-provider worker (self.avail has exactly ONE entry,
        # which is every stream in this fleet) gains NOTHING from cycling providers, so
        # `max(retries, len(avail))` used to mean up to 4 FULL-timeout attempts against
        # the same slow/throttled key - up to ~4x the per-call timeout before giving up
        # on one batch. A timeout/network error is a HARD signal exactly like a 429 (the
        # endpoint is not answering right now), so it now earns the SAME cooldown instead
        # of a bare 1s sleep-and-hammer-again. With one provider this caps a doomed batch
        # at ONE real attempt + one short-cooldown retry, not four long ones.
        last = None
        # With several keys for one provider, a 429 is a property of the KEY, not of the
        # endpoint — so a pinned single-provider worker now gets one real attempt PER KEY
        # instead of giving up after two. Cooling the whole provider on a per-key quota
        # error is what previously idled the fastest provider for a full cooldown.
        nkeys = max(len(v) for v in self.keys.values()) if self.keys else 1
        attempts = (min(4, nkeys) + 1) if len(self.avail) == 1 \
            else max(retries, len(self.avail))
        for _ in range(attempts):
            p, b, m = self._pick()
            ks = self.keys[p]
            now = time.time()
            # prefer a key that is not cooling; round-robin so load spreads evenly
            key, kidx = None, self.ki.get(p, 0)
            for _j in range(len(ks)):
                cand = kidx % len(ks)
                kidx += 1
                if _COOL.get((p, cand), 0) <= now:
                    key, kidx_used = ks[cand], cand
                    break
            if key is None:                        # every key cooling -> take the soonest
                kidx_used = min(range(len(ks)), key=lambda i: _COOL.get((p, i), 0))
                key = ks[kidx_used]
                time.sleep(min(_MAX_WAIT_S, max(0.0, _COOL.get((p, kidx_used), 0) - now)) + 0.3)
            self.ki[p] = kidx
            try:
                return _one(b, m, key, sysmsg, usermsg, timeout, max_tokens)
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (401, 403):
                    # A REVOKED/INVALID KEY NEVER RECOVERS. Without this it falls into the
                    # generic branch, is never cooled, and the round-robin hands it back on
                    # the very next call — a dead key in a 10-key pool otherwise costs a
                    # tenth of every stream's calls, forever. Park it for the whole run.
                    _COOL[(p, kidx_used)] = time.time() + 10 ** 9
                elif e.code in (429, 402, 503):
                    _COOL[(p, kidx_used)] = time.time() + _COOLDOWN_S
                else:
                    time.sleep(1)
                # only park the whole provider once EVERY key is cooling
                if all(_COOL.get((p, i), 0) > time.time() for i in range(len(ks))):
                    _COOL[p] = time.time() + _COOLDOWN_S
            except Exception as e:
                # timeout / URLError / connection reset - the endpoint didn't answer.
                # Blameless like a 429, and just as likely to still be slow on an
                # immediate retry - cool it down instead of hammering it again.
                last = e
                _COOL[(p, kidx_used)] = time.time() + _COOLDOWN_S
                if all(_COOL.get((p, i), 0) > time.time() for i in range(len(ks))):
                    _COOL[p] = time.time() + _COOLDOWN_S
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
