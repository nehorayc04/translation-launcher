"""Build the Phase-2 translation handoff (New-Era method).

Creates games/signalrgb/agent_handoff/ :
    to_translate.json   {key: {context, en, refs:{ar,ko,zh_CN,zh_TW,sr,ja}}}
    hebrew.json         {} - the output the translator fills
    name_registry.json  terms that must stay Latin + the locked glossary
    INSTRUCTIONS.md     the full brief

Ordering is by VISIBILITY: the strings a user meets first come first, and the
developer/diagnostic panels come last - so a partial pass still translates the
part of the app people actually see.

The reference columns come from the app's OWN shipped languages, labeled by
SCRIPT (SignalRGB ships a .qm whose Language block lies - see RECON.md).
They are MACHINE translations: use them to decide meaning/register/gender by
cross-language consensus, never copy one blindly.
"""
import os, sys, json, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROOT, 'agent_handoff')
EXTRACT = os.path.join(ROOT, 'extract')

# context keyword -> visibility bucket (lower = seen sooner / by more users)
BUCKETS = [
    (1, ('navpanel', 'main', 'settingsnav', 'onboarding', 'dashboard', 'home')),
    (2, ('settings', 'device', 'effect', 'layout', 'lighting', 'canvas',
         'macro', 'addon', 'monitor', 'fan', 'cooling', 'account', 'billing',
         'notification', 'audio', 'video', 'service', 'component')),
    (3, ()),                                     # everything else
    (4, ('dev', 'debug', 'smbus', 'inspector', 'console', 'mcp', 'log',
         'diagnostic', 'primitive')),
]

# Terms that must stay Latin verbatim (brands, protocols, product names).
KEEP_LATIN = [
    'SignalRGB', 'Signal RGB', 'WhirlwindFX', 'Corsair', 'iCUE', 'Razer',
    'Synapse', 'Logitech', 'ASUS', 'Aura', 'Aura Sync', 'MSI', 'Mystic Light',
    'Gigabyte', 'RGB Fusion', 'NZXT', 'CAM', 'Govee', 'Nanoleaf', 'Philips',
    'Hue', 'Cooler Master', 'Alienware', 'SteelSeries', 'HyperX', 'Wooting',
    'OpenRGB', 'Home Assistant', 'Discord', 'Twitch', 'Spotify', 'Steam',
    'Windows', 'macOS', 'Linux', 'Nvidia', 'AMD', 'Intel',
    'RGB', 'ARGB', 'SMBus', 'I2C', 'USB', 'HID', 'DPI', 'LED', 'MCP', 'API',
    'HTTP', 'JSON', 'CPU', 'GPU', 'RAM', 'FPS', 'PWM', 'RPM', 'QMK', 'SDK',
    'Pro', 'SignalRGB Pro', 'Ultralight', 'lightscripts', 'Lightscript',
    'ms', 'Breakpad', 'Cloudflare', 'Git', 'NanoLeaf', 'Govee', 'Discord',
    'DeviceManager', 'DeviceGrid', 'vortx', 'Vision Core', 'Qt WebEngine',
    'Windows Dynamic Lighting', 'LCD', 'OCR', 'MSI Center', 'MSI Bridge',
    'lightscript', 'lightscript:', 'AIO', 'WiFi', 'RTX', 'Esc', 'X', 'Y', '%',
    'Model Context Protocol', 'Claude', 'Anthropic', 'NVIDIA G-Assist', 'G-Assist',
    'TjMax [°C]', 'TSlope [°C]', 'TjMax', 'TSlope', 'CorsairLink', 'SMBus Mutex',
    'MiniPlayer', 'Ping', 'udev', 'Light Points', 'N/A', 'QR', 'crc', 'uid',
]

