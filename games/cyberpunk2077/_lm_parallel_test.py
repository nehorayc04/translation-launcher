"""
Decisive test: does --parallel 4 actually parallelize on this GPU,
or does KV-cache spill collapse it to serial?

Same realistic translation prompt × 4. First serial (one-after-the-other),
then concurrent (all 4 started at once). If concurrent ≈ serial total,
KV spilled → keep parallel 1. If concurrent ≈ serial / N, parallel N works.
"""
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

URL = "http://127.0.0.1:1234/v1/chat/completions"
PROMPT = ("Translate to Hebrew (output only the translation, no commentary): "
          "The corpo agreed to meet at the rooftop bar in the Arasaka tower "
          "tonight. Bring the data shard and keep your weapon hidden.")
PAYLOAD = json.dumps({
    "model": "gemma-2-27b-it",
    "messages": [
        {"role": "system", "content": "You are a professional Cyberpunk 2077 Hebrew localizer."},
        {"role": "user", "content": PROMPT},
    ],
    "max_tokens": 120,
    "temperature": 0,
}).encode("utf-8")


def call(i: int) -> float:
    t0 = time.time()
    req = urllib.request.Request(URL, data=PAYLOAD,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        body = json.loads(r.read())
    dt = time.time() - t0
    txt = body["choices"][0]["message"]["content"][:60]
    print(f"  [{i}] {dt:5.1f}s  {txt!r}", flush=True)
    return dt


def main():
    # 1 warm call so the first cold-start hit isn't counted
    print("[*] Warmup …", flush=True)
    call(0)

    print("\n[*] Serial (4 sequential calls):", flush=True)
    t0 = time.time()
    serial = [call(i) for i in range(1, 5)]
    serial_total = time.time() - t0
    print(f"  TOTAL serial: {serial_total:.1f}s "
          f"(avg per call {sum(serial)/4:.1f}s)", flush=True)

    print("\n[*] Concurrent (4 calls in parallel):", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as pool:
        cc = list(pool.map(call, range(5, 9)))
    cc_total = time.time() - t0
    print(f"  TOTAL concurrent: {cc_total:.1f}s "
          f"(slowest call {max(cc):.1f}s)", flush=True)

    speedup = serial_total / cc_total
    print(f"\n[=] Speedup = {speedup:.2f}x "
          f"(ideal would be ~4x; <1.2x means parallel is broken / KV spilling)",
          flush=True)


if __name__ == "__main__":
    main()
