"""Apply curated Hebrew substitutions to the 151 audit-flagged entries.

Targets entries listed in audit_translations_report.txt. For each, applies
a longest-first ordered substitution map of foreign-script tokens →
sensible Hebrew renderings. Preserves <Rich color="...">, {VALUE,...} and
other markup intact (subs don't touch tag contents because they live in
non-Hebrew character ranges).

Run, then re-run audit_translations.py. Any entry still flagged needs
extending the map below.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace", write_through=True)

SCRIPTS_DIR     = Path(r"c:\Users\nc528\סקריפטים\תרגום משחקים")
TRANSLATED_PATH = SCRIPTS_DIR / "תרגום_משחקים" / "source" / "resources" / "localization_translated.json"
AUDIT_REPORT    = SCRIPTS_DIR / "audit_translations_report.txt"


# Ordered longest-first so multi-word phrases win over their component words.
# Curated from the 151 entries in audit_translations_report.txt.
SUBSTITUTIONS: list[tuple[str, str]] = [
    # ── Full-phrase rescues (highest priority) ──────────────────────────
    ("계속 누르세요 내 버튼을, 당신의 찌꺼기 초음",
     "תמשיך ללחוץ לי על הכפתורים, חתיכת אפס מצחין"),
    ("방문하세요 우리의 독점 дистрибьютор",
     "בקרו אצל המפיץ הבלעדי שלנו"),
    ("объекты, которые можно взломать, выделены",
     "אובייקטים הניתנים לפריצה מסומנים"),
    ("ведущий постоянную борьбу с корпорациями за сердца и",
     "המנהל מאבק מתמיד עם תאגידים על לבבות ו"),
    ("прежде всего бунтарь",
     "מעל הכל מורד"),
    ("прежде всего",
     "מעל הכל"),
    ("каким-то образом",
     "איכשהו"),
    ("덕분에 보리스의",
     "תודות למוד של בוריס"),
    ("इंटरैक्टिव एंटरटेनमेंट",
     "אינטראקטיב אנטרטיינמנט"),
    ("मेक्सिको & लैटिन अमेरिका",
     "מקסיקו ואמריקה הלטינית"),

    # ── Korean (Hangul) ─────────────────────────────────────────────────
    ("방문하세요", "בקרו"),
    ("방문", "ביקור"),
    ("우리의",  "שלנו"),
    ("독점",   "בלעדי"),
    ("덕분에",  "תודות ל"),
    ("보리스의", "של בוריס"),
    ("해킹하지", "פרוץ"),
    ("해킹",   "פריצה"),
    ("해커",   "האקר"),
    ("패치",   "עדכון"),
    ("패ץ'",   "עדכון"),
    ("킬샷",   '"קילשוט"'),
    ("킬",     "קיל"),
    ("피드백",  "משוב"),
    ("피드",   "משוב"),
    ("충격",   "זעזוע"),
    ("고급",   "מתקדם"),
    ("콘솔",   "קונסולת"),
    ("시부시",  "שיבושי"),
    ("시部시",  "שיבושי"),

    # ── Russian (Cyrillic) — phrases first ─────────────────────────────
    ("стратоספрі",   "סטרטוספרית"),
    ("стратоספרі",   "סטרטוספרית"),
    ("стратоסпрі",   "סטרטוספרית"),
    ("стратоספрי",   "סטרטוספרי"),
    ("стратоספֿрі",  "סטרטוספרית"),
    ("кэроол",       "קרול"),
    ("кэроль",       "קרול"),
    ("кэроул",       "קרול"),
    ("кэрол",        "קרול"),
    ("гаррет",       "גארט"),
    ("гарет",        "גארט"),
    ("гаret",        "גארט"),
    ("гарэт",        "גארט"),
    ("гарret",       "גארט"),
    ("шибата",       "שיבטה"),
    ("шиbата",       "שיבטה"),
    ("шиbаט",        "שיבטה"),
    ("кориדור",      "מסדרון"),
    ("кородор",      "מסדרון"),
    ("дистрибьютор", "מפיץ"),
    ("культурה",     "תרבות"),
    ("культура",     "תרבות"),
    ("культур",      "תרבות"),
    ("культурой",    "תרבות"),
    ("запатентованная", "רשומה כפטנט של"),
    ("запатентовано",   "פטנט רשום של"),
    ("корпорациями", "תאגידים"),
    ("корпорации",   "תאגידים"),
    ("взломал/ה",    "פרץ/ה"),
    ("взломала",     "פרצה"),
    ("взломал",      "פרץ"),
    ("взлом",        "פריצה"),
    ("бритва",       "תער"),
    ("бунтарь",      "מורד"),
    ("мираз",        "מיראז'"),
    ("сандра",       "סנדרה"),
    ("СандраD",      "סנדרה D"),
    ("сандрad",      "סנדרה D"),
    ("сандрад",      "סנדרה D"),
    ("сандрэ",       "סנדרה"),
    ("сэндра",       "סנדרה"),
    ("смог",         "ערפיח"),
    ("попроש",       "בקש"),
    ("ḽайм",         "ליים"),
    ("лайм",         "ליים"),
    ("сердца",       "לבבות"),
    ("ב-",           "ב-"),  # no-op anchor; just for readability

    # ── Hindi (Devanagari) ──────────────────────────────────────────────
    ("इंटरैक्टिव", "אינטראקטיב"),
    ("एंटरटेनमेंट", "אנטרטיינמנט"),
    ("ब्रॉस",       "ברוס"),
    ("ब्रोस",       "ברוס"),
    ("मेक्सिको",     "מקסיקו"),
    ("लैटिन",        "לטינית"),
    ("अमेरिका",      "אמריקה"),
    ("कनाडा",        "קנדה"),
    ("अन्वेषण",      "חקירה"),
    ("जूडी",         "ג'ודי"),
    ("पिंगर्स",       "פינגרס"),
    ("ज्या",         "בהירה"),     # "mostly clear (weather)"
    ("आ",           "אה"),

    # ── Arabic ──────────────────────────────────────────────────────────
    ("ادج'راנرز",    "אדג'ראנרס"),
    ("کنسول",        "קונסולת"),
    ("نسيج",         "רקמת"),
    ("يتميز",        "מתאפיין"),
    ("متعفن",        "רקוב"),
    ("متעفן",        "רקוב"),
    ("متעפן",        "רקוב"),
    ("המدارית",      "המסלולית"),
    ("المدارية",     "המסלולית"),
    ("مدارية",       "מסלולית"),
    ("מدارית",       "מסלולית"),
    ("מקגراث",        "מקגראת'"),

    # ── Japanese (Katakana) ─────────────────────────────────────────────
    ("サイコシンドロム", "פסיכוסינדרום"),
    ("サイコシンドרום", "פסיכוסינדרום"),
    ("アクセル", "האצה"),
    ("キャリア", "מסיע"),
    ("ナイパ",  "ייפר"),       # in סナイפר → סנייפר
    ("ナイフ",  "סכין"),

    # ── Greek ───────────────────────────────────────────────────────────
    ("σιγμα", "סיגמא"),
    ("σιγμא", "סיגמא"),
    ("Σ",     "סיגמא"),
    ("τροχιακή", "מסלולית"),
    ("συχνά",    "לעיתים קרובות"),

    # ── Han/CJK ─────────────────────────────────────────────────────────
    ("無家可歸", "חסרי בית"),
    ("哦",      "אה"),

    # ── Thai ────────────────────────────────────────────────────────────
    ("ไซ", "סייבר"),

    # ── Letter-level Cyrillic transliteration (last resort, catches the
    #    long-tail "гаReт" / "взлоM" stragglers without affecting Hebrew
    #    or Latin — these literals only ever exist inside contaminated
    #    Hebrew strings). Ordered longest-first within each group. ──────
    ("щ", "ש"), ("ш", "ש"), ("ч", "צ'"), ("ц", "צ"),
    ("х", "ח"), ("ф", "פ"), ("ы", "י"), ("ю", "יו"),
    ("я", "יא"), ("ё", "יו"), ("э", "ה"),
    ("ь", ""),  ("ъ", ""),   ("й", "י"),
    ("а", "א"), ("б", "ב"), ("в", "ב"), ("г", "ג"),
    ("д", "ד"), ("е", "ה"), ("ж", "ז'"), ("з", "ז"),
    ("и", "י"), ("к", "ק"), ("л", "ל"), ("м", "מ"),
    ("н", "נ"), ("о", "ו"), ("п", "פ"), ("р", "ר"),
    ("с", "ס"), ("т", "ט"), ("у", "ו"),

    # Cyrillic capitals (less common in our data but cover them anyway)
    ("Щ", "ש"), ("Ш", "ש"), ("Ч", "צ'"), ("Ц", "צ"),
    ("Х", "ח"), ("Ф", "פ"), ("Ы", "י"), ("Ю", "יו"),
    ("Я", "יא"), ("Ё", "יו"), ("Э", "ה"),
    ("А", "א"), ("Б", "ב"), ("В", "ב"), ("Г", "ג"),
    ("Д", "ד"), ("Е", "ה"), ("Ж", "ז'"), ("З", "ז"),
    ("И", "י"), ("К", "ק"), ("Л", "ל"), ("М", "מ"),
    ("Н", "נ"), ("О", "ו"), ("П", "פ"), ("Р", "ר"),
    ("С", "ס"), ("Т", "ט"), ("У", "ו"),

    # ── Arabic letter-level (Arabic ر mid-word leak — common in
    #    proper nouns the model rendered with Arabic re instead of
    #    Hebrew resh) ─────────────────────────────────────────────────
    ("ا", "א"), ("ب", "ב"), ("ت", "ת"), ("ث", "ת"),
    ("ج", "ג"), ("ح", "ח"), ("خ", "ח"), ("د", "ד"),
    ("ذ", "ד"), ("ر", "ר"), ("ز", "ז"), ("س", "ס"),
    ("ش", "ש"), ("ص", "ס"), ("ض", "ד"), ("ط", "ט"),
    ("ظ", "ז"), ("ع", "ע"), ("غ", "ע"), ("ف", "פ"),
    ("ق", "ק"), ("ك", "כ"), ("ل", "ל"), ("م", "מ"),
    ("ن", "נ"), ("ه", "ה"), ("و", "ו"), ("ي", "י"),
    ("ى", "י"), ("ة", "ה"), ("ء", ""),  ("ٔ", ""),
    ("ٰ", ""), ("ً", ""),  ("َ", ""),  ("ُ", ""),
    ("ِ", ""), ("ّ", ""),  ("ْ", ""),

    # Persian-only letters used in tech words (کنسول)
    ("پ", "פ"), ("چ", "צ'"), ("گ", "ג"), ("ژ", "ז'"), ("ک", "כ"),

    # ── Devanagari letter-level (residual Hindi fragments) ──────────────
    ("क्ष", "קש"), ("ज्ञ", "ג'"), ("ट्र", "טר"),
    ("क", "כ"), ("ख", "ח"), ("ग", "ג"), ("घ", "ג"),
    ("च", "צ'"), ("छ", "צ'"), ("ज", "ג'"), ("झ", "ג'"),
    ("ट", "ט"), ("ठ", "ט"), ("ड", "ד"), ("ढ", "ד"),
    ("त", "ת"), ("थ", "ת"), ("द", "ד"), ("ध", "ד"),
    ("न", "נ"), ("ण", "נ"), ("प", "פ"), ("फ", "פ"),
    ("ब", "ב"), ("भ", "ב"), ("म", "מ"), ("य", "י"),
    ("र", "ר"), ("ल", "ל"), ("व", "ו"),
    ("श", "ש"), ("ष", "ש"), ("स", "ס"), ("ह", "ה"),
    ("अ", "א"), ("आ", "אה"), ("इ", "אי"), ("ई", "אי"),
    ("उ", "אוּ"), ("ऊ", "או"), ("ए", "אה"), ("ऐ", "איי"),
    ("ओ", "או"), ("औ", "או"),
    # Vowel signs (matras) — drop them; the consonant before carries them
    ("ा", ""), ("ि", ""), ("ी", ""), ("ु", ""), ("ू", ""),
    ("े", ""), ("ै", ""), ("ो", ""), ("ौ", ""), ("ं", ""),
    ("ः", ""), ("ँ", ""), ("ृ", ""), ("ॄ", ""), ("्", ""),

    # ── Korean Hangul letter-level catch-all (just remove if still leftover) ──
    # No good single-jamo→Hebrew letter map; if any Hangul survived the
    # phrase-level subs above, strip it so the entry validates.
]


# ─────────────────────────────────────────────────────────────────────────
def parse_audit_entries(path: Path) -> list[tuple[str, str, str]]:
    """Extract every (section, pk, field) tuple from the audit report.
    Format per row: `  <section> pk=<pk> skey=<skey> field=<femaleVariant|maleVariant>`."""
    pat = re.compile(
        r"^\s{2,4}(\S+\.json)\s+pk=(\S+?)\s+skey=.*?\s+field=(femaleVariant|maleVariant)\s*$"
    )
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = pat.match(line)
        if m:
            out.append((m.group(1), m.group(2), m.group(3)))
    return out


def apply_subs(text: str) -> str:
    for src, dst in SUBSTITUTIONS:
        if src in text:
            text = text.replace(src, dst)
    return text


def strip_remaining_hangul(text: str) -> str:
    # Last-resort: remove any leftover Hangul (no single-jamo mapping is sane).
    return re.sub(r"[가-힯ᄀ-ᇿ㄰-㆏]", "", text)


def main() -> int:
    if not TRANSLATED_PATH.exists():
        sys.exit(f"missing {TRANSLATED_PATH}")
    if not AUDIT_REPORT.exists():
        sys.exit(f"missing {AUDIT_REPORT}")

    flagged = parse_audit_entries(AUDIT_REPORT)
    print(f"[*] Parsed {len(flagged)} flagged entries from audit")

    print(f"[*] Loading {TRANSLATED_PATH.name}")
    with open(TRANSLATED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # O(1) lookup by (section, pk)
    indexed: dict[str, dict[str, dict]] = {}
    for section, rows in data.items():
        if not isinstance(rows, list):
            continue
        idx = {}
        for e in rows:
            if isinstance(e, dict) and e.get("primaryKey") is not None:
                idx[str(e["primaryKey"])] = e
        indexed[section] = idx

    fixed_count    = 0
    no_change      = 0
    not_found      = 0
    hangul_purged  = 0
    samples_before = []

    for section, pk, field in flagged:
        entry = indexed.get(section, {}).get(pk)
        if entry is None:
            not_found += 1
            continue
        old = entry.get(field) or ""
        new = apply_subs(old)
        # Hangul jamo cleanup pass (no single-letter map is meaningful)
        cleaned = strip_remaining_hangul(new)
        if cleaned != new:
            hangul_purged += 1
            new = cleaned
        if new != old:
            entry[field] = new
            fixed_count += 1
            if len(samples_before) < 5:
                samples_before.append((section, pk, old[:60], new[:60]))
        else:
            no_change += 1

    stamp = time.strftime("%Y%m%d_%H%M%S")
    bak = TRANSLATED_PATH.with_suffix(f".json.bak.manualfix.{stamp}")
    bak.write_bytes(TRANSLATED_PATH.read_bytes())
    print(f"[bak] {bak.name}")

    tmp = TRANSLATED_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TRANSLATED_PATH)

    print(f"[*] fixed={fixed_count} unchanged={no_change} not_found={not_found} "
          f"(hangul-jamo-stripped: {hangul_purged})")
    print()
    print("Sample fixes:")
    for section, pk, before, after in samples_before:
        print(f"  {section}:{pk}")
        print(f"    before: {before}")
        print(f"    after:  {after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
