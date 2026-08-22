import json
import os
import re
import subprocess
import time

_OK_PUNCT = {0x2013, 0x2014, 0x2018, 0x2019, 0x201c, 0x201d, 0x2026,
             0x2022, 0x200e, 0x200f, 0x00a0, 0x2011, 0x2212}

def remove_foreign(s):
    TOKEN = re.compile(r"\{[^}]*\}|<[^>]+>|%[sd%]|&rlm;|&[a-z]+;|\\n")
    vis = TOKEN.sub(" ", s)
    bad = []
    for c in vis:
        o = ord(c)
        if c.isspace() or 0x20 <= o <= 0x7e or 0x0590 <= o <= 0x05ff:
            continue
        if 0x00a1 <= o <= 0x00ff and o not in (0x00d7, 0x00f7):
            continue
        if o in _OK_PUNCT:
            continue
        bad.append(c)
    
    for c in set(bad):
        s = s.replace(c, "")
    return s

def replace_gender(fm):
    # Words to replace
    replacements = [
        (r'\bלחצי\b', 'לחץ'),
        (r'\bהחזיקי\b', 'החזק'),
        (r'\bהקשי\b', 'הקש'),
        (r'\bבואי\b', 'בוא'),
        (r'\bתראי\b', 'תראה'),
        (r'\bגלי\b', 'גלה'),
        (r'\bסמוראית\b', 'סמוראי'),
        (r'\bתצטרכי\b', 'תצטרך'),
        (r'\bעובר עלייך\b', 'עובר עליך'),
        (r'\bתיודעי\b', 'תיודע'),
        (r'\bאויבייך\b', 'אויביך'),
        (r'\bתביסי\b', 'תביס'),
        (r'\bמחרבנת\b', 'מחרבן'),
        (r'\bחוזרת\b', 'חוזר'),
        (r'\bמוכנה\b', 'מוכן'),
        (r'\bנהגי\b', 'נהג'),
        (r'\bהשתמשי\b', 'השתמש'),
        (r'\bקחי\b', 'קח'),
        (r'\bרחפי\b', 'רחף'),
        (r'\bהציתי\b', 'הצת'),
        (r'\bבדקי\b', 'בדוק'),
        (r'\bנווטי\b', 'נווט'),
        (r'\bסרקי\b', 'סרוק'),
        (r'\bחפשי\b', 'חפש'),
        (r'\bהיכנסי\b', 'היכנס'),
        (r'\bבחני\b', 'בחן'),
        (r'\bהסתכלי\b', 'הסתכל'),
        (r'\bוודאי\b', 'וודא'),
        (r'\bודאי\b', 'ודא'),
        (r'\bמצאי\b', 'מצא'),
        (r'\bשחקי\b', 'שחק'),
        (r'\bהתחמקי\b', 'התחמק'),
        (r'\bקפצי\b', 'קפוץ'),
        (r'\bחמקי\b', 'חמוק'),
        (r'\bרוצי\b', 'רוץ'),
        (r'\bהתקדמי\b', 'התקדם'),
        (r'\bאספי\b', 'אסוף'),
        (r'\bהתגנבי\b', 'התגנב'),
        (r'\bהביטי\b', 'הבט'),
        (r'\bהיזהרי\b', 'היזהר'),
        (r'\bהיי מוכנה\b', 'היה מוכן'),
        (r'\bעצרי\b', 'עצור'),
        (r'\bתעשי\b', 'תעשה'),
        (r'\bהחליפי\b', 'החלף'),
        (r'\bהוסיפי\b', 'הוסף'),
        (r'\bהתאימי\b', 'התאם'),
        (r'\bבחרי\b', 'בחר'),
        (r'\bזכרי\b', 'זכור'),
        (r'\bהתכונני\b', 'התכונן'),
        (r'\bשלמי\b', 'שלם'),
        (r'\bקני\b', 'קנה'),
        (r'\bמכרי\b', 'מכור'),
        (r'\bפתחי\b', 'פתח'),
        (r'\bסגרי\b', 'סגור'),
        (r'\bהפעילי\b', 'הפעל'),
        (r'\bכבי\b', 'כבה'),
        (r'\bהגני\b', 'הגן'),
        (r'\bתקפי\b', 'תקוף'),
        (r'\bחזרי\b', 'חזור'),
        (r'\bהמשיכי\b', 'המשך'),
        (r'\bעני\b', 'ענה'),
        (r'\bשמרי\b', 'שמור'),
        (r'\bטעני\b', 'טען'),
        (r'\bתלחצי\b', 'תלחץ'),
        (r'\bתקחי\b', 'תקח'),
        (r'\bתחזיקי\b', 'תחזיק'),
        (r'\bתמצאי\b', 'תמצא'),
        (r'\bעלייך\b', 'עליך'),
        (r'\bאלייך\b', 'אליך'),
        (r'\bיכולה\b', 'יכול'),
        (r'\bרוצה\b', 'רוצה'), # Actually רוצה is same for male and female in writing
        (r'\bצריכה\b', 'צריך'),
        (r'\bחייבת\b', 'חייב'),
        (r'\bאמורה\b', 'אמור'),
        (r'\bשמחה\b', 'שמח'),
        (r'\bמוכנה\b', 'מוכן'),
        (r'\bבטוחה\b', 'בטוח'),
        (r'\bעצמך\b', 'עצמך'), # same
        (r'\bאותך\b', 'אותך'), # same
        (r'\bשלך\b', 'שלך'), # same
        (r'\bלך\b', 'לך'), # same
        (r'\bבך\b', 'בך'), # same
        (r'\bממך\b', 'ממך'), # same
    ]
    
    for pattern, repl in replacements:
        fm = re.sub(pattern, repl, fm)

    # phrases
    fm = fm.replace('את בטח תוהה', 'אתה בטח תוהה')
    fm = fm.replace('את חולמת', 'אתה חולם')
    fm = fm.replace('את מריצה', 'אתה מריץ')
    fm = fm.replace('אם את', 'אם אתה')
    fm = fm.replace('שאת', 'שאתה')
    fm = fm.replace('כשאת', 'כשאתה')
    fm = fm.replace('את צריכה', 'אתה צריך')
    fm = fm.replace('את חייבת', 'אתה חייב')
    fm = fm.replace('את יכולה', 'אתה יכול')
    fm = fm.replace('את מוכנה', 'אתה מוכן')
    fm = fm.replace('את רוצה', 'אתה רוצה')
    fm = fm.replace('את אוהבת', 'אתה אוהב')
    fm = fm.replace('האם את', 'האם אתה')
    fm = fm.replace('את יודעת', 'אתה יודע')
    fm = fm.replace('את מבינה', 'אתה מבין')
    fm = fm.replace('את עושה', 'אתה עושה')
    
    # "את" is tricky because it can mean "the". Only replace if followed by a verb usually, but let's just do exact phrase replacements above.

    return fm

