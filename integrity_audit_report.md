# Integrity Audit — truncation detector

**Total:** 2127 findings (base=1620, dlc=507)

## Severity counts

| severity | count |
|---|---:|
| CRITICAL | 6 |
| HIGH | 1595 |
| MEDIUM | 526 |
| LOW | 0 |

## Signals seen

| signal | count |
|---|---:|
| `CUT_MID_SENTENCE` | 1258 |
| `MISSING_TERMINAL` | 535 |
| `LENGTH_TRUNCATION` | 304 |
| `SENTENCE_COUNT_LOSS` | 45 |

## CRITICAL (6 findings — showing top 6 by source length)

### `base` · subtitles/open_world/community/e3_q110_repairing_car_chat.json · pk=1711258448356233216 · femaleVariant
- **signals:** SENTENCE_COUNT_LOSS, LENGTH_TRUNCATION
- **length:** src=118, trans=17, ratio=0.144
- **sentence count:** src=4, trans=1
- **EN source:**
```
<kiroshi l="creo" o="Ugh, ou memn tou? Non, mwen pa konnen. Li pa pi bon o pi mal. Jis diferan?" t="Ugh, you too? No,
```
- **HE current:**
```
אוג', יוא טו? נו,
```
- **fix recommendation:** Re-translate fully — source has 4 sentences but Hebrew has 1. Preserve any \n line breaks; do not exceed ~153 chars (safe buffer).

### `base` · subtitles/open_world/scenes/conversation_street_new_val_11.json · pk=2276542635807252504 · femaleVariant
- **signals:** SENTENCE_COUNT_LOSS, LENGTH_TRUNCATION
- **length:** src=104, trans=10, ratio=0.096
- **sentence count:** src=4, trans=2
- **EN source:**
```
<kiroshi l="mex" o="¡Pff! Órale, sabes que yo no lo busqué, ¿verdad? Él me buscó a mí." t="Pf! Please. 
```
- **HE current:**
```
פף! בבקשה.
```
- **fix recommendation:** Re-translate fully — source has 4 sentences but Hebrew has 2. Preserve any \n line breaks; do not exceed ~135 chars (safe buffer).

### `base` · subtitles/open_world/voicesets/gang_scv_f_03_rus_30_fat.json · pk=1898309690977804292 · femaleVariant
- **signals:** SENTENCE_COUNT_LOSS, LENGTH_TRUNCATION
- **length:** src=94, trans=21, ratio=0.223
- **sentence count:** src=4, trans=2
- **EN source:**
```
<kiroshi l="rus" o="Пх-х... кх-х... на хер иди..." t="Ekhhh…. Khhh... Fuck you..." b="" a=""/
```
- **HE current:**
```
אכhhh…. קhhh… תזדיין.
```
- **fix recommendation:** Re-translate fully — source has 4 sentences but Hebrew has 2. Preserve any \n line breaks; do not exceed ~122 chars (safe buffer).

### `base` · subtitles/open_world/voicesets/gang_tcl_m_15_jap_40_mt.json · pk=1876460779404271620 · femaleVariant
- **signals:** SENTENCE_COUNT_LOSS, LENGTH_TRUNCATION
- **length:** src=93, trans=27, ratio=0.29
- **sentence count:** src=3, trans=1
- **EN source:**
```
<kiroshi l="jpn" o="ううっ… くっ… この… 卑怯者…" t="Arggh… ekhhh.. Kkh... You... Coward..." b="" a=""/
```
- **HE current:**
```
ארגghh… אקך… קך… אתה… פחדן…
```
- **fix recommendation:** Re-translate fully — source has 3 sentences but Hebrew has 1. Preserve any \n line breaks; do not exceed ~120 chars (safe buffer).

### `base` · onscreens/onscreens.json · pk=47952 · femaleVariant
- **signals:** MISSING_TERMINAL, SENTENCE_COUNT_LOSS, LENGTH_TRUNCATION
- **length:** src=87, trans=6, ratio=0.069
- **sentence count:** src=33, trans=1
- **EN source:**
```
//ROOT\n//ACCESSING . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 
```
- **HE current:**
```
//שורש
```
- **fix recommendation:** Re-translate fully — source has 33 sentences but Hebrew has 1. Preserve any \n line breaks; do not exceed ~113 chars (safe buffer).

### `base` · subtitles/open_world/scenes/hey_spr_chat_018.json · pk=2218604652769153024 · femaleVariant
- **signals:** SENTENCE_COUNT_LOSS, LENGTH_TRUNCATION
- **length:** src=87, trans=0, ratio=0.0
- **sentence count:** src=3, trans=1
- **EN source:**
```
<kiroshi l="jpn" o="ロ・シ・ア・語・は・話せませーん" t="I. DOOON'T. SPEEEAK. RUUUSSIAAAN." b="" a=""/
```
- **HE current:**
```
<kiroshi l="jpn" o="ロ・シ・ア・語・は・話せませーん" t="אני לא מדבר רוסית." b="" a=""/>
```
- **fix recommendation:** Re-translate fully — source has 3 sentences but Hebrew has 1. Preserve any \n line breaks; do not exceed ~113 chars (safe buffer).


## HIGH (1595 findings — showing top 50 by source length)

### `dlc` · ep1/onscreens/onscreens.json · pk=85425 · femaleVariant
- **signals:** MISSING_TERMINAL, SENTENCE_COUNT_LOSS
- **length:** src=3669, trans=1174, ratio=0.32
- **sentence count:** src=36, trans=14
- **EN source:**
```
You in Night City? Seen all highlights: Corpo Plaza, North Oak, Japantown, even the Trauma Hospital and other places the NC authorities can be proud of? Then it's now time for Dogtown, the part of Night City that those in power would like to forget... if they could.\nStart with my guide to NC to get a good taste of what awaits you beyond the gates to Dogtown - if Pacifica, Heywood or Santo Domingo
```
- **HE current:**
```
אתה בנייט סיטי? ראית את כל הנקודות החמות: כיכר הקורפו, נורת' אוק, יפן טאון, אפילו בית חולים לטראומה וכל השאר שהרשויות של נייט סיטי גאות בהם? אז הגיע הזמן לדוג'טאון, החלק בנייט סיטי שאלה ששלטונות היו רוצים לשכוח ממנו... אם רק יכלו.

התחל עם המדריך שלי לנייט סיטי כדי לקבל טעימה מהממתין לך מעבר לשערים של דוג'טאון - אם פאסיפיקה, הייווד או סנטו דומינגו לא יסיימו אותך ואת במצב רוח ליותר מזה, יש לי סיור 
```
- **fix recommendation:** Re-translate — LM dropped sentences. Send src in two halves (split on a newline or sentence boundary) and join, so the model sees the full thought.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=85425 · femaleVariant
- **signals:** MISSING_TERMINAL, SENTENCE_COUNT_LOSS
- **length:** src=3669, trans=1172, ratio=0.319
- **sentence count:** src=36, trans=14
- **EN source:**
```
You in Night City? Seen all highlights: Corpo Plaza, North Oak, Japantown, even the Trauma Hospital and other places the NC authorities can be proud of? Then it's now time for Dogtown, the part of Night City that those in power would like to forget... if they could.\nStart with my guide to NC to get a good taste of what awaits you beyond the gates to Dogtown - if Pacifica, Heywood or Santo Domingo
```
- **HE current:**
```
אתה בנייט סיטי? ראית את כל הנקודות החמות: פלאזה קורפו, נורת' אוק, יפ ntown, אפילו בית חולים לטראומה וכל המקומות שאנשי רשויות נייט סיטי גאים בהם? אז הגיע הזמן לדוגטאון, החלק בנייט סיטי שהשלטונות היו רוצים לשכוח ממנו... אם רק יכלו.

התחל עם המדריך שלי לנייט סיטי כדי לקבל טעימה טובה ממה שמחכה לך מעבר לשערים של דוגטאון - אם פאסיפיקה, הייווד או סנטו דומינגו לא יסיימו אותך ואת במצב רוח למעוד, יש לי סיור
```
- **fix recommendation:** Re-translate — LM dropped sentences. Send src in two halves (split on a newline or sentence boundary) and join, so the model sees the full thought.

### `dlc` · ep1/onscreens/onscreens.json · pk=85443 · femaleVariant
- **signals:** SENTENCE_COUNT_LOSS
- **length:** src=3519, trans=1278, ratio=0.363
- **sentence count:** src=52, trans=19
- **EN source:**
```
asdfghjkl!!!1! thank u chooms for all the luv and comments! I luv u alllll!!!!! <333 And to all my haters..... free tip --- just stop reading! ;) k thx XD\n\nEDIT: OMG I SHOWED KERRY MY STORY AFTER THE CONCERT AND HE SAID IT WAS PREEEEEM!!!!  IM CRYINGGGG. I CAN DIE HAPPY\n***\n\nOur heros:\n\nJohnny SIlverhand - long black hair, tall, can be jerk (but he's soooo cute when hes mad <333), dark sung
```
- **HE current:**
```
asdfghjkl!!!1! תודה לצ'ומים על כל האהבה והתגובות! אני אוהב אתכם כולם!!!!! <333 ולכל השונאים שלי..... טיפ חינם --- פשוט הפסיקו לקרוא! ;) k thx XD\n\n עריכה: OMG הראיתי ל akerry את הסיפור שלי אחרי ההופעה והוא אמר שזה היה PREEEEEM!!!! אני בוכה!!!! אני יכול למות בשקט\n***\n\n הגיבורים שלנו:\n\n ג'וני סילברהנד - שיער שחור ארוך, גבוה, יכול להיות פריק (אבל הוא כל כך חמוד כשהוא כועס <333), משקפי שמש כהים 
```
- **fix recommendation:** Re-translate — LM dropped sentences. Send src in two halves (split on a newline or sentence boundary) and join, so the model sees the full thought.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=85443 · femaleVariant
- **signals:** SENTENCE_COUNT_LOSS
- **length:** src=3519, trans=1256, ratio=0.357
- **sentence count:** src=52, trans=19
- **EN source:**
```
asdfghjkl!!!1! thank u chooms for all the luv and comments! I luv u alllll!!!!! <333 And to all my haters..... free tip --- just stop reading! ;) k thx XD\n\nEDIT: OMG I SHOWED KERRY MY STORY AFTER THE CONCERT AND HE SAID IT WAS PREEEEEM!!!!  IM CRYINGGGG. I CAN DIE HAPPY\n***\n\nOur heros:\n\nJohnny SIlverhand - long black hair, tall, can be jerk (but he's soooo cute when hes mad <333), dark sung
```
- **HE current:**
```
asdfghjkl!!!1! תודה לצ'ומים על כל האהבה והתגובות! אני אוהב אתכם כולם!!!!! <333 ולכל השונאים שלי..... טיפ חינם --- פשוט הפסיקו לקרוא! ;) k thx XD\n\n עריכה: OMG הראיתי לקרי שלי את הסיפור אחרי ההופעה והוא אמר שזה היה PREEEEEM!!!! אני בוכה!!!! אני יכול למות בשקט\n***\n\n הגיבורים שלנו:\n\n ג'וני סילברהנד - שיער שחור ארוך, גבוה, יכול להיות פריק (אבל הוא כל כך חמוד כשהוא כועס <333), משקפי שמש כהים (כדי
```
- **fix recommendation:** Re-translate — LM dropped sentences. Send src in two halves (split on a newline or sentence boundary) and join, so the model sees the full thought.

### `dlc` · ep1/onscreens/onscreens.json · pk=85432 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=2160, trans=1203, ratio=0.557
- **sentence count:** src=12, trans=9
- **EN source:**
```
After 3 weeks of observation, I can safely say BARGHEST recruitment is conducted in an entirely voluntary manner across the entire district of Dogtown. No combat experience is required, but all new recruits are required to undergo mandatory monthly endurance and weapons training, conducted by seasoned military veterans. Since this introduction has clear markings of an army boot camp, most recruits
```
- **HE current:**
```
אחרי 3 שבועות של תצפית, אני יכול לומר בביטחון שגיוס לברגסט מתבצע באופן וולונטרי לחלוטין בכל רחבי מחוז דוגטאון. אין צורך בניסיון קרב, אבל כל המתגייסים החדשים נדרשים לעבור אימוני סיבולת ונשק חודשיים חובה, הנערכים על ידי ותיקי צבא. מכיוון שההקדמה הזאת נושאת סימנים ברורים של מחנה אימונים צבאי, רוב המתגייסים מוכנים טוב יותר למלחמת ערים מאשר חברי כנופיות רגילים בנייט סיטי.

מתגייסים אלה לומדים גם משמעת,
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=85432 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=2160, trans=1195, ratio=0.553
- **sentence count:** src=12, trans=9
- **EN source:**
```
After 3 weeks of observation, I can safely say BARGHEST recruitment is conducted in an entirely voluntary manner across the entire district of Dogtown. No combat experience is required, but all new recruits are required to undergo mandatory monthly endurance and weapons training, conducted by seasoned military veterans. Since this introduction has clear markings of an army boot camp, most recruits
```
- **HE current:**
```
אחרי 3 שבועות של תצפית, אני יכול לומר בבטחה שגיוס לברגסט מתבצע באופן התנדבותי לחלוטין בכל רחבי מחוז דוגטאון. לא נדרשת ניסיון קרב, אך כל המגויסים החדשים חייבים לעבור אימוני סיבולת ונשק חודשיים חובה, הנערכים על ידי ותיקי צבא. מכיוון שההקדמה הזו נושאת סימנים ברורים של מחנה אימונים צבאי, רוב המגויסים מוכנים טוב יותר למלחמת עירונית מאשר חברי כנופיות רגילים בנייט סיטי.

