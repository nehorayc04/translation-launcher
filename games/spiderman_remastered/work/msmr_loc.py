"""MSMR localization codec (read side) + a decisive language classifier.

Shared by 02_loc_sections.py / 02b_verify_codec.py / 03_scope_report.py.

ASSET LAYOUT (verified empirically on all 23 variants)
  raw[0:36]   outer asset header:  u32 asset_type(0x122BB0AB 'localization')
                                   u32 payload_size (= len(raw)-36)
                                   28 x 0x00
  raw[36:]    DAT1 payload ('1TAD' on disk = 0x44415431 LE)

DAT1 (dat1lib/types/dat1.py layout)
  u32 magic, u32 unk1(asset type), u32 size, u16 nsections, u16 nunknowns
  nsections x { u32 tag, u32 offset, u32 size }        (offsets relative to DAT1)
  then a NUL-separated string blob up to the first section  ('Localization Built File')

SECTIONS — identical tag set to Spider-Man 2 / Ratchet & Clank Rift Apart
  0xD540A903  ENTRY_COUNT      4 B                 = N
  0x4D73CEBD  KEYS             NUL-separated UTF-8 key blob (alphabetical)
  0xA4EA55B2  KEY_OFFSETS      N x u32 -> KEYS
  0x70A382B8  VALUES           NUL-separated UTF-8 value blob   <-- PER LANGUAGE
  0xF80DEEB4  VALUE_OFFSETS    N x u32 -> VALUES                <-- PER LANGUAGE
  0x06A58050  HASHES           N x u32, entry order (key hash, algo unidentified)
  0xC43731B5  HASHES_SORTED    N x u32 = sorted(HASHES)
  0x0CD2CFE9  SORT_INDEX       N x u16, HASHES[SORT_INDEX[i]] == HASHES_SORTED[i]
  0xB0653243  RESERVED         N x u32, ~all zero

Only VALUES + VALUE_OFFSETS differ per language; everything else is byte-identical
across all 23 variants -> a Hebrew build copies the 7 shared sections verbatim and
never needs the key-hash algorithm.
"""
import os, struct
from collections import Counter

HDR = 36
DAT1_MAGIC = 0x44415431
TYPE_LOCALIZATION = 0x122BB0AB

T_HASHES      = 0x06A58050
T_SORT_INDEX  = 0x0CD2CFE9
T_KEYS        = 0x4D73CEBD
T_VALUES      = 0x70A382B8
T_KEY_OFFS    = 0xA4EA55B2
T_RESERVED    = 0xB0653243
T_HASHES_SORT = 0xC43731B5
T_COUNT       = 0xD540A903
T_VAL_OFFS    = 0xF80DEEB4

SECTION_NAMES = {
    T_HASHES: "HASHES", T_SORT_INDEX: "SORT_INDEX", T_KEYS: "KEYS",
    T_VALUES: "VALUES", T_KEY_OFFS: "KEY_OFFSETS", T_RESERVED: "RESERVED",
    T_HASHES_SORT: "HASHES_SORTED", T_COUNT: "ENTRY_COUNT", T_VAL_OFFS: "VALUE_OFFSETS",
}


class Loc:
    def __init__(self, path):
        self.path = path
        raw = open(path, "rb").read()
        self.raw = raw
        self.asset_type, self.payload_size = struct.unpack_from("<II", raw, 0)
        pay = raw[HDR:]
        self.pay = pay
        self.magic, self.unk1, self.size = struct.unpack_from("<III", pay, 0)
        nsec, nunk = struct.unpack_from("<HH", pay, 12)
        self.nunk = nunk
        self.sections = [struct.unpack_from("<III", pay, 16 + 12 * i) for i in range(nsec)]
        self.hdr_end = 16 + 12 * nsec + 8 * nunk
        self.min_off = min((o for _, o, _ in self.sections), default=len(pay))
        self.string_blob = pay[self.hdr_end:self.min_off]

    def seg(self, tag):
        for t, o, s in self.sections:
            if t == tag:
                return self.pay[o:o + s]
        return b""

    @property
    def n(self):
        return struct.unpack("<I", self.seg(T_COUNT))[0]

    def offsets(self, tag):
        return struct.unpack(f"<{self.n}I", self.seg(tag))

    def pairs(self):
        """[(key, value)] in entry order (duplicates of VALUE possible)."""
        n = self.n
        kb, vb = self.seg(T_KEYS), self.seg(T_VALUES)
        ko = struct.unpack(f"<{n}I", self.seg(T_KEY_OFFS))
        vo = struct.unpack(f"<{n}I", self.seg(T_VAL_OFFS))
        out = []
        for i in range(n):
            e = kb.find(b"\x00", ko[i]); k = kb[ko[i]: e if e >= 0 else len(kb)]
            e = vb.find(b"\x00", vo[i]); v = vb[vo[i]: e if e >= 0 else len(vb)]
            out.append((k.decode("utf-8", "replace"), v.decode("utf-8", "replace")))
        return out

    def value_offsets(self):
        return self.offsets(T_VAL_OFFS)


