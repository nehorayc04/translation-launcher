import sys, json, re
sys.path.insert(0, '../../../../universal')
from gender_oracle import he_addressee

HEB = re.compile(r'[֐-׿]')

def scaffold(s):
    return re.sub(r'\s', '', HEB.sub('', s))

tofix = json.load(open('to_fix.json', encoding='utf-8'))

fixes = {
  '360948': 'אתם עייפים, לכו הביתה.',
  '480903': 'את רוח, לא אישה!',
  '1156420': 'את מנהלת את הכרם לבד?',
  '401649': 'אני יודעת איפה אמך.',
  '1119350': 'לפני שתלכי... צריכה לבקש ממך חסד.',
  '1147938': 'חכה להזדמנות להוכיח חכמתך.',
  '558692': 'עיזבו עכשיו. אתם מפריעים לטקס.',
  '562103': 'אתם לא יודעים שום דבר על מנהגיהם.',
  '1113638': "אני מתנגד, גברתי. את מפסיקה את המרכיב החשוב ביותר בכריכת גינג'ר - הזמן.",
  '388628': "שומרים זולים למוות - אתם מקבלים את הערך שלכם! אפילו פחות! תודה לך, ויצ'ר! איפה הייתי בלעדיכם?",
  '1192023': 'כבר היה מטריד אותי כל הסודות שלך… עכשיו אני יודעת שאם יש לך משהו לומר לי, תגידי לי. לא צריכה לשאול.',
  '1182571': 'איך אני נראית? ובכל מקרה, המראה מטעה. אני לא מחפשת עשבים נפוצים שצומחים בכל מרעה, אלא מרכיבים נדירים. האם תוכלי לעזור לי? או שאצטרך להמשיך?',
  '1125029': 'את נוטלת הלוואות, תזונה קבועה. הפסיקי, ובעיה של הרוח תיעלם. נפרד.',
  '1100559': '\u202eאולי לקונטסה יש עוד ענייני וויטשר שהיא מוכנה לוותר עליהם? או לרכוש. אולי את יכולה לערוך עסקה? אני אגבה... חמישה אחוז - עמלה זעירה, אם לומר כך.',
  '1091536': 'אקח אותך לשם. אבל קודם צריכה לראות את האיש הרע.',
  '556580': 'לקיסר תוכניות לגביך - אני בטוחה בזאת.',
  '556693': 'אל תדאגי. לקיסר יש תוכניות לך - אני בטוחה בזה.',
}

errors = []
for k, new in fixes.items():
    if new.upper() == 'SKIP':
        print(f'{k}: SKIP -> OK')
        continue
    if k not in tofix:
        print(f'{k}: NOT IN TOFIX')
        continue
    orig = tofix[k]['he']
    tgt = tofix[k]['target']
    s_orig = scaffold(orig)
    s_new = scaffold(new)
    oracle = he_addressee(new)
    ok_scaffold = (s_orig == s_new)
    ok_oracle = (oracle in (tgt, None))
    ok_changed = (new != orig)
    status = 'OK' if (ok_scaffold and ok_oracle and ok_changed) else 'FAIL'
    if status == 'FAIL':
        errors.append(k)
        print(f'{k} [{tgt}]: {status}  scaffold={ok_scaffold} oracle={oracle}({ok_oracle}) changed={ok_changed}')
        if not ok_scaffold:
            print(f'  orig scaffold: {repr(s_orig[:80])}')
            print(f'  new  scaffold: {repr(s_new[:80])}')
    else:
        print(f'{k} [{tgt}]: OK (oracle={oracle})')

print(f'\n{len(errors)} errors: {errors}')