המגויסים הללו לומדים גם משמעת, מה
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=92244 · femaleVariant
- **signals:** CUT_MID_SENTENCE, MISSING_TERMINAL
- **length:** src=1978, trans=1183, ratio=0.598
- **sentence count:** src=30, trans=28
- **EN source:**
```
First it’s nothing but a bright future spread out shining before you: “You’re a once-in-a-generation talent! Amazing! Just sign on the dotted line, and we’ll turn you into the best boxer on the West Coast!” And then suddenly you’re out on the street with a second-place trophy. Worthless silver.\n\nFiona promised the moon to me and my parents, and they believed her. They signed the contract and pac
```
- **HE current:**
```
העתיד נוצץ לפנייך, כמו כוכבים בשמיים: "את כישרון נדיר! מדהימה! רק חתמי על הקו, ואנחנו נ biến אתך לאלופת אגרוף בחוף המערבי!" ואז פתאום אתה מוצא את עצמך ברחוב עם גביע של מקום שני. כסף חסר ערך.

פימונה הבטיחה ללי ולורידי הירח, והם האמינו לה. הם חתמו על החוזה וארזו את בתם בת ה-11 למרכז. לא התגעגעתי אליהם.

במרכז דחפו בי כדורים וכרום שהפכו אותי למין אל כל יכול. הייתי בגן עדן. היי, 24/7. הייתי הכי יפה, 
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens.json · pk=88093 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=1239, trans=994, ratio=0.802
- **sentence count:** src=14, trans=19
- **EN source:**
```
Manuel, the truth is that what we're doing here is illegal in every way. We have to conceal this project from the competition - that much is obvious, but more importantly so that NetWatch doesn't catch our scent. That's a little more complicated. I need the best algorithms your team's got - we have to update this ICE every few minutes. What about that permutational code you promised us? We also ne
```
- **HE current:**
```
מנואל, האמת היא שמה שאנחנו עושים כאן בלתי חוקי בכל דרך. אנחנו חייבים להסתיר את הפרויקט הזה מהתחרות - זה ברור מאליו, אבל חשוב יותר מכל כך שלא נטווטש תריח אותנו. זה קצת יותר מסובך. אני צריך את האלגוריתמים הטובים ביותר שיש לצוות שלך - אנחנו חייבים לעדכן את ה-ICE הזה כל כמה דקות. מה עם הקוד הפרומוטציונלי שהבטח לנו? אנחנו גם צריכים מסך עשן מסורתי יותר - אולי המודיעין שלנו יכול להסית איזה שהוא סוג של פר
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=88093 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=1239, trans=995, ratio=0.803
- **sentence count:** src=14, trans=19
- **EN source:**
```
Manuel, the truth is that what we're doing here is illegal in every way. We have to conceal this project from the competition - that much is obvious, but more importantly so that NetWatch doesn't catch our scent. That's a little more complicated. I need the best algorithms your team's got - we have to update this ICE every few minutes. What about that permutational code you promised us? We also ne
```
- **HE current:**
```
מנואל, האמת היא שאנחנו עושים פה משהו לא חוקי בכל מובן. אנחנו חייבים להסתיר את הפרויקט הזה מהתחרות - זה ברור מאליו, אבל חשוב יותר שנטוואץ לא יריחו אותנו. זה קצת יותר מסובך. אני צריך את האלגוריתמים הכי טובים שיש לצוות שלך - אנחנו צריכים לעדכן את ה-ICE הזה כל כמה דקות. מה עם הקוד הפרומוטציונלי שהבטח לנו? אנחנו גם צריכים מסך עשן מסורתי יותר - אולי המודיעין שלנו יכול להמריץ איזה שהוא סוג של פרובוקציה ש
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens.json · pk=87180 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=1033, trans=683, ratio=0.661
- **sentence count:** src=4, trans=6
- **EN source:**
```
PLEASE NOTE!\n\nFormer marketplace vendors are barred from entering the Night Corporation Complex construction site. With the investment plan approved by the Night City Council, no pickets, demonstrations or other displays of public disapproval will sway the Company's Board from altering its decision. Any instigators of protests or protestors apprehended while trespassing on land belonging to the 
```
- **HE current:**
```
שים לב!

לבעלי הדוכנים לשעבר אסור להיכנס לאתר הבנייה של מתחם נייט קורפוריישן. עם אישור תוכנית ההשקעה על ידי מועצת נייט סיטי, אין פיקטים, הפגנות או דרכים אחרות להבעת אי הסכמה ציבורית שיגרמו לדירקטוריון החברה לשנות את החלטתו. כל מי שיוזם מחאות או מפגינים שנלכדים בזמן שהם חודרים לשטח השייך לחברה יועמדו לדין פלילי. הדברים הבאים ייחשבו למעשי הסתה או מחאה:

-שהייה בשטח השוק ללא רשות;
-ניסיון להמשיך בפעי
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=87180 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=1033, trans=683, ratio=0.661
- **sentence count:** src=4, trans=6
- **EN source:**
```
PLEASE NOTE!\n\nFormer marketplace vendors are barred from entering the Night Corporation Complex construction site. With the investment plan approved by the Night City Council, no pickets, demonstrations or other displays of public disapproval will sway the Company's Board from altering its decision. Any instigators of protests or protestors apprehended while trespassing on land belonging to the 
```
- **HE current:**
```
שים לב!

לבעלי הדוכנים לשעבר אסור להיכנס לאתר הבנייה של מתחם נייט קורפוריישן. עם אישור תוכנית ההשקעה על ידי מועצת נייט סיטי, אין פיקטים, הפגנות או תצוגות אחרות של אי-אישור ציבורי שיכנעו את דירקטוריון החברה לשנות את החלטתה. כל מי שיוזם מחאות או מפגינים שנעצרו בזמן שהם חודרים לשטח השייך לחברה יועמד לדין פלילי. הדברים הבאים ייחשבו למעשי הסתה או מחאה:

-שהייה בשטח השוק ללא רשות;
-ניסיון להמשיך בפעילות
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens.json · pk=85445 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=866, trans=723, ratio=0.835
- **sentence count:** src=5, trans=7
- **EN source:**
```
ARTHUR "CORMAC" CORMAC\n\nCurrent Role: Fixer\n\nAge: 41\n\nOperates in: Wellsprings, Glen, Santo Domingo, Watson (occasionally)\nKnown Associates: El Sombreron, Dutch, Wesley Simms, Jago Szabó, Kiki, Myst Errya de Mort\n\nKnown Sources: Roork, Kyle J., Brisa, Dutch, The Foreman, Cholo, Kiki, The Grebe\n\nProfile: Cooperates with a number of Night City fixers, carrying out one-off contracts within
```
- **HE current:**
```
ארתור "קורמק" קורמק

תפקיד נוכחי: פיקסר

גיל: 41

אזור פעילות: וולספרינגס, גלין, סנטו דומינגו, ווטסון (מאוד לעיתים רחוקות)
שותפים ידועים: אל סומבררון, הולנדי, וסלי סימס, יאגו Szabó, קיקי, מיסט אריה דה מורט

מקורות מידע ידועים: רורק, קייל ג'., בריזה, הולנדי, מנהל העבודות, צ'ולו, קיקי, הגרבי

פרופיל: משתף פעולה עם מספר פיקסרים בנייט סיטי, מבצע חוזים חד-פעמיים בתחומי השיפוט שלהם. אוהב לפעול לבד ולהשל
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=85445 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=866, trans=717, ratio=0.828
- **sentence count:** src=5, trans=7
- **EN source:**
```
ARTHUR "CORMAC" CORMAC\n\nCurrent Role: Fixer\n\nAge: 41\n\nOperates in: Wellsprings, Glen, Santo Domingo, Watson (occasionally)\nKnown Associates: El Sombreron, Dutch, Wesley Simms, Jago Szabó, Kiki, Myst Errya de Mort\n\nKnown Sources: Roork, Kyle J., Brisa, Dutch, The Foreman, Cholo, Kiki, The Grebe\n\nProfile: Cooperates with a number of Night City fixers, carrying out one-off contracts within
```
- **HE current:**
```
ארתור "קורמק" קורמק

תפקיד נוכחי: פיקסר

גיל: 41

אזור פעילות: וולספרינגס, גלין, סנטו דומינגו, ווטסון (לפעמים)

שותפים ידועים: אל סומברונרון, הולנדי, וסלי סימס, יאגו Szabó, קיקי, מיסט ארויה דה מורט

מקורות מידע ידועים: רורק, קייל ג'., בריזה, הולנדי, הפורמן, צ'ולו, קיקי, הגרייב

פרופיל: משתף פעולה עם מספר פיקסרים בנייט סיטי, מבצע חוזים חד-פעמיים בתחומי פעילותם. אוהב לפעול לבד ולהשלים משימות באופן א
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens.json · pk=83055 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=790, trans=637, ratio=0.806
- **sentence count:** src=11, trans=25
- **EN source:**
```
Hey, so is it true we're saying goodbye to Africa? Arasaka's taken over the deposits there.\nSteve\n---------------\nFrom: Wanda L.\nTo: Steve A.\nre: we lost africa?\nI'm trying to figure it out. People are telling me different things. We're so cut off here that even corp news comes with a delay. I'll keep you posted.\nW.\n---------------\nFrom: Steve A.\nTo: Wanda L.\nre: we lost africa?\nBut if
```
- **HE current:**
```
היי, אז זה נכון שאנחנו מתפנים מאפריקה? אראסאקה השתלטו על המכרות שם.
סטיב
---------------
מ: ונדה ל.
ל: סטיב א.
עניין: איבדנו את אפריקה?
אני מנסה להבין. אנשים מספרים לי דברים שונים. אנחנו כל כך מבודדים פה שגם חדשות של תאגיד מגיעות עם עיכוב. אעדכן אותך.
ו.
---------------
מ: סטיב א.
ל: ונדה ל.
עניין: איבדנו את אפריקה?
אבל אם איבדנו, אז מה יקרה לפרויקט? אנחנו תלויים במכרות שם. ההנהלה תקבור את המחקר ש
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=83055 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=790, trans=624, ratio=0.79
- **sentence count:** src=11, trans=25
- **EN source:**
```
Hey, so is it true we're saying goodbye to Africa? Arasaka's taken over the deposits there.\nSteve\n---------------\nFrom: Wanda L.\nTo: Steve A.\nre: we lost africa?\nI'm trying to figure it out. People are telling me different things. We're so cut off here that even corp news comes with a delay. I'll keep you posted.\nW.\n---------------\nFrom: Steve A.\nTo: Wanda L.\nre: we lost africa?\nBut if
```
- **HE current:**
```
היי, אז זה נכון שאנחנו מתפנים מאפריקה? אראסאקה השתלטו על המכרות שם.
סטיב
---------------
מ: ונדה ל.
ל: סטיב א.
עניין: איבדנו את אפריקה?
אני מנסה להבין. אנשים מספרים לי דברים שונים. אנחנו כל כך מבודדים פה שגם חדשות של תאגיד מגיעות עם עיכוב. אשמור אותך מעודכן.
ו.
---------------
מ: סטיב א.
ל: ונדה ל.
עניין: איבדנו את אפריקה?
אבל אם איבדנו, אז מה יקרה לפרויקט? אנחנו תלויים במכרות שם. ההנהלה תקבור את 
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens.json · pk=87001 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=709, trans=546, ratio=0.77
- **sentence count:** src=5, trans=5
- **EN source:**
```
Chapter 2: Present day\n\nAccording to the 2075 census, Tycho's residents number 40,000 and is one of Luna's two thriving cities (the other being Copernicus with a population of approx. 18,000). The transport of minerals from Tycho to Earth as well as Crystal Palace is possible thanks to Mass Drivers (two on Tycho, one on Copernicus). In 2008 during the six-hour-long First Orbital War, a moon rock
```
- **HE current:**
```
פרק 2: הווה

