# -*- coding: utf-8 -*-
import os, json, urllib.request, urllib.error

def _load_env(path):
    env = {}
    try:
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
env = _load_env(os.path.join(ROOT, ".env"))
api_key = env.get("GEMINI_API_KEY", "")

url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
body = json.dumps({
    "model": "gemini-2.5-flash",
    "messages": [
        {"role": "user", "content": "Translate 'Hello' to Hebrew. Output only the translation, no extra text."}
    ],
    "max_tokens": 10
}).encode("utf-8")

req = urllib.request.Request(url, body, {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + api_key
})

try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print("Success:", json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"])
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.reason)
    try:
        print(e.read().decode('utf-8'))
    except Exception as read_err:
        print("Failed to read body:", read_err)
except Exception as e:
    print("Failed:", e)
