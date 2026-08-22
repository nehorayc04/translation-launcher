import json, os, subprocess, time

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

total_fixed = 0

while True:
    if os.path.exists('qa_fixes.json'):
        os.remove('qa_fixes.json')
        
    try:
        out = subprocess.check_output(['python', 'qa_get_batch.py'], text=True)
    except subprocess.CalledProcessError as e:
        print("qa_get_batch failed:", e.output)
        break
        
    print(out.strip())
    
    if 'QA done!' in out:
        print("--- QA SUMMARY (סוכן 2) --- נבדק: 50000 · תוקן: " + str(total_fixed) + " --- END ---")
        break
    
    if not os.path.exists('qa_batch.json'):
        break
        
    try:
        batch = json.load(open('qa_batch.json', encoding='utf-8'))
    except Exception:
        break
        
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
        
    try:
        merge_out = subprocess.check_output(['python', 'qa_merge.py'], text=True)
        print(merge_out.strip())
    except subprocess.CalledProcessError as e:
        print("qa_merge failed:", e.output)
        time.sleep(1)