לפי מפקד האוכלוסין לשנת 2075, לתושבי טיכו ישנם 40,000 תושבים והוא אחד משתי הערים המפיצות של לונה (השנייה היא קופרניקוס עם אוכלוסייה של כ-18,000). שינוע מינרלים מטיכו לכדור הארץ כמו גם לארמון הקריסטל אפשרי בזכות מדחפי מסה (שניים בטיכו, אחד בקופרניקוס). בשנת 2008 במהלך מלחמת המסלול הראשונה בת שש השעות, סלע ירח במשקל שתי טונות התנגש בקולורדו ספרינגס, שוגר ממדחף מסה בטיכו. הנפגעים כללו את
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=87001 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=709, trans=547, ratio=0.772
- **sentence count:** src=5, trans=5
- **EN source:**
```
Chapter 2: Present day\n\nAccording to the 2075 census, Tycho's residents number 40,000 and is one of Luna's two thriving cities (the other being Copernicus with a population of approx. 18,000). The transport of minerals from Tycho to Earth as well as Crystal Palace is possible thanks to Mass Drivers (two on Tycho, one on Copernicus). In 2008 during the six-hour-long First Orbital War, a moon rock
```
- **HE current:**
```
פרק 2: ימינו אלה

לפי מפקד האוכלוסין לשנת 2075, לתושבי טיכו ישנם 40,000 תושבים והוא אחד משני ערי הלונה המפיצות (השני הוא קופרניקוס עם אוכלוסייה של כ-18,000). הסעת מינרלים מטיכו לכדור הארץ כמו גם לארמון הקריסטל אפשרית בזכות מדחפי מסה (שניים בטיכו, אחד בקופרניקוס). בשנת 2008 במהלך מלחמת המסלול הראשונה בת שש שעות, סלע ירח במשקל שתי טונות התנגש בקולורדו ספרינגס, שוגר ממכונת הדחף בטיכו. הנפגעים כללו את
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens.json · pk=85202 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=700, trans=515, ratio=0.736
- **sentence count:** src=5, trans=6
- **EN source:**
```
Chapter 1: History\n\nTycho was founded in 1997 by the European Space Council. The moon was an obvious location for a number of reasons: the presence of gravity and the naturally soft terrain facilitated the construction of the first human settlement in space. By 2020, most of Tycho's infrastructure had been moved beneath the surface. A vast network of caves and tunnels were dug using nuclear pump
```
- **HE current:**
```
פרק 1: היסטוריה

