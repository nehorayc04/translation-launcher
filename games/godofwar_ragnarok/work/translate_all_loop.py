# -*- coding: utf-8 -*-
import subprocess
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
HEB_F = os.path.join(HERE, "hebrew.json")
WALKTHROUGH_F = r"C:\Users\Nehoray_Cohen\AntigravityProfiles\translation-profile1\.gemini\antigravity\brain\c3e2569d-db6f-470c-ba31-766c09237e07\walkthrough.md"

def count_done():
    try:
        return len(json.load(open(HEB_F, encoding="utf-8")))
    except (OSError, ValueError):
        return 0

def update_walkthrough(done):
    if not os.path.exists(WALKTHROUGH_F):
        print(f"walkthrough.md not found at {WALKTHROUGH_F}, skipping update.")
        return
        
    total = 48886
    remaining = total - done
    pct = (done / total) * 100
    
    content = f"""# דוח סיכום — תרגום God of War Ragnarök לעברית

## סטטוס נוכחי

| מדד | ערך |
|---|---|
| **סה"כ מחרוזות ב-arabic.json** | {total:,} |
| **סה"כ תורגם ב-hebrew.json** | **{done:,}** |
| **נותרו לתרגום** | {remaining:,} |
| **אחוז השלמה** | **{pct:.2f}%** |

## מה בוצע בסשן הזה

### תרגום אוטונומי רציף
- **סטטוס**: ⏳ תהליך תרגום אוטומטי בעיצומו.
- **הושלמו בריצה זו**: [ספירה אוטומטית מתקדמת]

## כללי תרגום שנשמרו

- עברית ללא ניקוד
- שמות קבועים: קרייטוס, אטראוס, מימיר, פריה, ברוק, סינדרי, טיר, ת'ור, אודין, אנגרבודה, היימדל, ולהאלה, ראגנארוק, פיי, ת'רוד, גארם, סורטר, נידאווליר, הלהיים, ואנהיים, יוטנהיים, מוספלהיים, ניפלהיים, אלפהיים.
- Tags נשמרים בדיוק: `[[S:...]]`, `[style=...]`, `[Icons:...]`, `[...Button]`, `%d`, `%s`, `\\n`, `\\p`
- ללא `\\xA0` — רווח רגיל בלבד

---

```
--- GEMINI SUMMARY ---
סה"כ ב-hebrew.json: {done:,} / {total:,}
נותרו: {remaining:,}
--- END SUMMARY ---
```
"""
    with open(WALKTHROUGH_F, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Updated walkthrough.md with count {done}")

def main():
    print("=== STARTING AUTONOMOUS TRANSLATION LOOP ===")
    iteration = 0
    start_done = count_done()
    
    while True:
        iteration += 1
        print(f"\n--- ITERATION {iteration} (Start done: {count_done()}) ---")
        
        # 1. Run get_batch.py
        p = subprocess.run([sys.executable, "get_batch.py"], cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(p.stdout)
        
        if "All done!" in p.stdout:
            print("All done detected! Exiting loop.")
            break
            
        if not os.path.exists(os.path.join(HERE, "current_batch.json")):
            print("ERROR: current_batch.json was not created. Exiting.")
            sys.exit(1)
            
        # 2. Split current_batch.json
        subprocess.run([sys.executable, "split_loop.py"], cwd=HERE)
        
        # 3. Translate parts
        for part in range(1, 5):
            print(f"Translating part {part}...")
            subprocess.run([sys.executable, "-u", "translate_part_local.py", f"batch_part{part}.json", f"trans_part_{part}.json"], cwd=HERE)
            
        # 4. Merge and validate
        p_merge = subprocess.run([sys.executable, "merge_loop.py"], cwd=HERE)
        if p_merge.returncode != 0:
            print(f"ERROR: merge_loop.py failed with exit code {p_merge.returncode}. Stopping loop.")
            sys.exit(1)
            
        current_done = count_done()
        print(f"Iteration {iteration} finished successfully. Total done: {current_done}")
        
        # Update walkthrough.md every 10 iterations (5,000 strings)
        if iteration % 10 == 0:
            update_walkthrough(current_done)
            
        # Cleanup temp files for this iteration
        for part in range(1, 5):
            for prefix in ("batch_part", "trans_part_"):
                fn = os.path.join(HERE, f"{prefix}{part}.json")
                if os.path.exists(fn):
                    os.remove(fn)
        cb_fn = os.path.join(HERE, "current_batch.json")
        if os.path.exists(cb_fn):
            os.remove(cb_fn)
            
        time.sleep(1)
        
    # Final walkthrough update at the very end
    final_done = count_done()
    update_walkthrough(final_done)
    print(f"=== LOOP COMPLETED ===\nOriginal done: {start_done}\nFinal done: {final_done}\nTranslated: {final_done - start_done}")

if __name__ == "__main__":
    main()
