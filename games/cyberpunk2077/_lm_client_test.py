"""
Test what the *translator* actually does — same SDK, same model ID,
realistic batch prompt with 12 items, 4 concurrent workers.

If serial-via-SDK >> serial-via-urllib, the OpenAI SDK / httpx pool is
the bottleneck. If concurrent-via-SDK ~= serial-via-SDK total, the
4-worker parallelism is broken at the client layer.
"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

# import the actual translator core
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import translate_queue_fast as tqf
from openai import OpenAI

# replicate the translator's setup exactly
tqf.lm_client = OpenAI(base_url=tqf.LM_URL, api_key="lm-studio", timeout=600)
tqf.TEMPERATURE = tqf.DEFAULT_TEMP

# realistic batch — matches the translator's actual DYN_MAX_LINES=12
BATCH = [
    "Hey, choom — meet me at the rooftop bar tonight.",
    "Bring the data shard, and keep the weapon hidden.",
    "I'll handle the corpo guards — you cover the exit.",
    "Don't trust Arasaka. Their fixers play dirty.",
    "Sandevistan engaged. Time to move, fast.",
    "Hit them hard, hit them fast, fade into the smoke.",
    "Night City never sleeps and neither do we.",
    "The Edgerunner died for a chrome plate worth nothing.",
    "Find the netrunner and crack the firewall.",
    "Watch your back — there's a snake in the deck.",
    "Pay the ripper, get the cyberware, walk out chrome.",
    "End of the line, output. Welcome to Dogtown.",
]

print(f"[*] LM_MODEL = {tqf.LM_MODEL!r}", flush=True)
print(f"[*] PARALLEL_WORKERS = {tqf.PARALLEL_WORKERS}", flush=True)
print(f"[*] DYN_MAX_LINES = {tqf.DYN_MAX_LINES}", flush=True)
print(f"[*] MAX_TOKENS = {tqf.MAX_TOKENS}", flush=True)

# warmup
print("\n[*] Warmup …", flush=True)
t0 = time.time()
tqf.translate_batch(BATCH)
print(f"  warmup {time.time()-t0:.1f}s", flush=True)


def one_batch(i: int) -> float:
    t0 = time.time()
    res = tqf.translate_batch(BATCH)
    dt = time.time() - t0
    ok = sum(1 for r, src in zip(res, BATCH) if tqf.is_valid_translation(src, r))
    print(f"  [{i}] {dt:5.1f}s  valid={ok}/12  sample={res[0][:40]!r}", flush=True)
    return dt


print("\n[*] Serial (4 batches one-after-the-other):", flush=True)
t0 = time.time()
serial = [one_batch(i) for i in range(1, 5)]
serial_total = time.time() - t0
print(f"  TOTAL serial: {serial_total:.1f}s "
      f"(avg per batch {sum(serial)/4:.1f}s)", flush=True)

print("\n[*] Concurrent (4 batches in parallel via 4 workers):", flush=True)
t0 = time.time()
with ThreadPoolExecutor(max_workers=tqf.PARALLEL_WORKERS) as pool:
    cc = list(pool.map(one_batch, range(5, 9)))
cc_total = time.time() - t0
print(f"  TOTAL concurrent: {cc_total:.1f}s "
      f"(slowest batch {max(cc):.1f}s)", flush=True)

speedup = serial_total / cc_total
print(f"\n[=] SDK Speedup = {speedup:.2f}x", flush=True)
print(f"    Effective items/min @ concurrent = "
      f"{12 * 4 / cc_total * 60:.1f}", flush=True)
