import urllib.request
import json
import time

url = 'http://localhost:1234/v1/chat/completions'
body = {
    'model': 'gemma-4-31b-it@q2_k_xl',
    'messages': [{'role': 'user', 'content': 'Hello, respond with only the word OK.'}],
    'temperature': 0.1
}

req = urllib.request.Request(
    url,
    data=json.dumps(body).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

print("Sending request to local LM Studio...")
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.loads(r.read().decode('utf-8'))
        print("Success in {:.2f}s:".format(time.time() - t0), res['choices'][0]['message']['content'])
except urllib.error.HTTPError as e:
    print("HTTP Error in {:.2f}s:".format(time.time() - t0), e.code, e.reason)
    print("Error Body:", e.read().decode('utf-8'))
except Exception as e:
    print("General Error after {:.2f}s:".format(time.time() - t0), e)