# One English term -> one Hebrew term, everywhere. Extend during the pass.
GLOSSARY = {
    'Effect': 'אפקט',
    'Effects': 'אפקטים',
    'Layout': 'פריסה',
    'Layouts': 'פריסות',
    'Canvas': 'קנבס',
    'Device': 'התקן',
    'Devices': 'התקנים',
    'Component': 'רכיב',
    'Components': 'רכיבים',
    'Layer': 'שכבה',
    'Layers': 'שכבות',
    'Macro': 'מאקרו',
    'Macros': 'מאקרו',
    'Add-on': 'תוסף',
    'Add-ons': 'תוספים',
    'Profile': 'פרופיל',
    'Preset': 'פריסט',
    'Lighting': 'תאורה',
    'Brightness': 'בהירות',
    'Settings': 'הגדרות',
    'Dashboard': 'לוח בקרה',
    'Monitoring': 'ניטור',
    'Fan': 'מאוורר',
    'Fans': 'מאווררים',
    'Fan Curve': 'עקומת מאוורר',
    'Notification': 'התראה',
    'Notifications': 'התראות',
    'Account': 'חשבון',
    'Sign In': 'התחברות',
    'Sign Out': 'התנתקות',
    'Language': 'שפה',
    'Home': 'בית',
    'Library': 'ספרייה',
    'Discover': 'גילוי',
    'Cooling': 'קירור',
    'Customize': 'התאמה אישית',
    'System': 'מערכת',
    'Free': 'חינם',
    'Installed': 'מותקן',
    'Playlist': 'רשימת השמעה',
    'Playlists': 'רשימות השמעה',
    'Troubleshooting': 'פתרון תקלות',
    'Skip': 'דלג',
    'Back': 'חזרה',
    'Continue': 'המשך',
    'Yes': 'כן',
    'No': 'לא',
    'Help': 'עזרה',
    'Install': 'התקן',
    'About': 'אודות',
    'Privacy': 'פרטיות',
    'Audio': 'שמע',
    'Video': 'וידאו',
    'Billing': 'חיוב',
    'Conflicts': 'התנגשויות',
    'Windows': 'Windows',
}


def bucket(ctx):
    c = (ctx or '').lower()
    for score, keys in BUCKETS:
        if score == 3:
            continue
        if any(k in c for k in keys):
            return score
    return 3