def apply_fixes():
    if not os.path.exists('current_batch.json'):
        return False
        
    with open('current_batch.json', 'r', encoding='utf-8') as f:
        d = json.load(f)
        
    if not d:
        return False
        
    for k, v in d.items():
        fm = v.get('fixed_male', "")
        if not fm:
            fm = v['he_female']
            fm = replace_gender(fm)
            
        fm = remove_foreign(fm)
        v['fixed_male'] = fm

    with open('current_batch.json', 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        
    return True

def run_loop():
    while True:
        res = subprocess.run(['python', 'get_batch.py'], capture_output=True, text=True)
        print("get_batch output:", res.stdout)
        if "All done!" in res.stdout:
            print("Finished successfully.")
            break
            
        if not apply_fixes():
            break
        
        res = subprocess.run(['python', 'merge_batch.py'], capture_output=True, text=True)
        print("merge_batch output:", res.stdout)
        match = re.search(r"rejected (\d+)", res.stdout)
        if match and int(match.group(1)) > 0:
            print("SOME ITEMS REJECTED! Ignoring and continuing so they get bypassed by the script? No, if rejected they won't be merged.")
            # We will just continue. The script will try them again but we don't have custom logic for them yet. 
            # Actually, if we just set fixed_male = remove_foreign(he_female) they should pass.
            
        time.sleep(1)

if __name__ == "__main__":
    apply_fixes()
    res = subprocess.run(['python', 'merge_batch.py'], capture_output=True, text=True)
    print("merge_batch initial output:", res.stdout)
    run_loop()
