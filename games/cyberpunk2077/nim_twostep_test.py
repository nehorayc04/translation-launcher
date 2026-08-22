"""NVIDIA NIM — TWO-STEP dual-gender test.
Step 1: translate a line (single Hebrew, the model's strength).
Step 2: a FOCUSED gender-split pass (strong prompt + few-shot) → f / m.
Tests whether a two-step pipeline can extract reliable dual-gender from an
open model on lines that GENUINELY differ by V's gender.
"""
import json, os, sys, re, urllib.request, urllib.error, argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
QA = os.path.join(HERE, "agent_handoff_qa")
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import cp2077_markup_translate as mk
BASE = "https://integrate.api.nvidia.com/v1"
FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]'); NIQ = re.compile(r'[֑-ֽֿׁׂ]'); HEB = re.compile(r'[֐-׿]')
WORD = re.compile(r'[A-Za-z]{2,}')
# lines that likely carry a CONSONANTAL gender difference in unpointed Hebrew
GSENSE = re.compile(r"^\s*(get|take|come|go|look|listen|wait|stop|move|run|hold|give|choose|bring|show|tell|calm|watch|hurry|relax|sit|stand|stay|leave|drop|follow)\b|"
                    r"\byou('re| are| can| could| will| look| seem| did| were| know| want| need| have to| gotta| should)\b|"
                    r"\bare you\b|\bcan you\b|\bdid you\b", re.I)


def load_key():
    k = os.environ.get("NVIDIA_API_KEY", "").strip()
    if k: return k
    for e in (os.path.join(ROOT, ".env"), os.path.join(ROOT, "website", ".env")):
        try:
            for l in open(e, encoding="utf-8"):
                if l.startswith("NVIDIA_API_KEY"): return l.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError: pass
    return ""


def chat(key, model, sysmsg, usermsg, timeout=180):
    payload = {"model": model, "temperature": 0.2, "max_tokens": 4000,
               "messages": [{"role": "system", "content": sysmsg}, {"role": "user", "content": usermsg}]}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(payload).encode(),
                                 method="POST", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
    txt = d["choices"][0]["message"]["content"]
    m = re.search(r'\{.*\}', txt, re.S)
    return json.loads(m.group(0)) if m else {}


def sample(n=14):
    pool = json.load(open(os.path.join(QA, "_pool", "full_pool.json"), encoding="utf-8"))
    out = []
    for k, en in pool.items():
        core = re.sub(r'<[^>]*>|\{[^}]*\}', ' ', en)
        if 8 <= len(en) <= 55 and len(WORD.findall(core)) >= 2 and GSENSE.search(core):
            out.append((k, en))
        if len(out) >= n: break
    return out


S1 = ("You are a senior Hebrew localizer for Cyberpunk 2077. Translate each English line to natural Hebrew "
      "(the line is spoken TO or BY the player). Keep tags/placeholders verbatim. No niqqud. Output JSON {id: hebrew}.")

S2 = ("You are a Hebrew grammar expert. Each item has an English line that ADDRESSES the player V, plus a Hebrew "
      "translation. In Hebrew, verbs/adjectives/2nd-person pronouns agree with the LISTENER's gender. Produce two "
      "versions:\n"
      " \"f\" = V is FEMALE (feminine forms: את, מוכנה, היכנסי, תוכלי, יודעת, נראית, קחי, בואי)\n"
      " \"m\" = V is MALE (masculine forms: אתה, מוכן, היכנס, תוכל, יודע, נראה, קח, בוא)\n"
      "Change ONLY gender-agreement words; keep the rest identical. If NO word changes by gender (e.g. שלך, אותך, "
      "past-tense עשית, or an infinitive), return f and m identical.\n"
      "Examples:\n"
      " EN 'Get in the car.' base 'תיכנס לרכב.' -> {\"f\":\"היכנסי לרכב.\",\"m\":\"היכנס לרכב.\"}\n"
      " EN \"You're the best.\" base 'אתה הכי טוב.' -> {\"f\":\"את הכי טובה.\",\"m\":\"אתה הכי טוב.\"}\n"
      " EN 'Take your time.' base 'קח את הזמן שלך.' -> {\"f\":\"קחי את הזמן שלך.\",\"m\":\"קח את הזמן שלך.\"}\n"
      " EN 'It belongs to you.' base 'זה שלך.' -> {\"f\":\"זה שלך.\",\"m\":\"זה שלך.\"} (no change)\n"
      "Output JSON {id:{\"f\":..,\"m\":..}} only.")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--models", default="deepseek-ai/deepseek-v4-pro,z-ai/glm-5.2,qwen/qwen3.5-397b-a17b"); ap.add_argument("--n", type=int, default=14)
    a = ap.parse_args(); key = load_key()
    if not key.startswith("nvapi-"): print("no key"); return
    batch = sample(a.n)
    print(f"בדיקה דו-שלבית · {len(batch)} שורות דיאלוג רגישות-מגדר\n")
    for k, en in batch: print(f"  · {en}")
    print()
    for model in [m.strip() for m in a.models.split(",") if m.strip()]:
        print("=" * 76); print(f"MODEL: {model}"); print("=" * 76)
        try:
            step1 = chat(key, model, S1, "Translate:\n" + json.dumps({k: en for k, en in batch}, ensure_ascii=False))
            payload2 = {k: {"en": en, "he": step1.get(k, "")} for k, en in batch}
            step2 = chat(key, model, S2, "Gender-split:\n" + json.dumps(payload2, ensure_ascii=False))
        except Exception as e:
            print(f"  FAILED: {e}\n"); continue
        diff = 0; bad = 0
        for k, en in batch:
            f = (step2.get(k, {}).get("f") or "").strip(); m = (step2.get(k, {}).get("m") or "").strip()
            base = step1.get(k, "")
            flag = ""
            if FOREIGN.search(f + m) or NIQ.search(f + m): flag = " [פגם]"; bad += 1
            if f and m and f != m: diff += 1; mark = "✅"
            else: mark = "  "
            print(f"{mark} EN: {en[:48]}")
            print(f"      f={f[:44]}{'  |  m='+m[:44] if m!=f else '  (זהה)'}{flag}")
        print(f"\n  → הבדיל מגדר: {diff}/{len(batch)} | פגמים: {bad}\n")


if __name__ == "__main__":
    main()