def main():
    ref = json.load(open(os.path.join(EXTRACT, 'reference.json'), encoding='utf-8'))
    os.makedirs(OUT, exist_ok=True)

    langs = ('ar', 'sr', 'ru', 'ja', 'ko', 'zh_CN', 'zh_TW')
    rows = {}
    for k, v in ref.items():
        refs = {L: v[L] for L in langs if v.get(L)}
        rows[k] = {'context': v['context'], 'en': v['en'], 'refs': refs}

    order = sorted(rows, key=lambda k: (bucket(rows[k]['context']),
                                        rows[k]['context'].lower(),
                                        rows[k]['en'].lower()))
    ordered = {k: rows[k] for k in order}

    json.dump(ordered, open(os.path.join(OUT, 'to_translate.json'), 'w',
                            encoding='utf-8'), ensure_ascii=False, indent=1)
    hp = os.path.join(OUT, 'hebrew.json')
    if not os.path.isfile(hp):
        json.dump({}, open(hp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump({'keep_latin': KEEP_LATIN, 'glossary': GLOSSARY},
              open(os.path.join(OUT, 'name_registry.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    counts = collections.Counter(bucket(r['context']) for r in rows.values())
    avg_refs = sum(len(r['refs']) for r in rows.values()) / max(1, len(rows))
    print('to_translate : %d strings' % len(rows))
    print('by visibility: 1=%d  2=%d  3=%d  4=%d'
          % (counts[1], counts[2], counts[3], counts[4]))
    print('avg reference languages per line: %.1f' % avg_refs)
    print('wrote ->', OUT)

    open(os.path.join(OUT, 'INSTRUCTIONS.md'), 'w', encoding='utf-8').write(
        INSTRUCTIONS.replace('__N__', str(len(rows))))


INSTRUCTIONS = """# SignalRGB → עברית — הנחיות למתרגם

**משימה:** לתרגם __N__ מחרוזות ממשק של SignalRGB (תוכנת RGB למחשב) מאנגלית לעברית.

## קבצים
* `to_translate.json` — `{מפתח: {context, en, refs}}`. ה-`refs` הן התרגומים
  שהיצרן עצמו שילח: `ar` ערבית, `sr` סרבית, `ja` יפנית, `ko` קוריאנית,
  `zh_CN` סינית מפושטת, `zh_TW` סינית מסורתית.
* `hebrew.json` — **קובץ הפלט**. `{אותו מפתח: "העברית"}`. אל תשנה מפתחות.
* `name_registry.json` — מונחים שנשארים לטיניים + מילון מונחים נעול.

## שיטה — "עידן חדש"
מחליטים כל שורה מול **פאנל השפות**, לא מהאנגלית לבד. האנגלית לבדה מאבדת
מידע (מין, פנייה, האם זו פקודה או שם עצם); השפות שנשלחו כבר הכריעו.

⚠️ **התרגומים של היצרן הם תרגום־מכונה ויש בהם שגיאות אמיתיות** —
`Sign Out → انقر فوق` ("לחץ על"), `Decline → انخفاض` ("ירידה"),
`Macros → ماكرون` (שם המשפחה מקרון). לכן: **קונצנזוס בין שפות**, ואם שפה
אחת חורגת מהשאר — התעלם ממנה. הן עוזרות להכריע משמעות/רגיסטר, לא מחליפות שיפוט.

## כללים נוקשים
1. **אחסון לוגי.** כותבים עברית טבעית. **בלי היפוך אותיות, בלי `&rlm;`,
   בלי RLE/PDF** — הוכח במשחק שהמנוע מריץ bidi בעצמו.
2. **טוקנים נשמרים בדיוק:** `%1`…`%9` (42 מופעים), `%` בודד (11), `\\n` (26).
   אותה כמות, אותם טוקנים, בדיוק. `\\n` הוא שבירת שורה אמיתית.
3. **מספרים ומזהים שורדים** — כל ספרה שיש באנגלית חייבת להופיע בעברית.
   מזהים באותיות גדולות/camelCase (`SMBus`, `ARGB`, `DPI`) נשארים לטיניים.
4. **מותגים ופרוטוקולים נשארים לטיניים** — ראה `keep_latin`.
5. **מילון נעול** — מונח אנגלי אחד ⇒ מונח עברי אחד בכל התוכנה
   (`name_registry.json`). אם חסר מונח, קבע אותו פעם אחת והוסף לרשימה.
6. **בלי ניקוד. בלי כתב זר** (ערבית/קירילית/סינית/יפנית לא נכנסות לפלט).
7. **אל תהפוך מילות כיוון.** נצפה במסך: **התוכנה לא ממרקרת (mirror) את
   הפריסה** — הטקסט מוצג RTL אבל הפאנלים והיישור נשארים כמו באנגלית. לכן
   "the left panel" נשאר "הפאנל השמאלי". אם משפט מפנה לצד מסך — השאר כפי שהוא.
8. **רגיסטר:** ממשק תוכנה, גוף שני יחיד ניטרלי, קצר ותכליתי. כפתור = שם
   פעולה (`שמור`, `בטל`, `החל`), לא משפט. כותרת = שם עצם.
9. אורך: התוויות בסרגל הצד קצרות — העדף מילה אחת קצרה על צירוף ארוך.

## סדר העבודה
הקובץ ממוין לפי **נראוּת**: קודם ניווט/הגדרות/onboarding, בסוף פאנלים
של מפתחים ואבחון. תרגם לפי הסדר — כך גם מעבר חלקי מכסה את מה שרואים.

## בסיום
הרץ `python ../work/qa_scan.py`. הוא בודק כיסוי, טוקנים, מספרים, ניקוד,
כתב זר, מזהים ועקביות מילון. **בנייה חסומה כל עוד יש כשלים.**
"""


if __name__ == '__main__':
    main()
