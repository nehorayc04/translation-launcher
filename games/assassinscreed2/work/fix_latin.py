"""Transliterate/translate the uppercase-Latin runs in the Hebrew corpus to Hebrew, so they
render with the BEAUTIFUL A-Z Hebrew atlas instead of gibberish. Word-boundary replace, applied
only OUTSIDE engine tokens (<...>,{...},[TOKEN],%spec). Writes fleet/hebrew.json in place (backup)."""
import json, re, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
HEBJ = os.path.join(HERE, "..", "fleet", "hebrew.json")
STRUCT = re.compile(r"<[^>]+>|\{[^}]*\}|\[(?:[A-Z][A-Za-z0-9_]*|[A-Z0-9][A-Z0-9 _\-]*)\]|%%|%[#0-9.*\-+]*[a-zA-Z]+")

# whole-PHRASE map (longest first) — applied before single words
PHRASE = {
    "ASSASSIN’S CREED® REVELATIONS": "אסאסינ'ס קריד רבלֵיישנס", "ASSASSIN'S CREED® REVELATIONS": "אסאסינ'ס קריד רבלֵיישנס",
    "ASSASSIN’S CREED® LINEAGE": "אסאסינ'ס קריד ליניג'", "ASSASSIN'S CREED® LINEAGE": "אסאסינ'ס קריד ליניג'",
    "ASSASSIN’S CREED® II": "אסאסינ'ס קריד II", "ASSASSIN'S CREED II": "אסאסינ'ס קריד II", "ASSASSIN’S CREED II": "אסאסינ'ס קריד II",
    "ASSASSIN'S CREED": "אסאסינ'ס קריד", "ASSASSIN’S CREED": "אסאסינ'ס קריד",
    "SANTA MARIA DEL FIORE": "סנטה מריה דל פיורה", "CASTEL SANT'ANGELO": "קסטל סנט'אנג'לו",
    "OSPEDALE DEGLI INNOCENTI": "אוספדאלה דלי אינוצֶ'נטי", "MONTE OLIVETO MAGGIORE": "מונטה אוליבֶטו מג'ורה",
    "CAMPANILE DI SAN MARCO": "קמפנילה די סן מרקו", "TORRI DEI SALVUCCI": "טורי דיי סלבוצ'י",
    "LOGGIA DEI LANZI": "לוג'ה דיי לנצי", "LA ROSA DELLA VIRTÙ": "לה רוזה דלה וירטו",
    "TORRE DEL DIAVOLO": "טורה דל דיאבולו", "MERCATO VECCHIO": "מרקטו וֶקיו",
    "REQUIESCAT IN PACE": "רקוּייסקאט אין פאצֶ'ה", "Requiescat in pace": "רקוּייסקאט אין פאצֶ'ה",
    "CAVEAT EMPTOR": "קוויאט אמפטור", "PlayStation®Portable": "פלייסטיישן פורטבל",
    "TELL COREY IF YOU SEE ME": "אמרו לקורי אם תראו אותי", "DATE CLASSIFIED": "תאריך חסוי",
    "Torre dell'Orologio": "טורה דל'אורולוג'ו",
}
# single-WORD / token map
WORD = {
    "Ubisoft": "יוביסופט", "UBISOFT": "יוביסופט", "Uplay": "יופליי", "UPLAY": "יופליי",
    "Xbox": "אקסבוקס", "XBOX": "אקסבוקס", "PlayStation": "פלייסטיישן", "PSP": "פי·אס·פי",
    "Abstergo": "אבסטרגו", "ABSTERGO": "אבסטרגו", "Shaun": "שון", "SHAUN": "שון",
    "Rebecca": "רבקה", "REBECCA": "רבקה", "Arrivederci": "ארוֵידרצ'י", "ARRIVEDERCI": "ארוֵידרצ'י",
    "SCHIAVONA": "סקיאבונה", "HELMSCHMIED": "הלמשמיד", "ABSTERGO": "אבסטרגו",
    "HUD": "ממשק", "DNA": "די·אן·איי", "DLC": "תוכן נוסף", "VSYNC": "סנכרון אנכי",
    "Network": "רשת", "Live": "לַייב", "Club": "מועדון", "Database": "מאגר", "Documents": "מסמכים",
    "CREED": "קריד", "TRIANGLE": "משולש", "ARRRGGGHHH": "אַאַרְררגְגְהְהְ", "AAaiiggggh": "אַאַאיגְגְהְ",
    "Devil": "שטן", "Signori": "סיניורי", "bene": "בֶּנֶה", "et": "אֶט",
    "CUT": "CUT",  # cut-content marker (never shown) -> leave, invisible
}
_PHRASE = sorted(PHRASE.items(), key=lambda p: -len(p[0]))

def fix_run(run):
    for a, b in _PHRASE:
        run = run.replace(a, b)
    def wsub(m):
        w = m.group(0); base = w.rstrip(".®’'")
        return WORD.get(base, WORD.get(w, w)) + w[len(base):] if (base in WORD or w in WORD) else w
    return re.sub(r"[A-Za-z][A-Za-z'’®.\-]*", wsub, run)

def fix(v):
    out, last = [], 0
    for m in STRUCT.finditer(v):
        out.append(fix_run(v[last:m.start()])); out.append(m.group(0)); last = m.end()
    out.append(fix_run(v[last:]))
    return "".join(out)

heb = json.load(open(HEBJ, encoding="utf-8"))
import shutil, time
shutil.copy(HEBJ, HEBJ + ".bak.latinfix." + time.strftime("%Y%m%d_%H%M%S"))
CAP = re.compile(r"[A-Z]")
changed = 0
for k, v in list(heb.items()):
    nv = fix(v)
    if nv != v: heb[k] = nv; changed += 1
tmp = HEBJ + ".tmp"; json.dump(heb, open(tmp, "w", encoding="utf-8"), ensure_ascii=False); os.replace(tmp, HEBJ)
# report residual uppercase-Latin (outside cut-content/cipher)
resid = 0
for k, v in heb.items():
    core = STRUCT.sub(" ", v)
    if CAP.search(core) and "CUT" not in v and len(CAP.findall(core)) < 100: resid += 1
print(f"lines changed: {changed}   residual visible uppercase-Latin lines: {resid}")
