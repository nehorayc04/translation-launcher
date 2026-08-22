import json

with open('current_batch.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

fixes = {
    "base|onscreens/onscreens_final.json|92696": [('לחצי', 'לחץ')],
    "base|onscreens/onscreens_final.json|49089": [('את בטח תוהה', 'אתה בטח תוהה')],
    "base|onscreens/onscreens_final.json|42184": [('עובר עלייך', 'עובר עליך'), ('את חוזרת ומחרבנת', 'אתה חוזר ומחרבן')],
    "base|onscreens/onscreens_final.json|42197": [('לחצי', 'לחץ'), ('החזיקי', 'החזק')],
    "base|onscreens/onscreens_final.json|47944": [('תביסי', 'תביס')],
    "base|onscreens/onscreens_final.json|49430": [('בואי', 'בוא')],
    "base|onscreens/onscreens_final.json|42599": [('תראי', 'תראה'), ('אלייך', 'אליך'), ('את חולמת', 'אתה חולם'), ('את מריצה', 'אתה מריץ'), ('שאת יכולה', 'שאתה יכול')],
    "base|onscreens/onscreens_final.json|43113": [('גלי', 'גלה'), ('הפירומנית הפנימית', 'הפירומן הפנימי'), ('והציתי', 'והצת'), ('אויבייך', 'אויביך'), ('תטעני', 'תטען'), ('סמוראית', 'סמוראי')],
    "base|onscreens/onscreens_final.json|40407": [('את עושה', 'אתה עושה'), ('אחד לשנייה', 'אחד לשני')],
    "base|onscreens/onscreens_final.json|45239": [('תצטרכי', 'תצטרך')],
    "base|onscreens/onscreens_final.json|3947": [('את סובלת', 'אתה סובל')],
    "base|onscreens/onscreens_final.json|3950": [('תיודעי', 'תיודע')],
    "base|onscreens/onscreens_final.json|4633": [('את שואלת', 'אתה שואל')],
}

for k, v in d.items():
    if k in fixes:
        fm = v['he_female']
        for old, new in fixes[k]:
            fm = fm.replace(old, new)
        v['fixed_male'] = fm
    else:
        v['fixed_male'] = "SKIP"

with open('current_batch.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=1)

print("Batch fixes applied.")
