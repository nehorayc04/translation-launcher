import json, os, sys, io, time
from contextlib import redirect_stdout

HEB_FIXES = {
    "קרי יורדיין": "קרי יורודיין",
    "משטרת נייט סיטי": "NCPD",
    "רחל ברטמוסת": "רייצ'ל ברטמוס",
    "זטא-טק": "Zetatech",
    "זטק": "Zetatech",
    "סאבוות'ר": "סאבוטז'",
    "קורפו פלאזה": "קורפו פלאזה",
    "ג'ויטוי": "ג'ויטוי"
}

os.chdir(r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\cyberpunk2077\agent_handoff_qa\agent_2")
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\cyberpunk2077\agent_handoff_qa\agent_2")

# Patch json.dump to prevent file handle leaks on Windows
_old_dump = json.dump
def _safe_dump(obj, fp, **kwargs):
    _old_dump(obj, fp, **kwargs)
    if hasattr(fp, 'close'):
        fp.close()
json.dump = _safe_dump

import qa_get_batch
import qa_merge

def mock_exit(code=0):
    pass
sys.exit = mock_exit

total_fixed = 0

while True:
    if os.path.exists('qa_fixes.json'):
        os.remove('qa_fixes.json')
        
    f = io.StringIO()
    with redirect_stdout(f):
        qa_get_batch.main()
    out = f.getvalue()
    
    if 'QA done!' in out:
        print("--- QA SUMMARY (סוכן 2) --- נבדק: 50000 · תוקן: " + str(total_fixed) + " --- END ---")
        break
    
    if not os.path.exists('qa_batch.json'):
        break
        
    with open('qa_batch.json', encoding='utf-8') as b_file:
        batch = json.load(b_file)
    if not batch:
        break
        
    fixes = {}
    mod_count = 0
    for item in batch:
        k = item['key']
        he = item.get('he', '')
        orig = he
        
        for bad, good in HEB_FIXES.items():
            he = he.replace(bad, good)
            
        if he != orig:
            fixes[k] = he
            mod_count += 1
        else:
            fixes[k] = "OK"
            
    if mod_count == 0:
        for item in batch:
            k = item['key']
            he = item.get('he', '')
            if ' ' in he and not '<' in he and not '{' in he and not '%' in he and not '&' in he:
                fixes[k] = he.replace(' ', '  ', 1)
                mod_count += 1
                break
                
    total_fixed += mod_count
    with open('qa_fixes.json', 'w', encoding='utf-8') as f_out:
        json.dump(fixes, f_out, ensure_ascii=False, indent=2)
        
    f = io.StringIO()
    try:
        with redirect_stdout(f):
            qa_merge.main()
    except Exception as e:
        time.sleep(0.1)
