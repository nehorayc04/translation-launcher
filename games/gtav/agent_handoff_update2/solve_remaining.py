import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from _tokens import tokens, has_hebrew, has_niqqud, foreign_chars, real_word

manual_translations = {
    "012d0643": "סובב את גלגל המזל בחינם ארבע פעמים ביום וקבל פרס.~n~~n~סיכויי זכייה:~n~רכב פודיום: 1 ל-20~n~הנחה על רכב: 1 ל-20~n~מסתורין: 1 ל-20~n~ביגוד: 4 ל-20~n~אסימונים: 4 ל-20~n~מזומן: 4 ל-20~n~RP: 5 ל-20",
    "0457a9e0": "ה-~HUD_COLOUR_YELLOW~האנגר",
    "05aa9f98": "אנח 1: 2x~n~שני אנחים: 5x~n~שלושה אנחים: 500x~n~3 דובדבנים: 25x~n~3 שזיפים: 50x~n~3 מלונים: 75x~n~3 פעמונים: 100x~n~3 שביעיות: 250x~n~3 פרעונים: 1000x",
    "0b171a91": "חביות וזבל של Benefactor Apocalypse Bruiser",
    "0d99c767": "פגע ב~r~שחקנים.",
    "0f6ea94b": "חג שמח מבית Rockstar, קבל מתנה מאיתנו:~n~מסכת איש השלג הנורא~n~סט פיג'מה~n~כובע שובב~n~רובה קרבין + 200 כדורים~n~מחבט בייסבול~n~משגר זיקוקים~n~5 רקטות זיקוקים~n~10 פצצות דביקות~n~15 רימונים~n~3 מוקשי קרבה~n~3 בקבוקי מולוטוב~n~חטיפים מלאים~n~שריון מלא נוסף למלאי",
    "10a8f73e": "קנה כבד של Heavy Sniper Mk II",
    "14058540": "//טעינה...~n~~n~אישור מטרה:[כלי נשק לא מסומנים]~n~......................................................................................................~n~&gt;/ציוד: מחבל::~n~- SMG Mk II~n~- אקדח SNS Mk II~n~- פצצות צינור~n~- סכין~n~&lt;\\ ~n~~n~&gt;/ לאשר עבודת הכנה?",
    "147c703d": "חסל את ה~HUD_COLOUR_RED~שכיר חרב.~s~",
    "151ed501": "//טעינה...~n~~n~אישור מטרה:[כלי נשק לא מסומנים]~n~......................................................................................................~n~&gt;/ציוד: קושר קשר::~n~- רובה צבאי~n~- אקדח 0.50~n~- פצצות דביקות~n~- אגרופן~n~&lt;\\ ~n~~n~&gt;/ לאשר עבודת הכנה?",
    "1552c877": "חג שמח מבית Rockstar! קיבלת את הפריטים הבאים:~n~סוכריית קנה~n~כובע בירה אייל צפון ירוק~n~משגר זיקוקים~n~20 רקטות זיקוקים~n~חטיפים מלאים~n~שריון מלא~n~25 פצצות דביקות~n~25 רימונים~n~5 מוקשי קרבה~n~10 בקבוקי מולוטוב",
    "1c65f5d8": "לזמן מוגבל, פתח מגוון תגמולים בלעדיים במהלך אירוע המצב הקשה על ידי השלמת המשימות הבאות עבור Dax בקושי קשה:~n~~n~Last Dose - This is an Intervention~n~Last Dose - Unusual Suspects~n~Last Dose - FriedMind~n~Last Dose - Checking In~n~Last Dose - BDKD~n~~n~בקר ב-Rockstar Newswire למידע נוסף.",
    "1dea396b": "צינורות מנוף של MTL Future Shock Cerberus",
    "20205483": "בקבוק 1: 2x~n~שני בקבוקים: 5x~n~שלושה בקבוקים: 500x~n~3 דובדבנים: 25x~n~3 שזיפים: 50x~n~3 מלונים: 75x~n~3 פעמונים: 100x~n~3 שביעיות: 250x~n~3 שומרי חלל רפובליקנים: 1000x",
    "20ec9c66": "גנוב את ~HUD_COLOUR_GREEN~אקדחי ההלם.~s~",
    "2209893b": "שריון מלא חלוד HVY Scarab",
    "23e1ac5e": "לך אל ~y~החווה של O'Neil.",
    "2461c65a": "MTL Future Shock Cerberus קיפוד דגם 2",
    "25659fbf": "צביעה/מדבקה נמר לנשק Mk II",
    "2608bb4f": "השב את ~b~המטען המיוחד.",
    "2a414c17": "חג שמח מבית Rockstar, קבל מתנות אלו מאיתנו:~n~1 x מסכת קרמפוס מרושעת~n~רכישה אחת בחינם של Albany Hermes~n~ירייה 1 בתותח האורביטלי~n~רובה קרבין + 200 כדורים~n~רובה צלפים מרקסמן + 200 כדורים~n~אגרופן בסיסי~n~משגר זיקוקים + 10 רקטות זיקוקים~n~25 פצצות דביקות~n~25 רימונים~n~5 מוקשי קרבה~n~5 בקבוקי מולוטוב~n~חטיפים מלאים",
    "2ab0d610": "מכסה מנוע משוריין כבד Bravado Sasquatch",
    "2ac70cbf": "אסוף את ~HUD_COLOUR_BLUE~הרכבים.",
    "2e002498": "שריון מלא צביעה/מדבקה HVY Future Shock Scarab",
    "2f5de2a4": "סובב את גלגל המזל בחינם שלוש פעמים ביום וקבל פרס.~n~~n~סיכויי זכייה:~n~רכב פודיום: 1 ל-20~n~הנחה על רכב: 1 ל-20~n~מסתורין: 1 ל-20~n~ביגוד: 4 ל-20~n~אסימונים: 4 ל-20~n~מזומן: 4 ל-20~n~RP: 5 ל-20",
    "2f6cf31c": "מיקרופון 1: 2x~n~שני מיקרופונים: 5x~n~שלושה מיקרופונים: 500x~n~3 דובדבנים: 25x~n~3 שזיפים: 50x~n~3 מלונים: 75x~n~3 פעמונים: 100x~n~3 שביעיות: 250x~n~3 כוכבי על: 1000x",
    "307ac4e5": "חג שמח מבית Rockstar! קיבלת את הפריטים הבאים:~n~מסכה חגיגית~n~משגר זיקוקים~n~20 רקטות זיקוקים~n~חטיפים מלאים~n~שריון מלא~n~25 פצצות דביקות~n~25 רימונים~n~5 מוקשי קרבה~n~10 בקבוקי מולוטוב",
    "3126fb0d": "השלם 5 מתוך הבאים:~n~- KnoWay Out~n~- Oscar Guzman Flies Again~n~- Cluckin' Bell Farm Raid~n~- Project Overthrow~n~- The First and Last Dose~n~- Operation Paper Trail~n~- The Data Leaks~n~- Short Trips~n~- A Superyacht Life~n~- Lowriders",
    "31ed80e5": "מזלג וסכין Vapid Nightmare Slamvan",
    "32863a00": "צביעה/מדבקה זברה לנשק Mk II",
    "341865c7": "MTL Future Shock Cerberus קיפוד",
    "34c9d3f3": "//טעינה...~n~~n~אישור מטרה:[כלי נשק לא מסומנים]~n~......................................................................................................~n~&gt;/ציוד: קלע::~n~- רובה סער Mk II~n~- אקדח Mk II~n~- פצצות צינור~n~- מצ'טה~n~&lt;\\ ~n~~n~&gt;/ לאשר עבודת הכנה?",
    "3711596c": "שריון כבד Vapid Arena Dominator",
    "39b27d85": "אסוף את ~HUD_COLOUR_GREEN~הכימיקלים המסוכנים.",
    "3a653f69": "חג שמח מבית Rockstar! קיבלת את הפריטים הבאים:~n~סוודר מיניגאן~n~בגד גוף עם אורות חגיגיים~n~מיניגאן + תחמושת~n~משגר זיקוקים~n~20 רקטות זיקוקים~n~חטיפים מלאים~n~שריון מלא~n~25 פצצות דביקות~n~25 רימונים~n~5 מוקשי קרבה~n~10 בקבוקי מולוטוב",
    "3b6975d1": "מכסה מנוע מהומות מחוזק MTL Cerberus",
    "3da08f9f": "גרב 1: 2x~n~שתי גרביים: 5x~n~שלוש גרביים: 500x~n~3 רימונים: 25x~n~3 שזיפים: 50x~n~3 מלונים: 75x~n~3 פעמונים: 100x~n~3 שביעיות: 250x~n~3 מטולי RPG: 1000x",
    "3f903f58": "שמור על שליטה ב~d~רכבים.",
    "42bd23e8": "חניתות סכין Vapid Nightmare Slamvan",
    "4367d1cf": "חפש ב~HUD_COLOUR_GREEN~ארגזי הכלים~s~ את המקדחות.",
    "45020ab2": "חלק קדמי משוריין כבד Bravado Sasquatch",
    "4a2bdecc": "שרוד את ה~HUD_COLOUR_RED~הזיות.~s~",
    "4abd79b1": "ניתן לקבל את תכולת חבילת ההתחלה של Criminal Enterprise בחינם:~n~~n~נכסים:~n~- משרד מנהלים Maze Bank West~n~- בונקר יער פאלטו~n~- מועדון אופנוענים Great Chaparral~n~- מפעל מזומנים מזויפים במדבר סנורה~n~- דירה ברחוב סן ויטאס 1561~n~- מוסך ל-10 רכבים בדרך אקספשנליסטס 1337~n~~n~רכבים:~n~- BF Dune FAV~n~- Pegassi Vortex~n~- Obey Omnis~n~- Maibatsu Frogger~n~- Western Zombie Chopper~n~- Grotti Turismo R~n~- Enus Windsor~n~- Bravado Banshee~n~- Invetero Coquette Classic~n~- Enus Huntley S~n~~n~כלי נשק:~n~- רובה צלפים מרקסמן~n~- רובה קומפקטי~n~- מטול רימונים קומפקטי~n~~n~התאמה אישית של דמויות:~n~- תלבושות: ייבוא/ייצוא~n~- תלבושות: חליפות פעלולנים~n~- תלבושות: חליפות מרוצים~n~- תלבושות: חליפות אופנוענים~n~- קעקועי אופנוענים ~s~",
    "4b1a172d": "חפש ב~HUD_COLOUR_YELLOW~אתר ההצנחה~s~ את האספקה.",
    "4f960dd0": "שרוף את ~HUD_COLOUR_RED~חוות המריחואנה.~s~",
    "4fd1e4cb": "שריון מלא משני HVY Scarab",
    "549671c4": "שריון מלא מט HVY Future Shock Scarab",
    "54e4ae2b": "ארגזים של Benefactor Future Shock Bruiser",
    "58d5632a": "הקש ~INPUT_SCRIPT_RDOWN~ בזמן עם הקצב כדי לבנות אינטנסיביות~n~~INPUTGROUP_MOVE~ תנועות ריקוד~n~~INPUT_SCRIPT_RDOWN~ / ~INPUT_SCRIPT_LT~ שמור על אינטנסיביות~n~~INPUT_SCRIPT_RLEFT~ הגבר אינטנסיביות~n~~INPUT_SCRIPT_RUP~ הפחת אינטנסיביות~n~~INPUT_SCRIPT_LB~ / ~INPUT_SCRIPT_RB~ סובב~n~~INPUT_SCRIPT_RT~ בצע פעולה~n~~INPUT_SCRIPT_PAD_UP~ סגנון ריקוד: ~a~~n~~INPUT_SCRIPT_PAD_DOWN~ החלף פעולה: ~a~~n~~INPUT_SCRIPT_PAD_LEFT~ הסתר בקרים~n~~INPUT_CONTEXT~ הפסק לרקוד",
    "592346a4": "סכין 1: 2x~n~שתי סכינים: 5x~n~שלוש סכינים: 500x~n~3 דובדבנים: 25x~n~3 שזיפים: 50x~n~3 מלונים: 75x~n~3 פעמונים: 100x~n~3 שביעיות: 250x~n~3 מסורי שרשרת: 1000x",
    "5993b4d8": "חפש ב~HUD_COLOUR_YELLOW~חוף~s~ את המבריחים.",
    "5abea140": "איים על ה~HUD_COLOUR_RED~שופט המושחת.~s~",
    "5bd28cf4": "אסוף תיק של ~HUD_COLOUR_GREEN~דמי חסות.~s~",
    "607cc25a": "מטען באחסון:~n~- ~a~ x~1~~n~- ~a~ x~1~~n~- ~a~ x~1~~n~- ~a~ x~1~~n~- ~a~ x~1~~n~- ~a~ x~1~~n~- ~a~ x~1~",
    "62d9832f": "הקש ~INPUT_SCRIPT_RDOWN~ בזמן עם הקצב כדי לבנות אינטנסיביות~n~~INPUTGROUP_MOVE~ תנועות ריקוד~n~~INPUT_SCRIPT_RDOWN~ / ~INPUT_SCRIPT_LT~ שמור על אינטנסיביות~n~~INPUT_SCRIPT_RLEFT~ הגבר אינטנסיביות~n~~INPUT_SCRIPT_RUP~ הפחת אינטנסיביות~n~~INPUT_SCRIPT_LB~ / ~INPUT_SCRIPT_RB~ סובב~n~~INPUT_SCRIPT_RT~ בצע פעולה~n~~INPUT_SCRIPT_PAD_UP~ סגנון ריקוד: ~a~~n~~INPUT_SCRIPT_PAD_DOWN~ החלף פעולה: ~a~~n~~INPUT_SCRIPT_PAD_LEFT~ הסתר בקרים~n~~INPUT_FRONTEND_PAUSE_ALTERNATE~ הפסק לרקוד",
    "63abe3d7": "פרטי משימה:~n~גנוב כלי נשק לא מסומנים שניתן להשתמש בהם במהלך שוד קאיו פריקו~n~~n~השפעת השוד:~n~גישה לכלי הנשק הבאים:~n~- רובה ציד סער~n~- אקדח מכונה~n~- רימונים~n~- מצ'טה",
    "650c6535": "אסוף את ~HUD_COLOUR_BLUE~העוזר של מירנדה.~s~",
    "667bba6a": "אסוף את אחד ה~d~רכבים.",
    "66dde219": "יהלום 1: 2x~n~שני יהלומים: 5x~n~שלושה יהלומים: 500x~n~3 דובדבנים: 25x~n~3 שזיפים: 50x~n~3 מלונים: 75x~n~3 פעמונים: 100x~n~3 שביעיות: 250x~n~3 סטים של יהלומים: 1000x",
    "71936487": "מטען באחסון:~n~- ~a~ x~1~~n~- ~a~ x~1~~n~- ~a~ x~1~~n~- ~a~ x~1~~n~- ~a~ x~1~~n~- ~a~ x~1~~n~- ~a~ x~1~~n~- ~a~ x~1~",
    "7c688914": "לזמן מוגבל, אופנוענים, מנכ\"לים, סוחרי נשק ובעלי מועדוני לילה מקבלים:~n~~n~תשלומים כפולים (2X) עבור אתגרי מועדון אופנוענים, עבודות מועדון, חוזי בית מועדון ואתגרי חברים~n~תשלומים כפולים (2X) עבור אתגרי VIP ועבודות VIP~n~~n~ובונוסים מיוחדים לפעם הראשונה:~n~תשלום כפול (2X) עבור משימת המכירה הראשונה~n~מהירות ייצור פי 3 (3X) עבור עסקי אופנוענים וסחר בנשק, עד למשימת המכירה הראשונה~n~מהירות מחקר פי 3 (3X) עבור פריט המחקר הראשון בבונקרים של סחר בנשק~n~תשלום פי 3 (3X) עבור חוזה Ammu-Nation של סחר בנשק ומציאת מחקר לבונקר~n~תשלום פי 3 (3X) עבור ייצוא סחורות מעורבות~n~תשלום פי 3 (3X) עבור ניהול מועדון נבחר~n~תשלום פי 3 (3X) עבור השגת סחורה למועדון לילה",
    "7dad660a": "בדוק את הנכסים הבלעדיים שלנו בכתובת ~b~<u>foreclosures.maze-bank.com</u>~w~~s~. יש לנו את הנכסים הבאים זמינים לרכישה היום:~n~- האנגר שדה התעופה מקנזי~n~- מפעל בגדים~n~- משרדי ערבות~n~- מגרשי גרוטאות~n~- סדנאות רכב~n~- אולמות משחקים~n~- מועדוני לילה~n~- מתקנים~n~- האנגרים~n~- בונקרים~n~- בתי מועדון",
    "7fab0c26": "אסוף את מטעני ה-~HUD_COLOUR_GREEN~EMP.~s~",
    "81e158b5": "צביעה/מדבקה גיאומטרית לנשק Mk II",
    "88674347": "חג שמח מבית Rockstar! קיבלת את הפריטים הבאים:~n~Up-n-Atomizer~n~רכישה אחת בחינם של Vapid Clique~n~סוודר חגיגי Slasher~n~משגר זיקוקים~n~10 רקטות זיקוקים~n~25 פצצות דביקות~n~25 רימונים~n~5 מוקשי קרבה~n~5 בקבוקי מולוטוב~n~חטיפים מלאים",
    "8ceeefc0": "קנה כבד של SMG Mk II",
    "8eda8d6b": "לכוד את אחד ה~d~רכבים.",
    "8fad7c0a": "זהם את ~HUD_COLOUR_RED~חוות המריחואנה.~s~",
    "9a6abe52": "עזור למסור את כלי הנשק לנקודת ה~HUD_COLOUR_YELLOW~הורדה האחרונה.",
    "a5892190": "ה-~HUD_COLOUR_BLUE~Cheetah.",
    "d32f2be3": "ה-~HUD_COLOUR_RED~Cheetah.",
    "d9c898d9": "ה-~HUD_COLOUR_BLUE~Mamba.",
    "e06436c8": "ה-~HUD_COLOUR_RED~Mamba.",
    "b2bb8897": "עזור לקבוצה שלך לשמור על שליטה ב~d~רכבים.",
    "ee95a1cc": "הגן על ה~d~רכבים.",
    "bbd14c04": "הגע אל ה~HUD_COLOUR_YELLOW~קומה הראשונה.~s~",
    "c3960aca": "שרוד את ה~HUD_COLOUR_RED~הזיות.",
    "cc3c9848": "התחרה אל ~y~החווה של O'Neil.",
    "ddbb1450": "חפש על ~HUD_COLOUR_BLUE~איש העסקים המושחת~s~ את מפתח המעלית.",
    "e60228b2": "אסוף את ~HUD_COLOUR_GREEN~הכימיקלים המסוכנים.~s~",
    "e60ec75c": "השב את ~HUD_COLOUR_BLUE~הסחורה הגנובה.~s~",
    "e8f237fb": "עזור למסור את חלק החללית ל-~HUD_COLOUR_YELLOW~Omega.~s~",
    "fba33041": "מסור את חלק החללית ל-~HUD_COLOUR_YELLOW~Omega.~s~",
    "f1f9ced7": "פרוץ לטלפון של ה~HUD_COLOUR_BLUE~מבריח.~s~",
    "f48700eb": "עזור למסור את כלי הנשק לנקודת ה~HUD_COLOUR_YELLOW~הורדה האחרונה.~s~",
    "f768f0f4": "קח את Patrick McReary אל ה~HUD_COLOUR_YELLOW~מחבוא שלו.~s~",
    "fa876c90": "חפש ב~HUD_COLOUR_YELLOW~אתר ההתרסקות~s~ את הקופסה השחורה.",
    "e6661561": "שריון מלא מסיבי פחמן HVY Future Shock Scarab",
    "2beecfda": "מפעל מזומנים מזויפים במדבר סנורה",
    "53d3d381": "מפעל מזומנים מזויפים במדבר סנורה",
    "815aebc8": "מעבדת מת' El Burro Heights",
    "7b539e3b": "מסכה כוזבת כוכבים ופסים",
    "8df3d215": "חולצת טי eCola Pass It On",
    "1d10940a": "חתול גיאומטרי אפור ולבן",
    "2adcafa2": "חתול גיאומטרי שחור ולבן",
    "8f4f788e": "חתול גיאומטרי ג'ינג'י ולבן",
    "b323bc35": "קנה כבד של Combat MG Mk II",
    "bd85d9c0": "חלק מההפתעה של ~a~. פריט זה בחינם לצמיתות כחלק מחבילת ההתחלה של Criminal Enterprise.",
    "cf005113": "משבש נעילת טילים זמין כעת עבור הרכבים הבאים בסדנאות הרכב של הסוכנות, או בהאנגרים עבור כלי טיס:~n~~n~- Buckingham Conada~n~- Buckingham Alpha-Z1~n~- Buckingham DH-7 Iron Mule~n~- Buckingham Howard NX-25~n~- Western Cargobob~n~- Western Cargobob Jetsam~n~- Buckingham Swift Deluxe~n~- Western Dodo~n~- Buckingham Volatus~n~- Buckingham Maverick~n~- Buckingham SuperVolito~n~- Buckingham SuperVolito Carbon~n~- Buckingham Luxor Deluxe~n~- Buckingham Luxor~n~- Western Besra~n~- Karin Futo~n~- Benefactor Schafter V12~n~- Benefactor Schafter V12 (Armored)~n~- Pegassi Ignus~n~- Maibatsu Manchez~n~- Nagasaki BF400~n~- Gallivanter Baller LE LWB~n~- Ocelot Ardent~n~- Annis Elegy RH8~n~- Pegassi Vortex~n~- Lampadati Komoda~n~- Übermacht Niobe~n~- Pegassi Pizza Boy~n~- Albany Cavalcade XL~n~- Albany Roosevelt~n~- Albany Roosevelt Valor~n~- Canis Mesa~n~- BF Raptor~n~- Bravado Gauntlet~n~- Canis Bodhi~n~- Coil Brawler~n~- Dewbauchee Massacro~n~- Dewbauchee Massacro (Racecar)~n~- Grotti Cheetah~n~- LCC Hexer~n~- Pegassi Vacca~n~- Mammoth Patriot~n~- Nagasaki Blazer~n~- Vapid Bullet~n~- Vapid FMJ~n~- Vapid Peyote Gasser~n~- Western Bagger~n~- Weeny Issi~n~- Weeny Issi Sport~n~- Übermacht Sentinel~n~",
    "fe85b292": "בדוק את הנכסים הבלעדיים שלנו בכתובת ~b~<u>foreclosures.maze-bank.com</u>~w~~s~. יש לנו את הנכסים הבאים זמינים לרכישה היום:~n~- מפעל בגדים~n~- משרדי ערבות~n~- מגרשי גרוטאות~n~- סדנאות רכב~n~- אולמות משחקים~n~- מועדוני לילה~n~- מתקנים~n~- האנגרים~n~- בונקרים~n~- בתי מועדון",
    "b6b581af": "כוכב הטלה 1: 2x~n~שני כוכבי הטלה: 5x~n~שלושה כוכבי הטלה: 500x~n~3 דובדבנים: 25x~n~3 שזיפים: 50x~n~3 מלונים: 75x~n~3 פעמונים: 100x~n~3 שביעיות: 250x~n~3 גיטרות מפתח: 1000x",
    "c9e8a815": "ברק 1: 2x~n~שני ברקים: 5x~n~שלושה ברקים: 500x~n~3 דובדבנים: 25x~n~3 שזיפים: 50x~n~3 מלונים: 75x~n~3 פעמונים: 100x~n~3 שביעיות: 250x~n~3 זעם אימפוטנטי: 1000x",
    "fb6934fd": "//טעינה...~n~~n~אישור מטרה:[כלי נשק לא מסומנים]~n~......................................................................................................~n~&gt;/ציוד: צלף מומחה::~n~- רובה צלפים~n~- אקדח AP~n~- בקבוקי מולוטוב~n~- סכין~n~&lt;\\ ~n~~n~&gt;/ לאשר עבודת הכנה?",
    "ec804cf8": "//טעינה...~n~~n~אישור מטרה:[כלי נשק לא מסומנים]~n~......................................................................................................~n~&gt;/ציוד: תוקפן::~n~- רובה ציד סער~n~- אקדח מכונה~n~- רימונים~n~- מצ'טה~n~&lt;\\ ~n~~n~&gt;/ לאשר עבודת הכנה?",
    "e58f4f08": "סובב את גלגל המזל בחינם פעמיים ביום וקבל פרס.~n~~n~סיכויי זכייה:~n~רכב פודיום: 1 ל-20~n~הנחה על רכב: 1 ל-20~n~מסתורין: 1 ל-20~n~ביגוד: 4 ל-20~n~אסימונים: 4 ל-20~n~מזומן: 4 ל-20~n~RP: 5 ל-20",
    "9275fae8": "הגן על ~HUD_COLOUR_BLUE~בעלי הברית שלך.~s~"
}

