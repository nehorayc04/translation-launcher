import urllib.request
import json

def main():
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "gemma4:latest",
        "prompt": "Translate the following English string to Hebrew (logical Hebrew, standard reading, no niqqud). Only return the translation, nothing else.\n\nEnglish: Hello world\nHebrew:",
        "stream": False
    }
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        res = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
        data = json.loads(res)
        print("SUCCESS:", repr(data["response"].strip()))
    except Exception as e:
        print("FAILED:", e)

if __name__ == "__main__":
    main()