# ---------------------------------------------------------------- classifier
def char_classes(text):
    c = Counter()
    for ch in text:
        cp = ord(ch)
        if cp < 0x80: c["ascii"] += 1
        elif 0x0590 <= cp <= 0x05FF: c["hebrew"] += 1
        elif 0x0600 <= cp <= 0x06FF or 0xFB50 <= cp <= 0xFEFF: c["arabic"] += 1
        elif 0x0400 <= cp <= 0x04FF: c["cyrillic"] += 1
        elif 0x0370 <= cp <= 0x03FF or 0x1F00 <= cp <= 0x1FFF: c["greek"] += 1
        elif 0x3040 <= cp <= 0x309F: c["hiragana"] += 1
        elif 0x30A0 <= cp <= 0x30FF: c["katakana"] += 1
        elif 0xAC00 <= cp <= 0xD7AF or 0x1100 <= cp <= 0x11FF: c["hangul"] += 1
        elif 0x0E00 <= cp <= 0x0E7F: c["thai"] += 1
        elif 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF: c["cjk"] += 1
        elif 0x0100 <= cp <= 0x024F: c["latin_ext"] += 1
        elif 0x00C0 <= cp <= 0x00FF: c["latin1"] += 1
        else: c["other"] += 1
    return c


# Simplified-only vs Traditional-only characters (disjoint by construction)
CJK_SIMPL = "这来说时会开们过样对进车马长东门问题实点风间应务级给亲龙"
CJK_TRAD  = "這來說時會開們過樣對進車馬長東門問題實點風間應務級給親龍"

# DECISIVE diacritics: a character that (nearly) only this language uses.
DIACRITIC = {
    "polish":     "łąęśżźćń",
    "czech":      "čřžěůňťďáíéúý",
    "hungarian":  "őű",
    "turkish":    "ğışİ",
    "romanian":   "ăîâșț",
    "german":     "ß",
    "spanish":    "ñ¿¡",
    "portuguese": "ãõ",
    "danonor":    "æø",
    "swefin":     "åäö",
    "french":     "çêèùœâîôû",
    "italian":    "àèìòù",
}
# function words chosen to NOT collide with common English words
FUNC = {
    "english":    [" the ", " and ", " you ", " your ", " with ", " that ", " this ",
                   " for ", " have ", " from ", " will ", " can "],
    "german":     [" der ", " die ", " das ", " und ", " nicht ", " ist ", " ich ",
                   " ein ", " eine ", " mit ", " für ", " den "],
    "french":     [" les ", " des ", " vous ", " est ", " pour ", " une ", " dans ",
                   " qui ", " avec ", " sur ", " pas "],
    "italian":    [" gli ", " della ", " questo ", " sono ", " per ", " non ", " che ",
                   " una ", " nel ", " con "],
    "spanish":    [" los ", " para ", " que ", " con ", " una ", " por ", " del ",
                   " está ", " las "],
    "portuguese": [" para ", " não ", " uma ", " com ", " que ", " dos ", " está ",
                   " isso ", " você ", " mais "],
    "polish":     [" nie ", " jest ", " się ", " tego ", " oraz ", " przez ", " który "],
    "czech":      [" není ", " jsem ", " jsou ", " jako ", " nebo ", " která ", " při "],
    "dutch":      [" het ", " een ", " niet ", " voor ", " van ", " zijn ", " ook ",
                   " maar ", " met ", " je "],
    "danish":     [" ikke ", " af ", " mig ", " dig ", " være ", " der ", " som ",
                   " med ", " for "],
    "norwegian":  [" ikke ", " av ", " meg ", " deg ", " være ", " som ", " med ",
                   " for ", " på "],
    "swedish":    [" inte ", " och ", " att ", " för ", " med ", " som ", " det ",
                   " den ", " är "],
    "finnish":    [" että ", " ei ", " on ", " sinun ", " voit ", " kun ", " jos ",
                   "ssa ", "ssä ", "ään "],
    "hungarian":  [" nem ", " egy ", " van ", " hogy ", " meg ", " ezt ", " ami "],
    "turkish":    [" bir ", " için ", " değil ", " daha ", " olarak "],
    "romanian":   [" este ", " pentru ", " care ", " sunt ", " nu "],
}
# hard discriminators inside a diacritic family
DK_NO = {"danish": [" af ", " mig ", " dig ", " selv "],
         "norwegian": [" av ", " meg ", " deg ", " ikke "]}
SW_FI = {"swedish": [" och ", " inte ", " att ", " för "],
         "finnish": [" ja ", " ei ", " että ", "ssa ", "ssä "]}
ES_VAR = {"es_ES": [" vosotros ", " os ", "áis ", "éis ", " vuestro ", " ordenador "],
          "es_419": [" ustedes ", " computadora ", " celular ", " tomar "]}
