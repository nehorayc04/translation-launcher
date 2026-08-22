import urllib.request
import json

def main():
    url = "http://localhost:11434/api/generate"
    
    strings = {
        "0x0002eba8": "Suspect identified as known criminal going by the streetname \"_T0_\".",
        "0x000780d0": "Misfiring in the Shooting Range caused the round to end and the Cops to be alerted.",
        "0x000d0ff3": "Layered Bob"
    }
    
    prompt = (
        "You are a professional game translator. Translate the following GTA V UI strings from English to Hebrew.\n"
        "Rules:\n"
        "1. Translate to logical, standard Hebrew (standard reading direction, no visual reversal).\n"
        "2. Do not use any niqqud (vocalization points).\n"
        "3. Do not translate formatting placeholders like _T0_, _T1_, _T2_. Keep them exactly as they are in the source, including spacing and underscores.\n"
        "4. Keep names and brands in English: Michael, Franklin, Trevor, Lester, Lamar, Los Santos, Blaine County, Ammu-Nation, LSPD, FIB, Lifeinvader, Social Club.\n"
        "5. Return the translations as a JSON object matching the format: { \"key\": \"Hebrew translation\" }.\n"
        "6. Output ONLY the raw JSON block, nothing else. Do not use markdown tags like ```json.\n\n"
        f"Input:\n{json.dumps(strings, indent=2)}\n\n"
        "Output JSON:"
    )
    
    payload = {
        "model": "qwen2.5:3b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        res = urllib.request.urlopen(req, timeout=300).read().decode('utf-8')
        data = json.loads(res)
        print("SUCCESS:", data["response"].strip())
    except Exception as e:
        print("FAILED:", e)

if __name__ == "__main__":
    main()