טייכו נוסדה בשנת 1997 על ידי מועצת החלל האירופית. הירח היה מיקום ברור למספר סיבות: נוכחות כוח המשיכה והשטח הרך באופן טבעי הקלו על בניית היישוב האנושי הראשון בחלל. עד שנת 2020, רוב התשתית של טייכו הועברה מתחת לפני השטח. רשת נרחבת של מערות ומנהרות נחצבה באמצעות לייזרים המופעלים בכוח גרעיני, בעוד התקרה חוזקה בשכבות של חול ירחי. שמורות צמחים ירוקים ממלאות עד היום את המערות המרווחות, ש
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=85202 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=700, trans=516, ratio=0.737
- **sentence count:** src=5, trans=6
- **EN source:**
```
Chapter 1: History\n\nTycho was founded in 1997 by the European Space Council. The moon was an obvious location for a number of reasons: the presence of gravity and the naturally soft terrain facilitated the construction of the first human settlement in space. By 2020, most of Tycho's infrastructure had been moved beneath the surface. A vast network of caves and tunnels were dug using nuclear pump
```
- **HE current:**
```
פרק 1: היסטוריה

טייכו נוסדה בשנת 1997 על ידי מועצת החלל האירופית. הירח היה מיקום ברור למספר סיבות: נוכחות כוח המשיכה והשטח הרך באופן טבעי הקלו על בניית ההתנחלות האנושית הראשונה בחלל. עד שנת 2020, רוב התשתית של טייכו הועברה מתחת לפני השטח. רשת נרחבת של מערות ומנהרות נחצבה באמצעות לייזרים המונעים בגרעין, בעוד תקרתן חוזקה בשכבות של חול ירחי. שמורות צמחים ירוקים ממלאות עד היום את המערות המרווחות, אשר
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `dlc` · ep1/onscreens/onscreens.json · pk=82916 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=369, trans=276, ratio=0.748
- **sentence count:** src=7, trans=7
- **EN source:**
```
For now, leave the machine be. Hansen got an offer from some general somewhere who sees potential in that heap of junk. Gist is - we're probably gonna sell. Meeting's scheduled for next week but until the decision to sell is final, don't go poking around the cables!! If you break it, you pay to match the general's offer. Tl;dr - don't touch, don't fix. WE SELL AS IS.
```
- **HE current:**
```
לעת עתה, תן למכונה להיות. הנסן קיבל הצעה מאיפשהו מגנרל שרואה פוטנציאל בגרוטאה הזאת. העיקר הוא - כנראה שנמכור. יש פגישה בשבוע הבא אבל עד שההחלטה למכירה תהיה סופית, אל תתעסק בכבלים!! אם אתה משבור אותה, אתה משלם כדי להתאים להצעה של הגנרל. קיצר - לא לגעת, לא לתקן. NEM SELL AS IS.
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens_final.json · pk=88093 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=177, trans=991, ratio=5.599
- **sentence count:** src=1, trans=19
- **EN source:**
```
Story-ep1-journal-onscreens-emails-quests-main_quests-q305-bunker_emails-cynosure_device_specific_emails-q305_hiding_from_netwatch_emails-Q305_hiding_from_netwatch_email_content
```
- **HE current:**
```
מנואל, האמת היא שאנחנו עושים פה משהו בלתי חוקי בכל דרך אפשרית. אנחנו חייבים להסתיר את הפרויקט הזה מהתחרות - זה ברור מאליו, אבל חשוב יותר שנטוואץ לא יריחו אותנו. זה קצת יותר מסובך. אני צריך את האלגוריתמים הכי טובים שיש לצוות שלך - אנחנו צריכים לעדכן את ה-ICE הזה כל כמה דקות. מה עם הקוד הפרומוטציונלי שהבטח לנו? אנחנו גם צריכים מסך עשן מסורתי יותר - אולי המודיעין שלנו יכול להמריץ איזשהי פרוווקציה שתג
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens.json · pk=7065 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=127, trans=77, ratio=0.606
- **sentence count:** src=1, trans=1
- **EN source:**
```
In the twentieth century, it was widely believed that the Japanese yen would become the world's predominant currency (though s
```
- **HE current:**
```
במאה העשרים האמינו רבים כי הין היפני יהפוך למטבע הדומיננטי בעולם (אף על פי ש-
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens.json · pk=43084 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=127, trans=112, ratio=0.882
- **sentence count:** src=1, trans=1
- **EN source:**
```
We hereby order you to call off this illegal strike.\nYour boss Michael Katic has engaged the cooperation of Militech to aid i
```
- **HE current:**
```
אנו מצווים עליך בזאת לבטל את השביתה הלא חוקית הזאת. הבוס שלך מייקל קטיק גייס את שיתוף הפעולה של מיליטים לעזרה ב-
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens.json · pk=50124 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=127, trans=93, ratio=0.732
- **sentence count:** src=1, trans=1
- **EN source:**
```
The scene opens with a close-up on KENNY and LINH posing for wedding pictures by a seaside cafe (sign and logo visible in the 
```
- **HE current:**
```
הסצנה נפתחת בזום על קני ולין שמצטלמים לתמונות חתונה ליד בית קפה לחוף הים (שלט ולוגו גלויים ב-
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens.json · pk=95338 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=127, trans=91, ratio=0.717
- **sentence count:** src=2, trans=2
- **EN source:**
```
Live fast and die young? Must be strivin' for that first thing, 'cause you already got the second in the bag. If you intend to
```
- **HE current:**
```
לחיות מהר ולמות צעיר? בטח שואף לזה הדבר הראשון, כי את השני כבר יש לך בכיס. אם אתה מתכוון ל-
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens_final.json · pk=7065 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=127, trans=75, ratio=0.591
- **sentence count:** src=1, trans=1
- **EN source:**
```
In the twentieth century, it was widely believed that the Japanese yen would become the world's predominant currency (though s
```
- **HE current:**
```
במאה ה-20, האמינו רבים כי הין היפני יהפוך למטבע הדומיננטי בעולם (אף על פי ש
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens_final.json · pk=43084 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=127, trans=111, ratio=0.874
- **sentence count:** src=1, trans=1
- **EN source:**
```
We hereby order you to call off this illegal strike.\nYour boss Michael Katic has engaged the cooperation of Militech to aid i
```
- **HE current:**
```
אנו מצווים עליך לבטל את השביתה הבלתי חוקית הזאת. הבוס שלך, מייקל קטיק, גייס את שיתוף הפעולה של מיליטים לעזרה ב-
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens_final.json · pk=50124 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=127, trans=93, ratio=0.732
- **sentence count:** src=1, trans=1
- **EN source:**
```
The scene opens with a close-up on KENNY and LINH posing for wedding pictures by a seaside cafe (sign and logo visible in the 
```
- **HE current:**
```
הסצנה נפתחת בזום על קני ולין שמצטלמים לתמונות חתונה ליד בית קפה לחוף הים (שלט ולוגו גלויים ב-
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens_final.json · pk=95338 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=127, trans=91, ratio=0.717
- **sentence count:** src=2, trans=2
- **EN source:**
```
Live fast and die young? Must be strivin' for that first thing, 'cause you already got the second in the bag. If you intend to
```
- **HE current:**
```
לחיות מהר ולמות צעיר? בטח שואף לזה הדבר הראשון, כי את השני כבר יש לך בכיס. אם אתה מתכוון ל-
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · subtitles/open_world/scenes/wat_lch_chat_025.json · pk=2172328057220349952 · femaleVariant
- **signals:** LENGTH_TRUNCATION
- **length:** src=127, trans=0, ratio=0.0
- **sentence count:** src=2, trans=1
- **EN source:**
```
<kiroshi l="mex" o="Mejor que sean cuatro para... esto y aquello..." t="Make it four for... Somethin' something..." b="" a=""/
```
- **HE current:**
```
<kiroshi l="mex" o="Mejor que sean cuatro para... esto y aquello..." t="תעשה את זה ארבע פעמים בשביל... משהו משהו..." b="" a=""/>
```
- **fix recommendation:** Re-translate fully — source has 2 sentences but Hebrew has 1. Preserve any \n line breaks; do not exceed ~165 chars (safe buffer).

### `base` · onscreens/onscreens.json · pk=90891 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=126, trans=7, ratio=0.056
- **sentence count:** src=1, trans=1
- **EN source:**
```
Story-ep1-gameplay-static_data-database-scanning-sandbox_activities-sa_ep1_cyberjunkie_clues-cbj_ep1_06_drugs_02_localizedName
```
- **HE current:**
```
מיוצר ב
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens_final.json · pk=90891 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=126, trans=7, ratio=0.056
- **sentence count:** src=1, trans=1
- **EN source:**
```
Story-ep1-gameplay-static_data-database-scanning-sandbox_activities-sa_ep1_cyberjunkie_clues-cbj_ep1_06_drugs_02_localizedName
```
- **HE current:**
```
מיוצר ב
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · subtitles/open_world/voicesets/civ_low_m_112_car_30_big_mt.json · pk=1922943046590668804 · femaleVariant
- **signals:** LENGTH_TRUNCATION
- **length:** src=126, trans=0, ratio=0.0
- **sentence count:** src=2, trans=1
- **EN source:**
```
<kiroshi l="creo" o="Mwen pa vle gen pwoblèm. Ou menm tou ou pa vle sa." t="I don't want trouble. Neither do you." b="" a=""/
```
- **HE current:**
```
<kiroshi l="creo" o="Mwen pa vle gen pwoblèm. Ou menm tou ou pa vle sa." t="אני לא רוצה צרות. גם אתה לא." b="" a=""/>
```
- **fix recommendation:** Re-translate fully — source has 2 sentences but Hebrew has 1. Preserve any \n line breaks; do not exceed ~163 chars (safe buffer).

### `base` · subtitles/quest/q112/q112_07a_parade_gameplay_and_combat_routines.json · pk=1876490251669618688 · femaleVariant
- **signals:** LENGTH_TRUNCATION
- **length:** src=126, trans=0, ratio=0.0
- **sentence count:** src=2, trans=1
- **EN source:**
```
<mothertongue l="mex" m="ese" b="Aww, c'mon, " a=". It's beautiful! Not often you get to see a whole bag full of eye candy."/
```
- **HE current:**
```
<mothertongue l="mex" m="ese" b="יאללה, תן כבר" a="יפה! לא כל יום רואים תיק שלם מלא בממתקים לעיניים."/>
```
- **fix recommendation:** Re-translate fully — source has 2 sentences but Hebrew has 1. Preserve any \n line breaks; do not exceed ~163 chars (safe buffer).

### `base` · subtitles/quest/q114/q114_09_convoy.json · pk=1887819298817830912 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=126, trans=94, ratio=0.746
- **sentence count:** src=3, trans=3
- **EN source:**
```
And then - boom! A pack of Raffens raided the construction site. Half of our people didn't make it out alive. You think that�
```
- **HE current:**
```
ואז - בום! חבורה של ראפנים תקפה את אתר הבנייה. חצי מהאנשים שלנו לא יצאו משם בחיים. אתה חושב ש…
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens.json · pk=79869 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=125, trans=78, ratio=0.624
- **sentence count:** src=2, trans=2
- **EN source:**
```
The Villefort Cortes V5000 Valor represents the very soul of American engineering. Impressive and dignified. A kid from a we
```
- **HE current:**
```
וילפורט קורטס V5000 ולור מייצג את נשמת ההנדסה האמריקאית. מרשים ועוצמתי. ילד מ-
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens.json · pk=79905 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=125, trans=92, ratio=0.736
- **sentence count:** src=1, trans=1
- **EN source:**
```
This Rayfield Aerondight "Guinevere" belonged to the ambassador of Argentina... that is, until the country returned to marti
```
- **HE current:**
```
רכב רייפילד ארונדיגט "גווינביר" הזה השתייך לשגריר ארגנטינה... כלומר, עד שהמדינה חזרה למצב של
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens_final.json · pk=79869 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=125, trans=78, ratio=0.624
- **sentence count:** src=2, trans=2
- **EN source:**
```
The Villefort Cortes V5000 Valor represents the very soul of American engineering. Impressive and dignified. A kid from a we
```
- **HE current:**
```
וילפורט קורטס V5000 ולור מייצג את נשמת ההנדסה האמריקאית. מרשים ועוצמתי. ילד מ-
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens_final.json · pk=79905 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=125, trans=92, ratio=0.736
- **sentence count:** src=1, trans=1
- **EN source:**
```
This Rayfield Aerondight "Guinevere" belonged to the ambassador of Argentina... that is, until the country returned to marti
```
- **HE current:**
```
רכב רייפילד ארונדיגט "גווינביר" הזה השתייך לשגריר ארגנטינה... כלומר, עד שהמדינה חזרה למצב של
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · subtitles/quest/q003/q003_01b_meat_factory.json · pk=1755949900726464512 · femaleVariant
- **signals:** LENGTH_TRUNCATION
- **length:** src=125, trans=0, ratio=0.0
- **sentence count:** src=2, trans=1
- **EN source:**
```
<mothertongue l="mex" m="Santa Madre" b="Take the Valentinos. They follow God and the " a=". Honor means something to 'em."/
```
- **HE current:**
```
<mothertongue l="mex" m="Santa Madre" b="תופסים את הוולנטינוז. הם הולכים על פי האל וה" a="כבוד משהו בשבילם."/>
```
- **fix recommendation:** Re-translate fully — source has 2 sentences but Hebrew has 1. Preserve any \n line breaks; do not exceed ~162 chars (safe buffer).

### `base` · onscreens/onscreens.json · pk=50152 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=124, trans=94, ratio=0.758
- **sentence count:** src=1, trans=2
- **EN source:**
```
Just when you think you've solved your problem, your solution goes and starts making fucking demands. Looks like Panam'll o
```
- **HE current:**
```
בדיוק כשאתה חושב שפתחת את הבעיה שלך, הפתרון הולך ומתחיל לדרוש דברים ***! נראה שפנאם תצטרך ל...
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens.json · pk=79552 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=124, trans=85, ratio=0.685
- **sentence count:** src=2, trans=2
- **EN source:**
```
V, got a fight at a construction site. Dude responsible is heavily ironed – heard something about lasers. If you manage to 
```
- **HE current:**
```
וי, יש קטטה באתר בנייה. האיש שאחראי כבד מאוד - שמעתי משהו על לייזרים. אם אתה מצליח ל-
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens.json · pk=79651 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=124, trans=92, ratio=0.742
- **sentence count:** src=3, trans=3
- **EN source:**
```
Was I speaking in tongues, V? I said no blood, not among civs. They've suffered enough. Although the end can justify the me
```
- **HE current:**
```
האם דיברתי בלשונות, V? אמרתי בלי דם, לא בין אזרחים. הם סבלו מספיק. אם כי הסוף יכול להצדיק את
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens.json · pk=86173 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=124, trans=98, ratio=0.79
- **sentence count:** src=1, trans=1
- **EN source:**
```
The perfect companion if you crave a refreshing beverage and surprisingly good company. Despite his appearance as no more t
```
- **HE current:**
```
בן ליווי מושלם אם אתה מתענג על משקה מרענן וחברה מפתיעה וטובה. למרות המראה שלו כאילו הוא לא יותר מ-
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens_final.json · pk=50152 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=124, trans=94, ratio=0.758
- **sentence count:** src=1, trans=2
- **EN source:**
```
Just when you think you've solved your problem, your solution goes and starts making fucking demands. Looks like Panam'll o
```
- **HE current:**
```
בדיוק כשאתה חושב שפתחת את הבעיה שלך, הפתרון הולך ומתחיל לדרוש דברים ***! נראה שפנאם תצטרך ל...
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens_final.json · pk=79552 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=124, trans=85, ratio=0.685
- **sentence count:** src=2, trans=2
- **EN source:**
```
V, got a fight at a construction site. Dude responsible is heavily ironed – heard something about lasers. If you manage to 
```
- **HE current:**
```
וי, יש קטטה באתר בנייה. האיש שאחראי כבד מאוד - שמעתי משהו על לייזרים. אם אתה מצליח ל-
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens_final.json · pk=79651 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=124, trans=92, ratio=0.742
- **sentence count:** src=3, trans=3
- **EN source:**
```
Was I speaking in tongues, V? I said no blood, not among civs. They've suffered enough. Although the end can justify the me
```
- **HE current:**
```
האם דיברתי בלשונות, V? אמרתי בלי דם, לא בין אזרחים. הם סבלו מספיק. אם כי הסוף יכול להצדיק את
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · onscreens/onscreens_final.json · pk=86173 · femaleVariant
- **signals:** CUT_MID_SENTENCE
- **length:** src=124, trans=98, ratio=0.79
- **sentence count:** src=1, trans=1
- **EN source:**
```
The perfect companion if you crave a refreshing beverage and surprisingly good company. Despite his appearance as no more t
```
- **HE current:**
```
בן ליווי מושלם אם אתה מתענג על משקה מרענן וחברה מפתיעה וטובה. למרות המראה שלו כאילו הוא לא יותר מ-
```
- **fix recommendation:** Re-translate as a single self-contained sentence. The Hebrew tail is a connector word, meaning the model halted mid-stream — likely a max_tokens cutoff.

### `base` · subtitles/open_world/voicesets/civ_low_f_66_mex_40_mt.json · pk=1908139519779545092 · femaleVariant
- **signals:** LENGTH_TRUNCATION
- **length:** src=124, trans=0, ratio=0.0
- **sentence count:** src=2, trans=1
- **EN source:**
```
<kiroshi l="mex" o="¿Ya viste? Sabía que llegaríamos a un acuerdo." t="See? I knew we would work something out." b="" a=""/
```
- **HE current:**
```
<kiroshi l="mex" o="¿Ya viste? Sabía que llegaríamos a un acuerdo." t="ראה? ידעתי שנמצא פתרון" b="" a=""/>
```
- **fix recommendation:** Re-translate fully — source has 2 sentences but Hebrew has 1. Preserve any \n line breaks; do not exceed ~161 chars (safe buffer).

### `base` · subtitles/open_world/voicesets/gang_val_f_03_mex_30_mt.json · pk=1806624246704234500 · femaleVariant
- **signals:** LENGTH_TRUNCATION
- **length:** src=124, trans=0, ratio=0.0
- **sentence count:** src=2, trans=1
- **EN source:**
```
<kiroshi l="mex" o="¡Chingada madre, que ya voy! ¿Por qué te encabronas?" t="I said I'm on it! Why are you mad?" b="" a=""/
```
- **HE current:**
```
<kiroshi l="mex" o="¡Chingada madre, que ya voy! ¿Por qué te encabronas?" t="אמרתי שאני על זה! למה אתה כועס?" b="" a=""/>
```
- **fix recommendation:** Re-translate fully — source has 2 sentences but Hebrew has 1. Preserve any \n line breaks; do not exceed ~161 chars (safe buffer).


## MEDIUM (526 findings — showing top 50 by source length)

### `dlc` · ep1/onscreens/onscreens.json · pk=91344 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2707, trans=1228, ratio=0.454
- **sentence count:** src=45, trans=30
- **EN source:**
```
Wassup choombas and choombettes! I gots another grain of fucked up truth for y'all. FR34K_S33K's always on the lookout!\n\nLemme start with a question - you know the MedCenter hospital? I mean, who wouldn't, right? Besides the few of y'all praying not to end up there, cuz once they through with you, you're hitting the bricks with a giant-ass bill to boot.\n\nI'll start general and go specific - ev
```
- **HE current:**
```
וואסאפ צ'ומים וצ'ומטות! יש לי עוד פירור של אמת מזויינת בשבילכם. FR34K_S33K תמיד בעניינים!

תתחילו עם שאלה - אתם מכירים את בית החולים MedCenter? כולם מכירים, נכון? חוץ ממי שמתפלל שלא יגיע לשם, כי אחרי שהם מסיימים איתך, אתה יוצא עם חשבון ענק.

אני אעשה כללי ואז ספציפי - כל חברה אופטימלית את המסים שלה, נכון? כי אם אפשר, היית טיפש שלא לעשות את זה. ומה הדרך הכי טובה? צדקה! כסף טוב ויחסי ציבור באותו מהל
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=91344 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2707, trans=1233, ratio=0.455
- **sentence count:** src=45, trans=30
- **EN source:**
```
Wassup choombas and choombettes! I gots another grain of fucked up truth for y'all. FR34K_S33K's always on the lookout!\n\nLemme start with a question - you know the MedCenter hospital? I mean, who wouldn't, right? Besides the few of y'all praying not to end up there, cuz once they through with you, you're hitting the bricks with a giant-ass bill to boot.\n\nI'll start general and go specific - ev
```
- **HE current:**
```
וואסאפ צ'ומים וצ'ומות! יש לי עוד פירור של אמת מזעזעת בשבילכם. FR34K_S33K תמיד ערוך!

תתחילו עם שאלה - אתם מכירים את בית החולים MedCenter? אני מתכוון, מי לא, נכון? חוץ ממי שחי בפחד להגיע לשם, כי אחרי שהם מסיימים איתכם, אתם יוצאים עם חשבון ענק.

אני אעשה את זה כללי ואז ספציפי - כל חברה אופטימלית את המסים שלה, נכון? כי אם אפשר, הייתם טיפשים שלא לעשות זאת. ומה הדרך הטובה ביותר? צדקה! כסף טוב ויחסי ציב
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=85437 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2576, trans=1217, ratio=0.472
- **sentence count:** src=15, trans=12
- **EN source:**
```
City governments of the east coast's metroplex, The Plex, have issued an appeal to residents of the region to register their place of residence in official NUS records. Baltimore City Council has attempted to restructure the primary school system and access to education for several years. Delaware in its entirety has struggled for months to implement waste disposal regulations. In both cases, stat
```
- **HE current:**
```
ממשלות הערים בחוף המזרח של המטרופולין, הנקרא "הפלכס", פרסמו פנייה לתושבים באזור לרשום את מקום מגוריהם בתיקונים רשמיים של NUS. מועצת העיר בולטימור ניסתה לארגן מחדש את מערכת בתי הספר היסודיים וגישה לחינוך במשך מספר שנים. דלאוור כולה מתמודדת עם קשיים במשך חודשים ליישם תקנות לפינוי אשפה. בשני המקרים, שינויי החקיקה נתקעו. לכל הצעה התנגדו חברי המועצה, ובסופו של דבר, עם סטגנציה חקיקתית.

בפנייה משותפת, ה
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=85437 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2576, trans=1220, ratio=0.474
- **sentence count:** src=15, trans=12
- **EN source:**
```
City governments of the east coast's metroplex, The Plex, have issued an appeal to residents of the region to register their place of residence in official NUS records. Baltimore City Council has attempted to restructure the primary school system and access to education for several years. Delaware in its entirety has struggled for months to implement waste disposal regulations. In both cases, stat
```
- **HE current:**
```
ממשלות הערים בחוף המזרח של המטרופולין, הנקרא "הפלכס", פרסמו פנייה לתושבי האזור לרשום את מקום מגוריהם בתיקונים הרשמיים של NUS. מועצת העיר בולטימור ניסתה לארגן מחדש את מערכת בתי הספר היסודיים וגישה לחינוך במשך מספר שנים. דלאוור כולה מתמודדת כבר חודשים עם יישום תקנות לפינוי אשפה. בשני המקרים, שינויים בחוקים נתקעו. לכל הצעה התנגדו חברי המועצה, ובסופו של דבר, עם עצירה חקיקתית.

בפנייה משותפת, הרשויות ה
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=91382 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2443, trans=1205, ratio=0.493
- **sentence count:** src=29, trans=21
- **EN source:**
```
A title we never asked for, and a title we don't deserve. Indie French studio Château de Rais has returned us once again to the pitiable fate of the medieval peasant. While the previous two installments were criticized for clumsy gameplay and overall lack of realism (and rightly so, we all remember the infamous "path of the fire shaman"), the franchise's creators have learned from these difficult 
```
- **HE current:**
```
כותרת שלא ביקשנו ולא ראינו שווה אותה. אולפן צרפתי אינדי בשם שאטו דה ריי החזיר אותנו לגורל העגום של האיכר בימי הביניים. בזמן ששני המשחקים הקודמים ספגו ביקורת על משחקיות גמלונית וחוסר ריאליזם (וצודק, כולם זוכרים את "דרך השמאן האש"), יוצרי הזיכיון למדו מלקחים קשים אלה. הם מזמינים כעת שחקנים לחוות "הסתו האכזרי ביותר של ימי הביניים" באמצעות מערכת VR משופרת. לאחר מספר שעות של משחק בגישה מוקדמת, נוכל לאש
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=91382 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2443, trans=1201, ratio=0.492
- **sentence count:** src=29, trans=21
- **EN source:**
```
A title we never asked for, and a title we don't deserve. Indie French studio Château de Rais has returned us once again to the pitiable fate of the medieval peasant. While the previous two installments were criticized for clumsy gameplay and overall lack of realism (and rightly so, we all remember the infamous "path of the fire shaman"), the franchise's creators have learned from these difficult 
```
- **HE current:**
```
כותרת שלא ביקשנו ולא ראויים לה. אולפן צרפתי אינדי בשם שאטו דה רס חזר אותנו פעם נוספת לגורל העגום של האיכר בימי הביניים. בזמן ששני פרקי המשחק הקודמים ספגו ביקורת על משחקיות גמלונית וחוסר ריאליזם (ובצדק, כולם זוכרים את "דרך השמאן האש"), יוצרי הזיכיון למדו מלקחים קשים אלה. הם כעת מזמינים שחקנים לחוות "סתיו קשה ביותר בימי הביניים" באמצעות מערכת VR משודרגת. לאחר מספר שעות של משחק גישה מוקדמת, אנו יכולי
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=82934 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2312, trans=1188, ratio=0.514
- **sentence count:** src=18, trans=12
- **EN source:**
```
Preliminary report no. 473\nSubject: Song So Mi "Songbird"\nCompiled by: Prof. Susan Baehr\n\nKey notes & observations: Agent Song does not fall into any category of disorder that would disqualify her from service. That is because, as things stand, we have no appropriate category for her ailment. Right now, So Mi's symptoms do not seem to have an effect on her ability to carry out her duties. It i
```
- **HE current:**
```
דו"ח מקדמי מס' 473
נושא: סונג סו מי "ציפור השיר"
מורכב ע"י: פרופ' סוזן בא ehr

נקודות מפתח ומצפיות: סוכנת סונג לא נכנסת לאף קטגוריה של הפרעה שתפסול אותה משירות. זאת משום, כפי שעומדת הדברים כעת, אין לנו קטגוריה מתאימה למחלתה. כרגע, תסמיניה של סו מי לא נראים להשפיע על יכולתה לבצע את חובותיה. קשה לומר כמה זמן המצב הזה יישאר כך.

מצפיות: לאחר ניתוח ההקלטות שסופקו ע"י הסוכנות לאורך שנים רבות, אני יכול 
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=82934 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2312, trans=1192, ratio=0.516
- **sentence count:** src=18, trans=12
- **EN source:**
```
Preliminary report no. 473\nSubject: Song So Mi "Songbird"\nCompiled by: Prof. Susan Baehr\n\nKey notes & observations: Agent Song does not fall into any category of disorder that would disqualify her from service. That is because, as things stand, we have no appropriate category for her ailment. Right now, So Mi's symptoms do not seem to have an effect on her ability to carry out her duties. It i
```
- **HE current:**
```
דוח מקדמי מס' 473
נושא: סונג סו מי "ציפור השיר"
מורכב ע"י: פרופ' סוזן באהר

הערות ותצפיות מרכזיות: סוכנת סונג לא נכנסת לאף קטגוריה של הפרעה שתפסול אותה משירות. זאת מכיוון, כפי שעומדת הדברים, אין לנו קטגוריה מתאימה למחלתה. כרגע, תסמיניה של סו מי לא נראים להשפיע על יכולתה לבצע את חובותיה. קשה לומר כמה זמן המצב הזה יישאר כך.

תצפיות: לאחר ניתוח ההקלטות שסופקו ע"י הסוכנות לאורך השנים הרבות, אני יכול ר
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=93008 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2248, trans=1266, ratio=0.563
- **sentence count:** src=25, trans=26
- **EN source:**
```
June 22\nIt’s my 13th birthday today, my first birthday away from Night City. I’m really sad.\n\nJune 23\nWhat do I miss? I miss having a bathroom with a shower and a toilet. I miss my room with my comfy bed and my games. I miss having a cleaning lady, I miss ordering takeout, I miss the clean air from our air purifier, I miss my friends from school. I even miss the Arasaka school and homework.\n\
```
- **HE current:**
```
יוני 22

זה יום הולדת 13 שלי היום, יום ההולדת הראשון שלי מחוץ לנייט סיטי. אני ממש עצוב.

יוני 23

מה אני מתגעגע? אני מתגעגע לשירותים עם מקלחת ושירותים. אני מתגעגע לחדר שלי עם המיטה הנוחה שלי והמשחקים שלי. אני מתגעגע למנקה, אני מתגעגע להזמין אוכל משלוח, אני מתגעגע לאוויר הנקי מהמטהר האוויר שלנו, אני מתגעגע לחברים שלי מבית הספר. אני אפילו מתגעגע לבית הספר של אראסאקה ומעבודות בית.

יוני 25

אמא ואבא 
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=93008 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2248, trans=1224, ratio=0.544
- **sentence count:** src=25, trans=18
- **EN source:**
```
June 22\nIt’s my 13th birthday today, my first birthday away from Night City. I’m really sad.\n\nJune 23\nWhat do I miss? I miss having a bathroom with a shower and a toilet. I miss my room with my comfy bed and my games. I miss having a cleaning lady, I miss ordering takeout, I miss the clean air from our air purifier, I miss my friends from school. I even miss the Arasaka school and homework.\n\
```
- **HE current:**
```
יוני 22\n זה יום הולדת 13 שלי היום, יום ההולדת הראשון שלי מחוץ לנייט סיטי. אני ממש עצוב.\n\n יוני 23\n על מה אני מתגעגע? אני מתגעגע לאמבטיה עם מקלחת ושירותים. אני מתגעגע לחדר שלי עם המיטה הנוחה שלי והמשחקים שלי. אני מתגעגע למנקה, אני מתגעגע להזמנת אוכל משליח, אני מתגעגע לאוויר נקי מהמטהר האוויר שלנו, אני מתגעגע לחברים שלי מבית הספר. אני אפילו מתגעגע לבית ספר של אראסאקה ומעבודות בית.\n\n יוני 25\n 
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=85399 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2208, trans=1190, ratio=0.539
- **sentence count:** src=17, trans=13
- **EN source:**
```
Night City International and Translunar is touted as the crown jewel of our city and one of North America's technological wonders. However, one look under the surface is enough to realize that the shine of this purported gem has been tarnished throughout the years. Despite the steady rise in demand and number of passengers, Orbital Air did not invest a single eurodollar in its development since th
```
- **HE current:**
```
נייט סיטי אינטרנשיונל וטרנסלונר מוצגת כיהלום שבכתר של העיר ואחת מהפלאים הטכנולוגיים של צפון אמריקה. עם זאת, מבט אחד מתחת לפני השטח מספיק כדי להבין שהברק של האבן היקרה המדוברת דעך לאורך השנים. למרות העלייה המתמדת בביקוש ובמספר הנוסעים, אורביטל אייר לא השקיעה יורודולר אחד בפיתוח שלה מאז שנפתח נמל החלל בשנת 2047. שיפוץ טרמינל טיכו הנוכחי אינו אלא טיפה באוקיינוס ​​של מה שנחוץ כדי לעצור את שקיעתו ההדרג
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=85399 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2208, trans=1215, ratio=0.55
- **sentence count:** src=17, trans=13
- **EN source:**
```
Night City International and Translunar is touted as the crown jewel of our city and one of North America's technological wonders. However, one look under the surface is enough to realize that the shine of this purported gem has been tarnished throughout the years. Despite the steady rise in demand and number of passengers, Orbital Air did not invest a single eurodollar in its development since th
```
- **HE current:**
```
נייט סיטי אינטרנשיונל וטרנסלונר מוצגת כיהלום שבכתר של העיר ואחד מפלאי הטכנולוגיה של צפון אמריקה. עם זאת, מבט אחד מתחת לפני השטח מספיק כדי להבין שהברק של האבן היקרה המדוברת דעך לאורך השנים. למרות העלייה המתמדת בביקוש ובמספר הנוסעים, אורביטל אייר לא השקיעה יורודולר אחד בפיתוח שלה מאז שהנמל החל לפעול בשנת 2047. שיפוץ טרמינל טיכו הנוכחי הוא רק טיפה באוקיינוס ​​של מה שנחוץ כדי לעצור את שקיעת הנמל החללי
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=86217 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2173, trans=1128, ratio=0.519
- **sentence count:** src=13, trans=11
- **EN source:**
```
The Chimera is a prototype tank designed for combat in difficult terrain, including urban areas. It was developed under the leadership of Militech armored division chief engineer Dr. Filippo Andrews. The project was created in response to the need for a "new heavy tank capable of sustained fire and prolonged engagement of enemy forces".\n\nThe design of the Chimera tank was developed between 2065 
```
- **HE current:**
```
הכימרה היא טנק פרוטוטיפ שפותח לקרב בשטח קשה, כולל אזורים עירוניים. הוא פותח בהובלת מהנדס ראשי של חטיבת השריון של מיליטיםכ, ד"ר פיליפו אנדרוז. הפרויקט נוצר בתגובה לצורך בטנק כבד חדש המסוגל אש מתמשכת והתמודדות ממושכת עם כוחות האויב.

עיצוב טנק הכימרה פותח בין השנים 2065 ל-2069. הציוד הסטנדרטי כולל תותח KL-274XYA חיצים, תותח לייזר PAN-12 פוריה, משגר GD27-Angstschema עם יכולת פני שטח-פני שטח ופני שטח-
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=91378 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2148, trans=1219, ratio=0.568
- **sentence count:** src=21, trans=19
- **EN source:**
```
The legendary Interstellar Commander series is BACK! After years of anticipation fans can once again board the Burgundy and travel at light speed to save the galaxy. But can the sixth installment of this beloved franchise still pack the same "oomph"? Or has it devolved into a lukewarm pile of "meh"? We've got the answer!\n\nInterstellar Commander 6: The Hunt for Baron Octavian still has everything
```
- **HE current:**
```
סדרת אינטרסטלר קומנדר האגדית חוזרת! אחרי שנים של ציפייה, מעריצים יכולים שוב לעלות על הבורגונדי ולטוס במהירות האור כדי להציל את הגלקסיה. אבל האם ההתקנה השישית של זיכיון אהוב זה עדיין יכולה להכיל את אותו "חוזק"? או שהיא התדרדרה לערימה חמימה של "בלה"? יש לנו את התשובה! אינטרסטלר קומנדר 6: הציד אחר הברון אוקטביאנוס עדיין מכיל הכל מה שהפך אותנו לגבוהים מזיכרונות הכניסות הקודמות של הסדרה. קרבות ספקטקולר
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=91378 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2148, trans=1202, ratio=0.56
- **sentence count:** src=21, trans=20
- **EN source:**
```
The legendary Interstellar Commander series is BACK! After years of anticipation fans can once again board the Burgundy and travel at light speed to save the galaxy. But can the sixth installment of this beloved franchise still pack the same "oomph"? Or has it devolved into a lukewarm pile of "meh"? We've got the answer!\n\nInterstellar Commander 6: The Hunt for Baron Octavian still has everything
```
- **HE current:**
```
סדרת קומנדר בין כוכבי אגדית חוזרת! אחרי שנים של ציפייה, מעריצים יכולים שוב לעלות על הבורגונדי ולטוס במהירות האור כדי להציל את הגלקסיה. אבל האם ההתקנה השישית של זיכיון אהוב זה עדיין יכולה להכיל את אותו "חזקה"? או שהיא התדרדרה לערימה חמימה של "בלה"? יש לנו את התשובה!

קומנדר בין כוכבי 6: הציד אחר הברון אוקטביוס עדיין מכיל הכל מה שהפך אותנו ללהוטים מכניסות קודמות בסדרה. קרבות ספקטקולריים בתחנות חלל נ
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=85395 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2145, trans=1165, ratio=0.543
- **sentence count:** src=15, trans=12
- **EN source:**
```
Sixty-six million years ago, an asteroid struck our planet and changed the course of natural history. Measuring approximately 6.2 miles (10 km) in diameter, the space rock struck with a force equal to 10 billion atom bombs, leaving a crater 18.5 miles (30 km) deep. Of course, the likelihood of another such catastrophe occuring in the near future is next to none. But can we really sleep soundly at 
```
- **HE current:**
```
לפני שישים וששה מיליון שנה, אסטרואיד פגע בכדור הארץ שלנו והשפיע על מהלך ההיסטוריה הטבעית. בקוטר של כ-6.2 מיילים (10 ק"מ), סלע החלל פגע בכוח שווה ל-10 מיליארד פצצות אטום, והותיר kráter בעומק של 18.5 מיילים (30 ק"מ). כמובן, הסבירות לכך שאסון כזה יתרחש בקרוב היא זניחה. אבל האם באמת נוכל לישון בשלווה בלילה? זה תלוי במועצת החלל האירופית, שיש לה כרגע שלושה מאיצי מסה מבוססי ירח לרשותה. נכון – שלושה!

חוק
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=85395 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2145, trans=1156, ratio=0.539
- **sentence count:** src=15, trans=12
- **EN source:**
```
Sixty-six million years ago, an asteroid struck our planet and changed the course of natural history. Measuring approximately 6.2 miles (10 km) in diameter, the space rock struck with a force equal to 10 billion atom bombs, leaving a crater 18.5 miles (30 km) deep. Of course, the likelihood of another such catastrophe occuring in the near future is next to none. But can we really sleep soundly at 
```
- **HE current:**
```
לפני שישים וששה מיליון שנה, אסטרואיד פגע בכדור הארץ שלנו והשפיע על מהלך ההיסטוריה הטבעית. בקוטר של כ-6.2 מיילים (10 ק"מ), הסלע החללי פגע בכוח שווה ל-10 מיליארד פצצות אטום, ויצר מכתש עמוק 18.5 מיילים (30 ק"מ). כמובן, הסבירות של אסון נוסף מסוג זה שיתרחש בקרוב היא כמעט אפסית. אבל האם באמת נוכל לישון בשקט בלילה? זה תלוי במועצת החלל האירופית, שיש לה כיום שלושה מאיצי מסה המבוססים על הירח לרשותה. נכון – 
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=85411 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2110, trans=1230, ratio=0.583
- **sentence count:** src=12, trans=13
- **EN source:**
```
NetWatch is denying rumors that it's secretly run by the primary RABID left by Rache Bartmoss after his death. Though the accusations are serious, for now only medias of questionable credibility seem to be circulating them. But let's imagine for a minute: if an institution like NetWatch truly was one of the entities responsible for the DataKrash and demise of the old Net, then we would have to ret
```
- **HE current:**
```
נטווטש דוחה שמועות לפיהן היא מנוהלת בסתר על ידי ה-RABID העיקרי שהותיר אחריו רחל ברטמוס לאחר מותו. למרות חומרת ההאשמות, נכון לעכשיו רק מדיה בעלת אמינות מפוקפקת מפיצה אותן. אבל בואו נדמיין לרגע: אם מוסד כמו נטווטש היה באמת אחד מהישויות האחראיות לקריסת הנתונים והרס הרשת הישנה, אז היינו צריכים לחשוב מחדש על כל מה שחשבנו שידענו על העולם של ימינו.
נטווטש היא היחידה שמגנה אותנו מ-AI פראיים, נטווטש היא הי
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=85411 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2110, trans=1245, ratio=0.59
- **sentence count:** src=12, trans=12
- **EN source:**
```
NetWatch is denying rumors that it's secretly run by the primary RABID left by Rache Bartmoss after his death. Though the accusations are serious, for now only medias of questionable credibility seem to be circulating them. But let's imagine for a minute: if an institution like NetWatch truly was one of the entities responsible for the DataKrash and demise of the old Net, then we would have to ret
```
- **HE current:**
```
נטווטש דוחה שמועות לפיהן היא מנוהלת בסתר על ידי ה-RABID העיקרי שהשאיר אחריו רחל ברטמוס לאחר מותו. למרות חומרת ההאשמות, נכון לעכשיו רק מדיה בעלת אמון מפוקפק מפיץ אותן. אבל בואו נדמיין לרגע: אם מוסד כמו נטווטש באמת היה אחד מהישויות האחראיות להריסתו של הנת ולקריסת הרשת הישנה, אז היינו צריכים לחשוב מחדש על כל מה שאנחנו חושבים שידענו על העולם של היום.
נטווטש היא היחידה שמגנה עלינו מ-AI פראיים, נטווטש ה
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=91384 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2102, trans=1228, ratio=0.584
- **sentence count:** src=16, trans=16
- **EN source:**
```
Arasaka Tower... the mere mention of which causes Arasaka corporate lawyers to start violently convulsing and hot-dialing their spec ops teams. Though the game saw the light of day a decade ago, it's still very much a bone of legal contention. Its sale was outlawed on all continents and only exists today in the form of pirate copies on the black market and in the farthest corners of the Net. On th
```
- **HE current:**
```
מגדל אראסאקה... רק הזכרת השם גורמת לעורכי דין של אראסאקה להתחיל להתכווץ ולהתקשר לצוותי הפעולה המיוחדים שלהם. למרות שהמשחק ראה אור לפני עשור, הוא עדיין נושא של מחלוקת משפטית. מכירתו נאסרה בכל היבשות והוא קיים היום רק בצורת עותקים פיראטיים בשוק השחור ובפינות הכי רחוקות של הרשת. לרגל יום השנה העשירי להוצאת המשחק, אנחנו כאן כדי להזכיר לכם מה באמת קרה.

"מגדל אראסאקה" הוא משחק ארקייד פשוט מסוג "הק ופגע
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=91384 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=2102, trans=1225, ratio=0.583
- **sentence count:** src=16, trans=15
- **EN source:**
```
Arasaka Tower... the mere mention of which causes Arasaka corporate lawyers to start violently convulsing and hot-dialing their spec ops teams. Though the game saw the light of day a decade ago, it's still very much a bone of legal contention. Its sale was outlawed on all continents and only exists today in the form of pirate copies on the black market and in the farthest corners of the Net. On th
```
- **HE current:**
```
מגדל אראסאקה... הזכרת השם שלו גורמת לעורכי דין של אראסאקה להתחיל להתכווץ באלימות ולהתקשר לצוותי הפעולה המיוחדים שלהם. למרות שהמשחק ראה אור לפני עשור, הוא עדיין נושא לתביעות משפטיות רבות. מכירתו נאסרה בכל היבשות והוא קיים היום רק בצורת עותקים פיראטיים בשוק השחור ובפינות הכי רחוקות של הרשת. לרגל יום השנה העשירי להוצאת המשחק, אנחנו כאן כדי להזכיר לכם מה באמת קרה.

"מגדל אראסאקה" הוא משחק ארקייד פשוט 
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=82684 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1988, trans=1198, ratio=0.603
- **sentence count:** src=34, trans=25
- **EN source:**
```
Yo yo yooo it’s your favorite irongirl here! Comin’ at you with the latest in only the BEST in military iron. You would not BELIEVE how much gear I tested this past week, and even some from the one and only Tsunami! We love you Tsunamiiii <3\n\nTime to dive in! Let's start with something special. I'm talkin special like "special forces" special, not like "oh wow, so special!" special. Nokota relea
```
- **HE current:**
```
יו יואו יואו זה הברזל גירל האהובה עליכם! מגיעה אליכם עם הכי טוב שיש בנשק צבאי. לא תאמינו כמה ציוד בדקתי השבוע, ואפילו קצת מהאחד והיחיד טסונאמי! אנחנו אוהבים אותך טסונאמי <3

זמן לצלול פנימה! בואו נתחיל עם משהו מיוחד. אני מדברת על מיוחד כמו "כוחות מיוחדים" מיוחד, לא כמו "וואו, כל כך מיוחד!" מיוחד. נוקוטה הוציאה את הרובה הצלף הדגל שלה - האוספרי. אם אנחנו רוצים להפוך ליותר טכניים באנליזה של מחיר-איכו
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=82684 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1988, trans=1206, ratio=0.607
- **sentence count:** src=34, trans=28
- **EN source:**
```
Yo yo yooo it’s your favorite irongirl here! Comin’ at you with the latest in only the BEST in military iron. You would not BELIEVE how much gear I tested this past week, and even some from the one and only Tsunami! We love you Tsunamiiii <3\n\nTime to dive in! Let's start with something special. I'm talkin special like "special forces" special, not like "oh wow, so special!" special. Nokota relea
```
- **HE current:**
```
יו יואו יואו זה הברזל גירל האהובה עליכם! מגיעה אליכם עם הכי טוב שיש בנשק צבאי. לא תיאמנו כמה ציוד בדקתי השבוע, ואפילו קצת מהאחד והיחיד טסונמי! אנחנו אוהבים אותך טסונמיי <3

זמן לצלול פנימה! בואו נתחיל עם משהו מיוחד. אני מדברת על מיוחד כמו "כוחות מיוחדים" מיוחד, לא כמו "וואו, כל כך מיוחד!" מיוחד. נוקוטה הוציאו את הרובה צלפים הדגל שלהם - האוספריי. אם אנחנו רוצים להפוך לטכניים באנליזה של מחיר-איכות, 
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=91345 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1942, trans=1144, ratio=0.589
- **sentence count:** src=22, trans=20
- **EN source:**
```
Wassup, all you losers, winners and inbetweeners!\n\nRemember that scandal at the Biotechnica Academy a few years back? "Scandal's" a bit of an exaggeration seeing as the noise fizzled out and the media's hard-on went dead limp quick. Bribes here, greased palms there - part and parcel of our daily existence, ain't it? The cornerstone of our society?\n\nSo why, you ask, is FR34K_S33K digging up old
```
- **HE current:**
```
וואסאפ, כלכם לוזרים, מנצחים וכל מה שביניהם!

תזכרו את השערורייה באקדמיה הביוטכניקה לפני כמה שנים? "שערורייה" זה קצת הגזמה בהתחשב בכך שהרעש דעך והמדיה איבדה עניין מהר מאוד. שוחד פה, כפות משומנות שם - חלק בלתי נפרד מקיומנו היומיומי, לא? אבן היסוד של החברה שלנו?

אז למה, אתם שואלים, FR34K_S33K חופר בזבל ישן ושכוח? האם הנט לא נותן לי מספיק דברים לשקוע בהם שיניים?

הנה העניין - כל מה שיש ברשת אתם יכולי
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=85460 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1932, trans=1188, ratio=0.615
- **sentence count:** src=11, trans=15
- **EN source:**
```
Hello! This is Leland, your Creative Assistant!\nBeing a language-based framework, I am able to generate a large number of texts regarding a variety of topics. I can help you prepare content for many creative endeavors, including scripts, marketing campaigns or visual design.\nfkillncljjrjjhvgrcuf\nMy services are already being utilized by millions of satisfied users, and my script for Feudal Peas
```
- **HE current:**
```
שלום! זה לילנד, עוזר היצירתי שלך!

כמודל מבוסס שפה, אני מסוגל לייצר כמות גדולה של טקסטים בנושאים מגוונים. אני יכול לעזור לך להכין תוכן למגוון רחב של יזמות יצירתיות, כולל תסריטים, מסעות שיווק או עיצוב חזותי.

fkillncljjrjjhvgrcuf

השירותים שלי כבר משמשים מיליוני משתמשים מרוצים, ותסריטי לסימולטור איכר פיאודלי 3 זכה בליבותיהם של

cccccbcbhftbcckhdlugvihccelcdfblcvhrhjlihfel

גיימרים ברחבי העולם. האול
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=86306 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1864, trans=1175, ratio=0.63
- **sentence count:** src=11, trans=9
- **EN source:**
```
In the 2020s Militech established a secret, experimental military project in this part of Pacifica, constructing bunkers and laboratories cleverly hidden beneath urban infrastructure. Nearly half a century later, a group of investors appeared, unaware they were building on the remains of an old military complex. When a lab was excavated at one of the construction sites, the investors were forced o
```
- **HE current:**
```
בשנות ה-2020 הקימה מיליטים פרויקט צבאי ניסיוני סודי באזור זה של פאסיפיקה, ובנתה בו Bunkers ומעבדות שהוסתרו בתוך התשתית העירונית בצורה חכמה. כמעט חצי מאה לאחר מכן הופיעה קבוצת משקיעים, לא מודעת לכך שהיא בונה על שרידי מתחם צבאי ישן. כאשר מעבדה נחפרה באחד מאתרי הבנייה, המשקיעים נאלצו לעזוב את פאסיפיקה ומיליטים הקימה חומה סביב השכונה prétendument עקב דליפות גז, תיעוד לקוי של פיתוחים מקומיים ופעילות נפ
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=86298 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1855, trans=1202, ratio=0.648
- **sentence count:** src=11, trans=11
- **EN source:**
```
Night City International and Translunar Spaceport (NCX) is Orbital Air's flagship investment in North America. It was built between 2045 and 2047 where the majestic Morro Rock volcanic neck, a geological feature sacred to local Native American tribes, had stood for 23 million years. But it wasn't heartless corpos who gave permission to demolish the rock – Night City authorities did.\n\nIn consulta
```
- **HE current:**
```
נייט סיטי אינטרנשיונל וטרנסלונר ספייספורט (NCX) היא ההשקעה הדגל של אורביטל אייר בצפון אמריקה. היא נבנתה בין 2045 ל-2047 במקום בו עמד צוואר הר הגעש מורו רוק המפואר, תופעת גיאולוגית קדושה לשבטים ילידים אמריקאים מקומיים במשך 23 מיליון שנה. אבל זה לא קורפו חסרי לב שנתנו רשות להרוס את הסלע - רשויות נייט סיטי עשו זאת.

בתשאול עם קבוצת משקיעים, ראש עיריית נייט סיטי הסכים לחתום על חוזה לבניית מדחף המוני ב
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=86298 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1855, trans=1197, ratio=0.645
- **sentence count:** src=11, trans=12
- **EN source:**
```
Night City International and Translunar Spaceport (NCX) is Orbital Air's flagship investment in North America. It was built between 2045 and 2047 where the majestic Morro Rock volcanic neck, a geological feature sacred to local Native American tribes, had stood for 23 million years. But it wasn't heartless corpos who gave permission to demolish the rock – Night City authorities did.\n\nIn consulta
```
- **HE current:**
```
נייט סיטי אינטרנשיונל וטרנסלונר ספייספורט (NCX) היא ההשקעה הדגל של אורביטל אייר בצפון אמריקה. היא נבנתה בין 2045 ל-2047 במקום בו עמד צוואר הר הגעש מורו רוק המפואר, תכונה גיאולוגית קדושה לשבטים ילידים אמריקאים מקומיים במשך 23 מיליון שנה. אבל זה לא קורפו חסרי לב שהעניקו רשות להרוס את הסלע – רשויות נייט סיטי עשו זאת.

בייעוץ עם קבוצת משקיעים, ראש עיריית נייט סיטי הסכים לחתום על חוזה לבנות מסלול ירי ב
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=82907 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1853, trans=1110, ratio=0.599
- **sentence count:** src=9, trans=7
- **EN source:**
```
Sending you a general list of events of the inauguration, then I'll send a detailed breakdown for the crew. Familiarize yourselves with what's there. Reminder: NO DIBS ON SPECIFIC TASKS. I'll make sure to split them fairly.\nHere's a copy of what the participants received:\n---------------------------\n\nThe inauguration of Founding Our Future EXPO is close at hand. Here are some activities you ca
```
- **HE current:**
```
הנחיות כלליות לאירוע ההשקה של יריד "מכוננים את העתיד" לפניכם רשימה כללית של האירועים שיתקיימו, ואחריה אפרט לכל אחד מכם את המשימות. שימו לב היטב לפרטים. תזכורת: אין לתפוס משימות ספציפיות. אדאג לחלק אותן באופן הוגן.
הנה העתק מהשלוח שקיבלו המשתתפים:

---------------------------

השקת יריד "מכוננים את העתיד" מתקרבת בצעדי ענק. הנה כמה מהפעילויות שאתם יכולים לצפות להן:

**יום 1:**
- נאום פתיחה של נשיאת 
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=82907 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1853, trans=1107, ratio=0.597
- **sentence count:** src=9, trans=6
- **EN source:**
```
Sending you a general list of events of the inauguration, then I'll send a detailed breakdown for the crew. Familiarize yourselves with what's there. Reminder: NO DIBS ON SPECIFIC TASKS. I'll make sure to split them fairly.\nHere's a copy of what the participants received:\n---------------------------\n\nThe inauguration of Founding Our Future EXPO is close at hand. Here are some activities you ca
```
- **HE current:**
```
האינאוגורציה של תערוכת "מייסדים את העתיד" מתקרבת בצעדי ענק. הנה כמה מהפעילויות שאתם יכולים לצפות להן:

יום 1:
- נאום פתיחה מאת נשיאת ארה"ב רוזלינד מאיירס, יחד עם חיתוך סרט טקסי!
- הופעה של הטנור המדהימה ג'וזף דוארטה
- שמפניה ומגוון מאכלים באולם התערוכה הראשון

יום 2:
- קונצרט פסנתר סובלימי של ג'יאנג יאן יא
- מופע זיקוקין שמאיר את ההתקדמות בשולי המחוז
- שמפניה ומגוון Hors d'oeuvres

יום 3:
- "אבטחה
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=85397 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1818, trans=1288, ratio=0.708
- **sentence count:** src=21, trans=19
- **EN source:**
```
(…) we're like animals that have enough self-awareness to realize they're living on a farm, their freedom limited, their death inevitable, yet believing they understand the inner machinations of their small, isolated world. Imperfect, but familiar.\n\nThe truth, as always, eludes us. Those in control try desperately to hide the fact that the truth cannot be found within the confines of the farm, b
```
- **HE current:**
```
(…) אנחנו כמו בעלי חיים שיש להם מספיק מודעות עצמית כדי להבין שהם חיים בחווה, חופשיהם מוגבלים, מותם בלתי נמנע, ובכל זאת מאמינים שהם מבינים את המנגנונים הפנימיים של עולמם הקטן וה מבודד. לא מושלם, אבל מוכר.\n\n האמת, כמו תמיד, חומקת מאיתנו. אלה שבשליטה מנסים נואשות להסתיר את העובדה שהאמת לא נמצאת בתוך גבולות החווה, אלא מעבר לה - מתחתיה. האמת המסוכנת והעגומה הזאת. אלה שמפקחים עלינו, שולטים בנו, שולטים
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=85397 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1818, trans=1297, ratio=0.713
- **sentence count:** src=21, trans=19
- **EN source:**
```
(…) we're like animals that have enough self-awareness to realize they're living on a farm, their freedom limited, their death inevitable, yet believing they understand the inner machinations of their small, isolated world. Imperfect, but familiar.\n\nThe truth, as always, eludes us. Those in control try desperately to hide the fact that the truth cannot be found within the confines of the farm, b
```
- **HE current:**
```
(…) אנחנו כמו חיות שיש להן מספיק מודעות עצמית כדי להבין שהן חיים בחווה, חירותן מוגבלת, מותן בלתי נמנע, ובכל זאת מאמינות שהן מבינות את המנגנונים הפנימיים של עולמן הקטן וה מבודד. לא מושלם, אבל מוכר.\n\n האמת, כמו תמיד, חומקת מאיתנו. אלה שבשליטה מנסים נואשות להסתיר את העובדה שאמת לא ניתן למצוא בתוך גבולות החווה, אלא מעבר לה - מתחתיה. האמת המסוכנת והעגומה הזאת. אלה שמפקחים עלינו, שולטים בנו, שולטים בנ
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=86193 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1800, trans=1188, ratio=0.66
- **sentence count:** src=10, trans=10
- **EN source:**
```
The incumbent president of the New United States of America. Myers was born into a wealthy and influential East Coast family, said to be descendants of the first English settlers aboard the Mayflower. She began her political career in the US Marine Corps - her patriotism, courage on the battlefield, obedience and discipline paved the way for her rapid promotion and brought her to the attention of 
```
- **HE current:**
```
נשיאת ארצות הברית המאוחדות הנוכחית. מאיירס נולדה למשפחה עשירה ומשפיעה בחוף המזרחי, שמועות גורסות כי היא צאצאית של המתיישבים האנגלים הראשונים על ספינת "מייפלואר". היא החלה את הקריירה הפוליטית שלה בכוחות הנחתים של ארצות הברית - הפטריוטיזם שלה, האומץ בשדה הקרב, הציות והמשמעת סללו את הדרך לקידום מהיר שלה והביאו אותה לתשומת לבם של בכירים במיליטק. לאחר מותו של מנכ"ל החברה, דונלד לונדיי, זו הייתה מאיירס 
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=86193 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1800, trans=1204, ratio=0.669
- **sentence count:** src=10, trans=11
- **EN source:**
```
The incumbent president of the New United States of America. Myers was born into a wealthy and influential East Coast family, said to be descendants of the first English settlers aboard the Mayflower. She began her political career in the US Marine Corps - her patriotism, courage on the battlefield, obedience and discipline paved the way for her rapid promotion and brought her to the attention of 
```
- **HE current:**
```
נשיאת ארצות הברית המאוחדות החדשות הנוכחית. מאיירס נולדה למשפחה עשירה ובעלת השפעה בחוף המזרחי, שמועות גורסות שהם צאצאים של המתיישבים האנגלים הראשונים על סיפון המייפלואר. היא החלה את הקריירה הפוליטית שלה בכוחות הנחתים של ארצות הברית - הפטריוטיות שלה, האומץ בשדה הקרב, הציות והמשמעת סללו את הדרך לקידום מהיר שלה והביאו אותה לתשומת לבם של בכירים במיליטק. לאחר מותו של המנכ"ל של החברה, דונלד לונד yee, זו 
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=86422 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1800, trans=1193, ratio=0.663
- **sentence count:** src=10, trans=10
- **EN source:**
```
The incumbent president of the New United States of America. Myers was born into a wealthy and influential East Coast family, said to be descendants of the first English settlers aboard the Mayflower. She began her political career in the US Marine Corps - her patriotism, courage on the battlefield, obedience and discipline paved the way for her rapid promotion and brought her to the attention of 
```
- **HE current:**
```
נשיאת ארצות הברית המאוחדות הנוכחית. מאיירס נולדה למשפחה עשירה ובעלת השפעה בחוף המזרחי, שמועות גורסות שהם צאצאים של המתיישבים האנגלים הראשונים על סיפון המייפלואר. היא החלה את הקריירה הפוליטית שלה בכוחות הנחתים של ארצות הברית - הפטריוטיזם שלה, האומץ בשדה הקרב, הציות והמשמעת סללו את הדרך לקידום מהיר שלה והביאו אותה לתשומת לבם של בכירים במיליטק. לאחר מותו של המנכ"ל של החברה, דונלד לונדיאה, זו הייתה מא
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=86255 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1764, trans=1206, ratio=0.684
- **sentence count:** src=10, trans=11
- **EN source:**
```
If you hear "Dogtown" and automatically think "BARGHEST," chances are you won't die straight away. The organization founded by Kurt Hansen is more than just an ordinary Night City gang. No one else has managed the feat of carving an entire district out for themselves, kicking out the police completely and keeping it that way for nearly a decade.\nIt started small: Colonel Hansen's unit seized part
```
- **HE current:**
```
אם אתה שומע "דוגטאון" ואתה חושב אוטומטית על "ברג'סט", הסיכויים שאתה לא תמות מיד גבוהים. הארגון שהוקם על ידי קורט הנסן הוא הרבה יותר מאשר כנופיה רגילה בנייט סיטי. אף אחד אחר לא הצליח להשיג את המשימה של לגזור לעצמו מחוז שלם, לגרש את המשטרה לחלוטין ולהשאיר את זה כך במשך כמעט עשור. הכל התחיל קטן: יחידתו של קולונל הנסן השתלטה על חלק מפסיפיקה בסוף מלחמת האיחוד ולא הניחה נשק. רק שש חיילים נותרו מהיחידה ה
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=86255 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1764, trans=1195, ratio=0.677
- **sentence count:** src=10, trans=11
- **EN source:**
```
If you hear "Dogtown" and automatically think "BARGHEST," chances are you won't die straight away. The organization founded by Kurt Hansen is more than just an ordinary Night City gang. No one else has managed the feat of carving an entire district out for themselves, kicking out the police completely and keeping it that way for nearly a decade.\nIt started small: Colonel Hansen's unit seized part
```
- **HE current:**
```
אם אתה שומע "דוגטאון" ומתחיל לחשוב "ברג'סט", הסיכויים שאתה לא תמות מיד גבוהים. הארגון שהוקם על ידי קורט הנסן הוא הרבה יותר מארגון פשע רגיל בנייט סיטי. אף אחד אחר לא הצליח להשיג את ההישג של גזירת רבע שלם לעצמו, לגרש את המשטרה לחלוטין ולהשאיר את זה כך במשך כמעט עשור. הכל התחיל קטן: יחידת קולונל הנסן השתלטה על חלק מפאסיפיקה בסוף מלחמת האיחוד ולא הניחה את הנשק. רק שש חיילים נותרו מהסגל הזה, והם, כאנשי
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=86269 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1736, trans=1231, ratio=0.709
- **sentence count:** src=9, trans=11
- **EN source:**
```
Orbital Air was founded in Nairobi, Kenya, at the beginning of the 21st century - it is the oldest corporation specializing in the transportation of cargo and passengers via the Earth's orbit. OA's fleet consists of heavy-lift rockets, manned and unmanned spacecraft and commercial passenger shuttles. The Kenyan giant controls most of the world's spaceports, including the largest cosmodrome in Moga
```
- **HE current:**
```
אורביטל אייר נוסדה בניירובי, קניה, בתחילת המאה ה-21 - זו הקורפורציה העתיקה ביותר המתמחה בהובלת מטען ונשיאה דרך מסלול כדור הארץ. צי המטוסים של OA מורכב מרוקטות כבדות, כלי חלל מאוישים ולא מאוישים ונושאות נוסעים מסחריות. הענק הקנייתי שולט ברוב נמלי החלל בעולם, כולל הקוסמודרום הגדול ביותר במוגדישו.

תיק השירותים הנרחב של אורביטל אייר כולל גם את הבנייה והתחזוקה של תחנות τροפיות ורשתות לוויינים. החברה מ
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=86456 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1736, trans=1188, ratio=0.684
- **sentence count:** src=17, trans=6
- **EN source:**
```
Dear Dr. Vargas,\nWe need your help. Our daughter Jennifer Haley spent three years of her life in your facility, but unfortunately was never chosen for a contract. I make no secret of the fact that our family's financial situation doesn't permit us to cover the costs of Jennifer's medication.\n\nAs you're well aware, without her medication, the modifications you've given her will cause her to suff
```
- **HE current:**
```
לד"ר ורגס,\n אנחנו צריכים את עזרתך. בתנו ג'ניפר היילי בילתה שלוש שנים מחייה במתקן שלך, אבל לצערנו לא נבחרה לחוזה. אני לא מסתיר את העובדה שהמצב הכלכלי של משפחתנו אינו מאפשר לנו לכסות את עלויות התרופות של ג'ניפר.\n\n כפי שאתה ודאי יודע, בלי התרופות שלה, השינויים שנתת לה יגרמו לה לסבל. ילדה בת שש עשרה לא צריכה לחוות כאבי ראש באשכולות או אבנים בכליות.\n\n אני מתחנן לעזרתך. אני לא מבקש כסף - רק תרופה כ
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=86269 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1736, trans=1209, ratio=0.696
- **sentence count:** src=9, trans=11
- **EN source:**
```
Orbital Air was founded in Nairobi, Kenya, at the beginning of the 21st century - it is the oldest corporation specializing in the transportation of cargo and passengers via the Earth's orbit. OA's fleet consists of heavy-lift rockets, manned and unmanned spacecraft and commercial passenger shuttles. The Kenyan giant controls most of the world's spaceports, including the largest cosmodrome in Moga
```
- **HE current:**
```
אורביטל אייר נוסדה בניירובי, קניה, בתחילת המאה ה-21 - זו הקורפורציה העתיקה ביותר המתמחה בהובלת מטען ונשיאה דרך מסלול כדור הארץ. צי המטוסים של OA מורכב מרוקטות כבדות, כלי חלל מאוישים ולא מאוישים ונוסעות נוסעים מסחריות. ענקית הקניית שולטת ברוב נמלי החלל בעולם, כולל הקוסמודרום הגדול ביותר במוגדישו.

תיק השירותים הנרחב של אורביטל אייר כולל גם את הבנייה והתחזוקה של תחנות מסלוליות ורשתות לוויינים. הקורפ
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=83122 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1730, trans=1206, ratio=0.697
- **sentence count:** src=9, trans=11
- **EN source:**
```
"The situation in Dogtown (as it is called by the local inhabitants) is complex in nearly every aspect. From an economic perspective, the entire district demonstrates enormous potential for development. Assuming that legal matters pertaining to land ownership and real estate would be settled and the current residents relocated, a whole new world of opportunities would become available. One of them
```
- **HE current:**
```
המצב בדוגטאון (כפי שקוראים לו תושביו המקומיים) מסובך כמעט בכל היבט. מבחינה כלכלית, כל המחוז מדגים פוטנציאל עצום לפיתוח. בהנחה שהנושאים המשפטיים הקשורים לבעלות על קרקעות ונדל"ן ייוסדרו והתושבים הנוכחיים יועתקו, עולם שלם של הזדמנויות יהפוך זמין. אחת מהן תהיה בוודאות החזרה לחזון של יצירת מוקדים לבידור (קזינו, בתי מלון, מסעדות) ועסקים (מרכזי טכנולוגיה ומרכזי כנסים). קבלת זכויות לתוכניות שימוש בקרקע בא
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=86812 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1712, trans=1185, ratio=0.692
- **sentence count:** src=11, trans=11
- **EN source:**
```
Popular in Dogtown, “phant” is a highly addictive hallucinogenic drug that affects the central nervous system and causes irreversible changes in the brain. It stimulates the production of both serotonin and dopamine. Delusions and hallucinations involving all the senses (sight, hearing, touch) appear soon after the drug is consumed – hence the rumors that the drug is stronger than even the best br
```
- **HE current:**
```
פופולרי בדוגטאון, "פאנט" הוא סם הזיה פסיכואקטיבי ממכר מאוד המשפיע על מערכת העצבים המרכזית וגורם לשינויים בלתי הפיכים במוח. הוא מעודד את ייצור הסרוטונין והדופמין. אשליות והזיות המעורבות בכל החושים (ראייה, שמיעה, מגע) מופיעות זמן קצר לאחר צריכת הסם – מכאן השמועות שהסם חזק יותר אפילו מהבריינדאנס הטובים ביותר. מעניין לציין שהסביבה שמסביב לאדם הצורך את הסם יש לה השפעה ישירה על מהלך ההזייה. בדוגטאון, כב
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=90180 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1712, trans=1177, ratio=0.688
- **sentence count:** src=16, trans=17
- **EN source:**
```
Sienna Simon - chick's chipped with preem chrome from her corpo days, Arasaka memory enhacement, private ICE (no point trying to break through from up close or at a distance), Biotech Mk.3 cyberdeck and a monowire. You'll find her at the Heavy Hearts working the bar.\n\nEliana Zarate - Militech corpo who's supposed to drop by the stadium to do biz with a Sophia Dupont. Little missy's got her own d
```
- **HE current:**
```
סיינה סימון - בובה עם כרום משודרג מימי הקורפו שלה, שיפור זיכרון של אראסקה, קרח פרטי (אין טעם לנסות לפרוץ מקרוב או מרחוק), סייברוור Mk.3 של ביוטק ומונווויר. תמצא אותה בבר בהבי הארטס.

אליאנה זארטה - קורפו של מיליטק שצריכה להגיע לאצטדיון כדי לעשות עסקים עם סופיה דופונט. ליל' הזאת יש נהג פרטי, אז הכי טוב לגמור אותו ראשון, לגנוב את הרכב ולהמתין שהדיימה חסרת האונים תיכנס. ואז כמו תמיד - לחסום את אות הב
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=90180 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1712, trans=1159, ratio=0.677
- **sentence count:** src=16, trans=16
- **EN source:**
```
Sienna Simon - chick's chipped with preem chrome from her corpo days, Arasaka memory enhacement, private ICE (no point trying to break through from up close or at a distance), Biotech Mk.3 cyberdeck and a monowire. You'll find her at the Heavy Hearts working the bar.\n\nEliana Zarate - Militech corpo who's supposed to drop by the stadium to do biz with a Sophia Dupont. Little missy's got her own d
```
- **HE current:**
```
סיינה סימון - בובה עם כרום משודרג מימי הקורפו שלה, אראסאקה שיפור זיכרון, קרח פרטי (אין טעם לנסות לפרוץ מקרוב או מרחוק), סייברדק ביוטק Mk.3 ומונוווייר. תמצאו אותה ב-Heavy Hearts עובדת בבר.

אליאנה זראטה - קורפו של מיליטק שצריכה להגיע לאצטדיון כדי לעשות עסקים עם סופיה דופונט. לילדה הזאת יש נהג פרטי, אז הכי טוב לגמור אותו קודם, לגנוב את הרכב ולהמתין שהדמה חסרת האונים שלנו תעלה פנימה. ואז כמו תמיד - ל
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=91342 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1688, trans=1276, ratio=0.756
- **sentence count:** src=19, trans=22
- **EN source:**
```
Wassup dickbags and pussycaps- it's FR34K_S33K at your fuckin' service with some oh-so-fresh news. I be watching what strings those slender-ass corpo fingers be pulling, cuz if I don't do it, who the fuck will?\n\nSo you know how corps always blaming shit on "gang wars" like they ain't the ones fucking supplying the heat and lead and stirring up the beef? No surprise, right? Everyone know that. Bu
```
- **HE current:**
```
וואסאפ כיסויי זין ותחתיות - זה FR34K_S33K לשירותכם עם חדשות טריות. אני עוקב אחרי החוטים האלה שאצבעות קורפו הדקות שולפות, כי אם לא אני אז מי לעזאזל יעשה את זה?

אתם יודעים איך קורפוז תמיד מאשימים את "מלחמות כנופיות" כאילו הם לא אלה שמספקים את החום והעופרת ומלהיטים את העניינים? אין פלא, נכון? כולם יודעים את זה. אבל לקורפוז לשתול סוכנים בכל כנופיה גדולה ברחובות של נייט סיטי נשמע קצת כמו יתר על המידה,
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=91342 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1688, trans=1255, ratio=0.743
- **sentence count:** src=19, trans=22
- **EN source:**
```
Wassup dickbags and pussycaps- it's FR34K_S33K at your fuckin' service with some oh-so-fresh news. I be watching what strings those slender-ass corpo fingers be pulling, cuz if I don't do it, who the fuck will?\n\nSo you know how corps always blaming shit on "gang wars" like they ain't the ones fucking supplying the heat and lead and stirring up the beef? No surprise, right? Everyone know that. Bu
```
- **HE current:**
```
וואסאפ זבלים וזונות - זה FR34K_S33K לשירותכם עם חדשות טריות. אני עוקב אחרי החוטים האלה שאצבעות הקורפו הדקות שולפות, כי אם לא אני אז מי לעזאזל יעשה את זה?

אתם יודעים איך קורפוז תמיד מאשימים את "מלחמות כנופיות" כאילו הם לא אלה שמספקים את החום והעופרת ומלהיטים את העניינים? אין הפתעה, נכון? כולם יודעים את זה. אבל לקורפוז לשתול סוכנים בכל כנופיה גדולה ברחובות של נייט סיטי נשמע קצת כמו יתר על המידה, לא
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=85407 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1666, trans=1149, ratio=0.69
- **sentence count:** src=18, trans=27
- **EN source:**
```
The Collective (street name) - call themselves a group, in reality a borderline criminal & terrorist organization (find a good analogy/comparison for the opening - readers need specific references).\n\nParis, France, Europe (Paris - Eiffel Tower - make a reference!).\n\nMonarchist motifs (questionable - follow the money trail! - transfers, accounts in Switzerland, the parliament, Albanian mafia? -
```
- **HE current:**
```
הקולקטיב (שם רחוב) - קוראים לעצמם קבוצה, במציאות ארגון גבולי פלילי וטרוריסטי (מצא אנלוגיה/השוואה טובה לפתיחה - הקוראים צריכים התייחסויות ספציפיות).

פריז, צרפת, אירופה (פריז - מגדל אייפל - עשה הפניה!).

מוטיבים מונרכיסטיים (מנוגדים? עקוב אחר מסלול הכסף! - העברות, חשבונות בשוויץ, הפרלמנט, מאפיה אלבנית? - ארבע שורות של אנשי קשר; ממשלה, עסקים, מאפיה, קומוניסטים).

פעולות טרור בכל רחבי צרפת (תקשר לסעי
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=85393 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1631, trans=1218, ratio=0.747
- **sentence count:** src=13, trans=13
- **EN source:**
```
According to international law, space belongs to everybody – yes, yourself included. In practice however, it is controlled by three major players: Orbital Air, the European Space Council and the Highriders. The Keynan megacorporation has completely monopolized the market of commercial space travel and the ESC is focused on scientific exploration – for the good of all mankind, allegedly. And the Hi
```
- **HE current:**
```
לפי המשפט הבינלאומי, החלל שייך לכולם – כן, גם לך. בפועל, הוא נשלט על ידי שלושה שחקנים עיקריים: אורביטל אייר, מועצת החלל האירופית וההייריידרס. המגה-קורפורציה הקניאנית השתלטה לחלוטין על שוק הנסיעות המסחריות בחלל, והמועצה האירופית לחלל מתמקדת בחקר מדעי – לטובת כל האנושות, לכאורה. וההייריידרס? הם פשוט... בית. הם חיים בין הכוכבים ואינם מעוניינים במיוחד לקבל מבקרים, במיוחד כאלה שתובעים שהם יעזבו.

המתיח
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens.json · pk=85421 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1607, trans=1202, ratio=0.748
- **sentence count:** src=12, trans=17
- **EN source:**
```
Disgusting scop squeezed from tubes is (thankfully) a thing of the past. Freeze-dried food, once rehydrated and heated, is no different from the food served at your favorite Earth restaurant. Learn the facts and myths about  space diet!\n\nIn space, the diet must be rich in vitamin D and calcium.\nFACT: Shortages of sunlight in space mean that vitamin D has to be ingested in other ways (such as wi
```
- **HE current:**
```
גועל נפש סחוט מצינורות הוא (למזלנו) עבר זמננו. אוכל מיובש, לאחר שחזר והתחמם, אינו שונה מהאוכל שמגישים במסעדה האהובה עליך בכדור הארץ. למד את העובדות והמיתוסים על תזונה בחלל!

בחלל, התזונה חייבת להיות עשירה בוויטמין D וסידן.
עובדה: מחסור באור שמש בחלל פירושו שהוויטמין D צריך להילקח בדרכים אחרות (כמו עם אבקה של ביצים מבושלות מחברת Space Foods!). תוספת סידן, חיונית לשמירה על מסת עצם נורמלית, חשובה לא 
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

### `dlc` · ep1/onscreens/onscreens_final.json · pk=85421 · femaleVariant
- **signals:** MISSING_TERMINAL
- **length:** src=1607, trans=1207, ratio=0.751
- **sentence count:** src=12, trans=17
- **EN source:**
```
Disgusting scop squeezed from tubes is (thankfully) a thing of the past. Freeze-dried food, once rehydrated and heated, is no different from the food served at your favorite Earth restaurant. Learn the facts and myths about  space diet!\n\nIn space, the diet must be rich in vitamin D and calcium.\nFACT: Shortages of sunlight in space mean that vitamin D has to be ingested in other ways (such as wi
```
- **HE current:**
```
גועל נפש שנדחס מצינורות הוא (למזלנו) עבר זמניות. אוכל מיובש, לאחר השריה וחימום, אינו שונה מהאוכל המוגש במסעדת האהובה עליך בכדור הארץ. למד את העובדות והמיתוסים על תזונה בחלל!

בחלל, התזונה חייבת להיות עשירה בוויטמין D וסידן.
עובדה: מחסור באור שמש בחלל אומר שוויטמין D צריך להילקח בדרכים אחרות (כגון עם אבקה של ביצים מבושלות מחברת Space Foods!). תוספת סידן, חיונית לשמירה על מסת עצם נורמלית, חשובה לא פ
```
- **fix recommendation:** Likely OK content — add the missing terminal punct deterministically (no LM): if source ends with `.`, append `.` to the Hebrew; same for `!` and `?`.