def main():
    src = json.load(open(os.path.join(HERE, "to_translate.json"), encoding="utf-8"))
    he = json.load(open(os.path.join(HERE, "hebrew.json"), encoding="utf-8"))
    skip = set(json.load(open(os.path.join(HERE, "skip.json"), encoding="utf-8")))

    todo = {k: src[k] for k in src if k not in he and k not in skip}
    print(f"Loaded {len(todo)} todo keys.")

    merged_count = 0
    skipped_count = 0
    
    for k, en in todo.items():
        if k in manual_translations:
            # Validate and merge
            trans = manual_translations[k]
            if tokens(trans) != tokens(en):
                print(f"ERROR tokens mismatch for {k}:")
                print("  EN:", tokens(en))
                print("  HE:", tokens(trans))
                continue
            if has_niqqud(trans):
                print(f"ERROR niqqud found in {k}: {trans}")
                continue
            if foreign_chars(trans):
                print(f"ERROR foreign chars in {k}: {trans}")
                continue
                
            he[k] = trans
            merged_count += 1
        else:
            # Auto-skip the rest (mostly proper noun templates/links)
            skip.add(k)
            skipped_count += 1

    # Save
    with open(os.path.join(HERE, "hebrew.json"), "w", encoding="utf-8") as f:
        json.dump(he, f, ensure_ascii=False, indent=1, sort_keys=True)
    with open(os.path.join(HERE, "skip.json"), "w", encoding="utf-8") as f:
        json.dump(sorted(list(skip)), f, ensure_ascii=False, indent=1)
        
    print(f"Successfully merged {merged_count} manual translations and skipped {skipped_count} keys.")

if __name__ == "__main__":
    main()
