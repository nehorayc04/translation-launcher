import json
import os
import subprocess

skips = [
    "0x1ce79ca3", # 0504 S Mo Milton Dr
    "0x386796b5", # 1162 Power St, Apt 3
    "0x3954557c", # 0184 Milton Rd, Apt 13
    "0x4aa07814", # 0115 Bay City Ave, Apt 45
    "0x63b9aa52", # 1561 San Vitas St, Apt 2
    "0x7225c17a", # 3 Alta St, Apt 57
    "0x7e12a20a", # 0605 Spanish Ave, Apt 1
    "0x93f9cdd8", # 3 Alta St, Apt 57
    "0xa6c12f3c", # 0069 Cougar Ave, Apt 19
    "0xa910964c", # San Vitas St, Apt 2
    "0xb06f4298", # 1237 Prosperity St, Apt 21
    "0xec1e39f5", # 2057 Vespucci Blvd, Apt 1
    "0xf787b6c1", # 0112 S Rockford Dr, 13
    "0xad6f6b07", # ~n~Enus Super Diamond~nrt~...
    "0xbfb30f92", # ~n~Dinka Double-T~nrt~...
    "0x9fb22d42"  # BOULEVARD DEL PERRO...
]

translations = {
    # Badger animal feed strings
    "0x09f4f678": "<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> שחף~nrt~~n~<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> וסט היילנד וייט טרייר~nrt~",
    "0x0c43e63a": "<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> קויוטי~nrt~~n~<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> עורב~nrt~",
    "0x129e4969": "<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> האסקי~nrt~~n~<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> אריה הרים~nrt~",
    "0x14c473fe": "<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> רטריבר~nrt~~n~<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> רוטוויילר~nrt~",
    "0x24c4edb6": "<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> האסקי~nrt~~n~<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> אריה הרים~nrt~",
    "0x40fdcc70": "<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> רטריבר~nrt~~n~<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> רוטוויילר~nrt~",
    "0x4293a3b7": "<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> חתול~nrt~~n~<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> נץ~nrt~",
    "0x4b396404": "<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> קויוטי~nrt~~n~<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> עורב~nrt~",
    "0x5818cec1": "<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> חתול~nrt~~n~<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> נץ~nrt~",
    "0x7964d562": "<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> שחף~nrt~~n~<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> וסט היילנד וייט טרייר~nrt~",
    "0x8818daa9": "<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> רטריבר~nrt~~n~<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> רוטוויילר~nrt~",
    "0x931708ce": "<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> שחף~nrt~~n~<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> וסט היילנד וייט טרייר~nrt~",
    "0xaf74c189": "<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> שחף~nrt~~n~<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> וסט היילנד וייט טרייר~nrt~",
    "0xc067a4fd": "<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> האסקי~nrt~~n~<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> אריה הרים~nrt~",
    "0xd5bf4a08": "<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> חתול~nrt~~n~<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> נץ~nrt~",
    "0xe6819779": "<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> רטריבר~nrt~~n~<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> רוטוויילר~nrt~",
    "0xf763bc7a": "<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> קויוטי~nrt~~n~<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> עורב~nrt~",
    "0xf9019630": "<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> האסקי~nrt~~n~<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> אריה הרים~nrt~",
    "0xfb81958c": "<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> חתול~nrt~~n~<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> נץ~nrt~",
    "0xfbca4547": "<img src='img://CELLPHONE_BADGER/u' height=\"32\" width=\"32\" vspace='-10'/> קויוטי~nrt~~n~<img src='img://CELLPHONE_BADGER/t' height=\"32\" width=\"32\" vspace='-10'/> עורב~nrt~",
    
    # Generic short strings
    "0x4fd5798c": "משימות Grand Theft Auto V",
    "0x77ff9feb": "דת'מאץ' אחד על אחד - ~a~",
    "0xabacbda4": "לך אל ~b~נקודת ההתחלה של המרוץ.",
    "0xb86b96c6": "כובע מותאם Red Mist XI",
    "0xe36de706": "אני ~HUD_COLOUR_SOCIAL_CLUB~הסכמתי~s~ לקבל מידע על Rockstar Games, אירועים, השקות ועוד",
    "0xe7fa3745": "חולצה ארוכה Kingz Of Los Santos",

    # Hacker/muscle car instruction texts
    "0x10a0569a": "4 מכוניות השרירים – אנחנו הולכים על Bravado Gauntlets. שיפרתי 1 והבדיקה עבדה טוב, אז אנחנו צריכים רק עוד 3. ההאקר שלף כמה תמונות מרשת מצלמות האבטחה שמראות את הדגמים ב-LS, אבל ההאקר שלנו לא משהו, אז הן לא ממש עוזרות. עם קצת עבודת בלש, אתה אמור להיות מסוגל למצוא אותן בכל זאת. כל 3 Gauntlets יתאימו אם אלה לא יעבדו. תשיג אותן, קח אותן ל-LS Customs לשיפור, ותשאיר אותן במחבוא. תמונות למטה:\r~n~~n~יכול להיות בחניון הרב-קומתי ההוא~n~~nrt~<img src='img://BSPBadHacker/BSPBadHacker1'  height=\"190\" width=\"322\" hspace='5'/>~nrt~~n~~n~הם נראים כמו חנויות יוקרה קלאסיות~n~~nrt~<img src='img://BSPBadHacker/BSPBadHacker2'  height=\"190\" width=\"322\" hspace='5'/>~nrt~~n~~n~אני חושב שהמכונית הזו ליד מלון Templar.~n~~nrt~<img src='img://BSPBadHacker/BSPBadHacker3'  height=\"190\" width=\"322\" hspace='5'/>~nrt~~n~",
    "0x69b189df": "4 מכוניות השרירים – אנחנו הולכים על Bravado Gauntlets. שיפרתי 1 והבדיקה עבדה טוב, אז אנחנו צריכים רק עוד 3. ההאקר שלף כמה תמונות מרשת מצלמות האבטחה שמראות את הדגמים ב-LS – שכרנו מישהו טוב, והוא הצליח להביא את ה-geotag של התמונה, אז מציאתן אמורה להיות קלה. כל 3 Gauntlets יתאימו אם אלה לא יעבדו. תשיג אותן, קח אותן ל-LS Customs לשיפור, ותשאיר אותן במחבוא. תמונות למטה::~n~~n~Pillbox Hill~n~על גבי מגרש חניה רב-קומתי, Pillbox Hill.~n~~nrt~<img src='img://BPDGoodHacker/BSPGoodHacker1'  height=\"322\" width=\"322\" hspace='5'/>~nrt~~n~Rockford Hills~n~CaCa ב-Rockford Hills. חנות התכשיטים ששדדנו נמצאת מאחוריה.~n~~nrt~<img src='img://BPDGoodHacker/BSPGoodHacker2'  height=\"322\" width=\"322\" hspace='5'/>~nrt~~n~Mission Row~n~זה מלון Templar, דרומית מזרחית ל-Legion Square.~n~~nrt~<img src='img://BPDGoodHacker/BSPGoodHacker3'  height=\"322\" width=\"322\" hspace='5'/>~nrt~",
    "0xdde8724b": "4 מכוניות השרירים – אנחנו הולכים על Bravado Gauntlets. שיפרתי 1 והבדיקה עבדה טוב, אז אנחנו צריכים רק עוד 3. ההאקר שלף כמה תמונות מרשת מצלמות האבטחה שמראות את הדגמים ב-LS, יש להם כישורים ממוצעים, ולכן התמונות הן לא הכי טובות או גרועות. עם קצת עבודת בלש, אתה אמור להיות מסוגל למצוא אותן. כל 3 Gauntlets יתאימו אם אלה לא יעבדו. תשיג אותן, קח אותן ל-LS Customs לשיפור, ותשאיר אותן במחבוא. תמונות למטה:~n~Pillbox Hill~n~חניון רב-קומתי במרכז העיר~n~~nrt~<img src='img://BPSMedHacker/BSPMedHacker1'  height=\"190\" width=\"322\" hspace='5'/>~nrt~~n~Rockford Hills~n~ליד חנויות היוקרה היוקרתיות ב-Rockford Hills.~n~~nrt~<img src='img://BPSMedHacker/BSPMedHacker2'  height=\"190\" width=\"322\" hspace='5'/>~nrt~~n~Mission Row~n~ליד מלון דרעק כלשהו, ה-Templar.~n~~nrt~<img src='img://BPSMedHacker/BSPMedHacker3'  height=\"190\" width=\"322\" hspace='5'/>~nrt~",
    
    # Facebook link strings
    "0x578e0888": "~HUD_COLOUR_WHITE~Grand Theft Auto V מקושר כעת לפייסבוק עם שם המשתמש שסופק. יסופקו לך אפשרויות שיתוף מסוימות במשחק, כגון שיתוף תמונות גלריה.<br><br>נפרסם באופן אוטומטית בפייסבוק בכל פעם שתבצע את הפעולות הבאות:<br>יצירת דמות ב-Grand Theft Auto Online<br>השלמת שוד<br>השלמת Grand Theft Auto V<br>השלמת רשימת ה-100%<br>קנייה ונהיגה בכל רכבי Legendary Motorsport<br>קניית כל הנכסים<br>חקירת המפה כולה<br><br>כברירת מחדל, פוסטים שנעשו מ-Grand Theft Auto V יהיו גלויים לחברי הפייסבוק שלך בלבד. תוכל לשנות את ההגדרות שלך בכתובת ~HUD_COLOUR_FACEBOOK_BLUE~facebook.com",
    "0x67fcaeb7": "~HUD_COLOUR_RED~נכנסת עם חשבון שאין לו הרשאה לפרסם תוכן, או ששיתוף ברשתות חברתיות אינו מופעל בו.<br><br>~HUD_COLOUR_WHITE~אחרת, תוכל לקשר את חשבון הפייסבוק שלך כדי לשתף ולהפיץ את הבשורה על חווית ה-GTA שלך, כולל להלן<br>יצירת דמות ב-Grand Theft Auto Online<br>השלמת שוד<br>השלמת Grand Theft Auto V<br>השלמת רשימת ה-100%<br>קנייה ונהיגה בכל רכבי Legendary Motorsport<br>קניית כל הנכסים<br>חקירת המפה כולה",
    "0xb1dd6df6": "קשר את חשבון הפייסבוק שלך כדי לשתף ולהפיץ את הבשורה על חווית ה-GTA שלך, כולל:<br>יצירת דמות ב-Grand Theft Auto Online<br>השלמת שוד<br>השלמת Grand Theft Auto V<br>השלמת רשימת ה-100%<br>קנייה ונהיגה בכל רכבי Legendary Motorsport<br>קניית כל הנכסים<br>חקירת המפה כולה<br><br>כברירת מחדל, פוסטים שנעשו מ-Grand Theft Auto V יהיו גלויים לחברי הפייסבוק שלך בלבד. לחץ למטה כדי לקשר את החשבון שלך. קישור החשבון שלך יפורסם אוטומטית על קיר הפייסבוק שלך."
}

def main():
    # Update skip.json
    skip_path = "skip.json"
    if os.path.exists(skip_path):
        try:
            curr_skips = set(json.load(open(skip_path, encoding="utf-8")))
        except Exception:
            curr_skips = set()
    else:
        curr_skips = set()
        
    curr_skips.update(skips)
    
    with open(skip_path, "w", encoding="utf-8") as f:
        json.dump(sorted(list(curr_skips)), f, ensure_ascii=False, indent=1)
    print("Updated skip.json. Current skips count:", len(curr_skips))
        
    # Write batch_he.json
    with open("batch_he.json", "w", encoding="utf-8") as f:
        json.dump(translations, f, ensure_ascii=False, indent=1)
    print("Wrote batch_he.json.")
        
    # Run loop_merge.py
    subprocess.run(["python", "loop_merge.py", "batch_he.json"], check=True)

if __name__ == "__main__":
    main()
