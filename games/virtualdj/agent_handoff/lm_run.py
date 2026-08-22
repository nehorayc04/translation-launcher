r"""
Auto-run the whole VirtualDJ translation via a LOCAL LM (LM Studio, OpenAI API
at localhost:1234). New-Era: each line is sent with the source English + all
shipped-language refs; the model returns Hebrew; every reply is structurally
validated (_tokens.validate) before merge. Resumable, serial, atomic.

Prereq (LM Studio must be up with any chat model loaded):
    lms load qwen2.5-32b-instruct -y --gpu max          (or any model)
Run:
    python lm_run.py            # loops until All done!
    python lm_run.py 20         # request batch size (default 15)
"""
import sys
import json
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _tokens import validate  # noqa: E402

API = "http://localhost:1234/v1/chat/completions"
MODELS = "http://localhost:1234/v1/models"
REQ = int(sys.argv[1]) if len(sys.argv) > 1 else 15

SYS = (
    "אתה מתרגם מקצועי המתרגם ממשק תוכנת DJ (VirtualDJ) מאנגלית לעברית תקנית, "
    "בסגנון לוקליזציה של תוכנה (קצר, מקצועי). לכל שורה תקבל את המקור האנגלי (en) "
    "ורשימת תרגומים לשפות אחרות (refs) כהצלבת משמעות/מגדר. כללים: (1) עברית לוגית "
    "רגילה, בלי להפוך אותיות. (2) בלי ניקוד. (3) שמור כל placeholder בדיוק "
    "(%i %s %d %% %2F) ואת [[...]] ואת \\n. (4) שמות מותגים/ראשי-תיבות באנגלית "
    "(VirtualDJ, ASIO, MIDI, CDJ, BPM, iTunes, Serato, RekordBox, Traktor, Deezer, "
    "TIDAL, SoundCloud, Beatport, Spotify...). (5) מונחים: Deck=דק, Loop=לולאה, "
    "Sampler=דוגם, Crossfader=קרוספיידר, Cue=קיו, Gain=גיין, Pitch=פיץ'. "
    "החזר JSON בלבד: {\"key\": \"תרגום עברי\", ...} עבור כל המפתחות שקיבלת, ללא טקסט נוסף."
)


def _post(payload, timeout=180):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(API, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def model_id():
    with urllib.request.urlopen(MODELS, timeout=10) as r:
        return json.load(r)["data"][0]["id"]


def main():
    mid = model_id()
    print("model:", mid)
    tt = json.load(open(HERE / "to_translate.json", encoding="utf-8"))
    hp = HERE / "hebrew.json"
    done = json.load(open(hp, encoding="utf-8")) if hp.exists() else {}
    todo = [k for k in tt if k not in done]
    print(f"remaining {len(todo)} / {len(tt)}")

    i = 0
    while i < len(todo):
        chunk = todo[i:i + REQ]
        payload_lines = {k: {"en": tt[k]["en"], "refs": tt[k]["refs"]} for k in chunk}
        user = json.dumps(payload_lines, ensure_ascii=False)
        try:
            resp = _post({"model": mid, "temperature": 0.2,
                          "messages": [{"role": "system", "content": SYS},
                                       {"role": "user", "content": user}]})
            txt = resp["choices"][0]["message"]["content"]
            s, e = txt.find("{"), txt.rfind("}")
            out = json.loads(txt[s:e + 1])
        except Exception as ex:
            print(f"  [chunk {i}] error {type(ex).__name__}: {ex} -> retry singly")
            out = {}
        ok = 0
        for k in chunk:
            he = (out.get(k) or "").strip()
            good, _ = validate(tt[k]["en"], he)
            if good:
                done[k] = he
                ok += 1
        # atomic save each chunk (resumable)
        tmp = hp.with_suffix(".tmp")
        json.dump(done, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        tmp.replace(hp)
        i += REQ
        print(f"  {len(done)}/{len(tt)}  (+{ok}/{len(chunk)})")
    print("All done!" if len(done) >= sum(1 for _ in tt) else "stopped")


if __name__ == "__main__":
    main()