# NOTE: " tem " / " está " / " pode " are 3rd person and shared by BOTH variants —
# using them made pt-PT read as pt-BR. Only 2nd-person "tu" forms + regional nouns
# are decisive (verified on MSMR variant_12 'TENS A CERTEZA?' vs variant_16 'TEM CERTEZA?').
PT_VAR = {"pt_PT": [" tu ", " tens ", " estás ", " podes ", " ecrã ", " telemóvel ",
                    " percebes ", " contigo ", " queres ", " fazes ", " vais "],
          "pt_BR": [" você ", " tela ", " celular ", " a gente ", " cara ", " tá ", " né "]}


def _score(joined, toks):
    return sum(joined.count(t) for t in toks)


def classify_language(strings, sample=8000):
    """Return (label, evidence dict). Evidence-based, no guessing."""
    text = "\n".join(strings)
    cc = char_classes(text)
    total = max(1, sum(cc.values()))
    ev = {"chars": dict(cc), "nonlatin_pct": round(
        100 * sum(cc[k] for k in ("hebrew", "arabic", "cyrillic", "greek", "hiragana",
                                  "katakana", "hangul", "thai", "cjk")) / total, 3)}

    # 1) non-latin scripts are decisive
    for k, lab in (("hebrew", "HEBREW"), ("arabic", "ARABIC"), ("cyrillic", "RUSSIAN"),
                   ("greek", "GREEK"), ("hangul", "KOREAN"), ("thai", "THAI")):
        if cc[k] > 500:
            return lab, ev
    if cc["hiragana"] + cc["katakana"] > 500:
        return "JAPANESE", ev
    if cc["cjk"] > 500:
        s = sum(text.count(ch) for ch in CJK_SIMPL)
        t = sum(text.count(ch) for ch in CJK_TRAD)
        ev["cjk_simpl"], ev["cjk_trad"] = s, t
        return ("CHINESE_SIMPLIFIED" if s > t else "CHINESE_TRADITIONAL"), ev

    # 2) latin family
    joined = " " + " ".join(strings[:sample]).lower().replace("\n", " ") + " "
    accent_density = (cc["latin_ext"] + cc["latin1"]) / total
    ev["accent_density"] = round(accent_density, 5)
    fscore = {name: _score(joined, toks) for name, toks in FUNC.items()}
    ev["func_scores"] = dict(sorted(fscore.items(), key=lambda x: -x[1])[:5])
    dscore = {name: sum(joined.count(ch) for ch in chars)
              for name, chars in DIACRITIC.items()}
    ev["diacritics"] = {k: v for k, v in sorted(dscore.items(), key=lambda x: -x[1]) if v}

    # ENGLISH: essentially no accents AND a dominant english function-word score
    if accent_density < 0.0015 and fscore["english"] >= max(
            v for k, v in fscore.items() if k != "english"):
        return "ENGLISH", ev

    # DECISIVE diacritic families
    if dscore["polish"] > 200:      return "POLISH", ev
    if dscore["hungarian"] > 200:   return "HUNGARIAN", ev
    if dscore["turkish"] > 200:     return "TURKISH", ev
    if dscore["romanian"] > 200:    return "ROMANIAN", ev
    if dscore["czech"] > 200 and fscore["czech"] >= fscore["english"] / 4:
        return "CZECH", ev
    if dscore["danonor"] > 200:
        a, b = _score(joined, DK_NO["danish"]), _score(joined, DK_NO["norwegian"])
        ev["dk_vs_no"] = {"danish": a, "norwegian": b}
        return ("DANISH" if a > b else "NORWEGIAN"), ev
    if dscore["spanish"] > 200:
        a, b = _score(joined, ES_VAR["es_ES"]), _score(joined, ES_VAR["es_419"])
        ev["es_variant"] = {"es_ES": a, "es_419": b}
        return ("SPANISH(es-ES)" if a >= b else "SPANISH(latam)"), ev
    if dscore["portuguese"] > 200:
        a, b = _score(joined, PT_VAR["pt_PT"]), _score(joined, PT_VAR["pt_BR"])
        ev["pt_variant"] = {"pt_PT": a, "pt_BR": b}
        return ("PORTUGUESE(pt-PT)" if a > b else "PORTUGUESE(pt-BR)"), ev
    if dscore["german"] > 200:      return "GERMAN", ev
    if dscore["swefin"] > 200:
        a, b = _score(joined, SW_FI["swedish"]), _score(joined, SW_FI["finnish"])
        ev["sv_vs_fi"] = {"swedish": a, "finnish": b}
        return ("SWEDISH" if a > b else "FINNISH"), ev
    if dscore["french"] > 200 and fscore["french"] > fscore["italian"]:
        return "FRENCH", ev
    if dscore["italian"] > 200:     return "ITALIAN", ev

    # 3) low-accent latin -> function words only (dutch etc.)
    ranked = sorted(fscore.items(), key=lambda x: -x[1])
    best, second = ranked[0], ranked[1]
    lab = best[0].upper()
    if second[1] and best[1] / max(1, second[1]) < 1.4:
        lab += f"?(vs {second[0]})"
    return lab, ev
