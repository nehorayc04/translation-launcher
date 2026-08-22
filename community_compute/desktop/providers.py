# -*- coding: utf-8 -*-
"""BYOK 3-provider adapter (Groq / SambaNova / NVIDIA NIM).

Adapted from universal/fleet_providers.py — but the keys come from the
VOLUNTEER's local encrypted keystore, and a job batch is SHARDED across whatever
providers the volunteer configured, translated in parallel (one thread per
provider), then any line a provider dropped is retried on another. Nothing here
ever leaves the machine except the provider API calls themselves (which the
volunteer consented to, with their own key + IP).

All three providers are OpenAI-compatible. A browser User-Agent is mandatory
(Groq sits behind Cloudflare and 403s the default Python-urllib UA — "error
code: 1010"). An optional user-configured proxy is honored (the app bundles NO
VPN; a volunteer may point at their own proxy).
"""
from __future__ import annotations

import json
import re
import ssl
import threading
import time
import urllib.error
import urllib.request

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
_SSL = ssl.create_default_context()
_JSON = re.compile(r"\{.*\}", re.S)

# id, base url, model  (labels map to keystore ids in config.PROVIDERS)
ENDPOINTS = {
    "groq":      ("https://api.groq.com/openai/v1",      "openai/gpt-oss-120b"),
    "sambanova": ("https://api.sambanova.ai/v1",         "DeepSeek-V3.2"),
    "nim":       ("https://integrate.api.nvidia.com/v1", "meta/llama-3.1-70b-instruct"),
}

_COOLDOWN_S = 60
_COOL: dict[str, float] = {}


def _opener(proxy: str):
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
            urllib.request.HTTPSHandler(context=_SSL))
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=_SSL))


def _call(provider: str, key: str, sysmsg: str, usermsg: str,
          proxy: str = "", timeout: int = 120, max_tokens: int = 2500) -> str:
    base, model = ENDPOINTS[provider]
    payload = {"model": model, "temperature": 0.2, "max_tokens": max_tokens,
               "messages": [{"role": "system", "content": sysmsg},
                            {"role": "user", "content": usermsg}]}
    req = urllib.request.Request(
        base + "/chat/completions", data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": _UA})
    body = _opener(proxy).open(req, timeout=timeout).read().decode()
    return json.loads(body)["choices"][0]["message"]["content"]


def _translate_shard(provider: str, key: str, sysmsg: str, shard: dict,
                     proxy: str, result: dict, counts: dict, lock: threading.Lock) -> None:
    if not shard:
        return
    if _COOL.get(provider, 0) > time.time():
        return
    user = ("Translate every value to Hebrew. Return ONLY a JSON object mapping the SAME "
            "ids to the Hebrew translation:\n" + json.dumps(shard, ensure_ascii=False))
    try:
        raw = _call(provider, key, sysmsg, user, proxy)
    except urllib.error.HTTPError as e:
        if e.code in (429, 402, 503):
            _COOL[provider] = time.time() + _COOLDOWN_S
        return
    except Exception:
        return
    m = _JSON.search(raw)
    if not m:
        return
    try:
        got = json.loads(m.group(0))
    except Exception:
        return
    n = 0
    with lock:
        for k in shard:
            v = got.get(k) or got.get(str(k))
            if isinstance(v, str) and v.strip():
                result[k] = v.strip()
                n += 1
        counts[provider] = counts.get(provider, 0) + n


def available(keys: dict) -> list:
    """provider ids that both have a key AND are known endpoints."""
    return [p for p in ("groq", "sambanova", "nim") if keys.get(p) and p in ENDPOINTS]


def translate_batch(keys: dict, sysmsg: str, items: dict, proxy: str = "") -> tuple[dict, dict]:
    """Shard `items` ({id:en}) across the configured providers, translate in
    parallel, retry any dropped line once on another provider. Returns
    (out {id:he}, counts {provider:lines}). Raises if NO provider is configured."""
    provs = available(keys)
    if not provs:
        raise RuntimeError("no provider keys configured")
    ids = list(items)
    result: dict = {}
    counts: dict = {}
    lock = threading.Lock()

    # round-robin shard so each provider gets a contiguous, balanced slice
    shards = {p: {} for p in provs}
    for i, k in enumerate(ids):
        shards[provs[i % len(provs)]][k] = items[k]

    threads = [threading.Thread(target=_translate_shard,
                                args=(p, keys[p], sysmsg, shards[p], proxy, result, counts, lock))
               for p in provs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # retry whatever any provider dropped, on a NOT-cooling provider
    missing = {k: items[k] for k in ids if k not in result}
    if missing:
        for p in provs:
            if _COOL.get(p, 0) > time.time():
                continue
            _translate_shard(p, keys[p], sysmsg, missing, proxy, result, counts, lock)
            missing = {k: items[k] for k in ids if k not in result}
            if not missing:
                break
    return result, counts
