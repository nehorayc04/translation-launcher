import json

with open("current_batch.json", encoding="utf-8") as f:
    d = json.load(f)

translations = {
    '~z~A "patient". That\'s cheating code if ever I saw it. I\'m not stupid. Do I sound stupid to you?': '~z~"מטופלת". זה קוד לבגידה אם ראיתי כזה אי פעם. אני לא טיפשה. אני נשמעת לך טיפשה?',
    '~z~God damn it, he\'s seen us! Which part of "Keep our distance" did you not understand?': '~z~לעזאזל, הוא ראה אותנו! איזה חלק מ-"שמור מרחק" לא הבנת?',
    '~z~One time he didn\'t answer my calls, so I hid in the back of his car and put a bag over his head, shouting "See,': '~z~פעם אחת הוא לא ענה לשיחות שלי, אז התחבאתי בחלק האחורי של המכונית שלו ושמתי לו שקית על הראש, צועקת "תראה,',
    '~z~Very "now" stuff. But you\'ll be seeing a lot more of me very soon.': '~z~דברים מאוד "עכשוויים". אבל תראו הרבה יותר ממני מאוד בקרוב.',
    '~z~"Okay, guys, before I say anything, I want you to think "Shoulder of Orion" meets "Shore Whore.""': '~z~"אוקיי, חבר\'ה, לפני שאני אומרת משהו, אני רוצה שתחשבו "כתף של אוריון" פוגש את "זונת החוף.""',
    '~z~Man what happened to "no ties"? I\'ve dated girls I\'ve known less about than your ass at this point.': '~z~בן אדם מה קרה ל-"בלי קשרים"? יצאתי עם בנות שידעתי עליהן פחות ממה שאני יודע עליך בנקודה הזו.',
    '~z~Are you for real? So much for "clean and quiet." What the hell happened with the alarm?': '~z~אתה רציני? ככה הולך "נקי ושקט." מה לעזאזל קרה עם האזעקה?',
    '~z~Me? What happened to the "easiest money I\'ll ever make?"': '~z~אני? מה קרה ל-"הכסף הכי קל שאי פעם ארוויח?"',
    '~z~Everyone whispering, "Who is that guy?" I\'m Derrick and I\'m a shadow in the night.': '~z~כולם לוחשים, "מי זה הבחור?" אני דריק ואני צל בלילה.'
}

for k, v in translations.items():
    if k in d:
        d[k] = v
    else:
        print(f"KEY NOT FOUND: {k}")

with open("current_batch.json", "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=4)

# Verify
empty = [k for k, v in d.items() if not v]
print(f"Remaining empty: {len(empty)}")
