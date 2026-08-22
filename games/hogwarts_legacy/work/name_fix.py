# -*- coding: utf-8 -*-
r"""name_fix.py — enforce SPELL/creature transliteration consistency in hebrew.json.

The game's OWN Arabic transliterates spells (Accio->آكيو, Descendo->ديسيندو), so the
correct policy is to transliterate; the fleet did it INCONSISTENTLY. We measure the
fleet's OWN canonical Hebrew from its atomic single-word entries ([[glossary-measure-
then-correct]]) and enforce it on lines that left the spell Latin. Brands/tech/legal/
product-titles stay Latin. Genuine unresolved names (Crossed Wands, English-echo bugs)
are re-queued to the fleet — Claude never invents a transliteration ([[delegate-all-translation]]).

  python name_fix.py            # REPORT only (buckets + name_requeue_keys.json)
  python name_fix.py --apply    # + rewrite the fixable lines into hebrew.json (backup)
"""
import argparse, json, re, shutil, time
from pathlib import Path
from collections import Counter, defaultdict
HERE=Path(__file__).resolve().parent; EX=HERE.parent/"extract"
HE_PATH=HERE/"hebrew.json"
me=json.loads((EX/"main_en.json").read_text(encoding="utf-8")); se=json.loads((EX/"sub_en.json").read_text(encoding="utf-8"))
def en(k): p,b=k.split(":",1); return (me if p=="MAIN" else se).get(b)
HEB=re.compile(r"[\u0590-\u05ff]"); LAT=re.compile(r"[A-Za-z]")
STRIP=re.compile(r"</?i>|</?b>|[!?.,]|\u200f")
ENWORD=re.compile(r"^[A-Za-z][A-Za-z'\-]+$"); HEBWORD=re.compile(r"^[\u0590-\u05ea'\u05f3\u05f4\"\- ]+$")

# brands / tech / legal / UI / product-titles / ICU-syntax that STAY Latin (not defects)
KEEP={
 "WB","Games","GAMES","NVIDIA","Nvidia","AMD","CurseForge","FSR","Nintendo","DLSS",
 "DualSense","DUALSHOCK","Intel","XeSS","TGAS","Reflex","Inc","eShop","GPU","HDR",
 "Switch","PS","QR","NIS","Unreal","Epic","PlayStation","HUD","EULA","Warner","Bros",
 "Entertainment","Technology","USB","VSYNC","https","http","Code","RR","Numpad","HE",
 "Legacy","HOLD","TAP","PRESS","ON","OFF","Body_Text","plural","one","other","select",
 "Xbox","Steam","Denuvo","FidelityFX","CAS","DLAA","TAA","FXAA","SSAO","VRAM","FPS","Hz",
 "II","III","IV","VI","VII","VIII","IX","XI","XII","and","The","J","T",
 # NON-spell words the fleet also has a Hebrew for, but which are wrong to replace inline:
 "Hogwarts","Wands","Crossed","Tools","Frame","Generation","Resolution","Potion","Potions",
 "Thunderbrew","Modding","Mods","Kit","Creator",
}
# first-consonant phonetic map: a genuine transliteration shares its initial sound
# (Accio->אקיו a~א), a translation does not (Wands->שרביטים W!=ש). Kills word-translations.
PHON={"a":"אע","b":"בו","c":"קסצ","d":"ד","e":"אע","f":"פ","g":"גז","h":"הח","i":"אי",
      "j":"גז","k":"קכ","l":"ל","m":"מ","n":"נ","o":"אוע","p":"פ","q":"ק","r":"ר",
      "s":"סשצז","t":"תטצ","u":"אוע","v":"ובו","w":"ו","x":"זסקא","y":"יא","z":"ז"}
def phon_ok(en_tok, heb):
    e=en_tok[0].lower(); h=heb[0]
    return e not in PHON or h in PHON[e]
ROMAN=re.compile(r"^[IVXLC]+$")
KEYNAME=re.compile(r"_Pronunciation$")   # keyboard-key labels: never touch, never learn from
def heblen(s): return len(re.findall(r"[֐-ת]",s))
# protected spans where Latin must NEVER be touched
PROT=re.compile(r"<[^>]+>|\{[^}]*\}|\[\[.*?\]\]|\[[^\]]*\]|&[a-z]+;|%[#0-9.\*\-\+ ]*[a-zA-Z]"
                r"|\|plural\([^)]*\)|\([A-Z]{2,}\)|https?://\S+")
LATWORD=re.compile(r"[A-Za-z][A-Za-z'\-]*[A-Za-z]|[A-Za-z]")

def build_gloss(he):
    # 1-word atomic transliterations, majority vote, spells/creatures only (not KEEP,
    # not keyboard-key labels), and ONLY when the Hebrew is a plausible TRANSLITERATION
    # (length ratio 0.55-1.7, dominant form) so mistranslations like Disillusionment->
    # אכזבה or Alt->תיק can never enter the map.
    cand=defaultdict(Counter)
    for k,v in he.items():
        if not isinstance(v,str) or not HEB.search(v) or KEYNAME.search(k): continue
        ev=en(k)
        if not ev: continue
        ec=STRIP.sub("",ev).strip(); hc=STRIP.sub("",v).strip()
        if ENWORD.match(ec) and ec not in KEEP and not ROMAN.match(ec) and HEBWORD.match(hc) and hc:
            cand[ec][hc]+=1
    g={}
    for t,c in cand.items():
        heb,n=c.most_common(1)[0]
        total=sum(c.values())
        if n/total < 0.6:                    # ambiguous -> don't trust
            continue
        if " " in heb:                       # single-word translit only (no multi-word translations)
            continue
        r=heblen(heb)/max(1,len(t))
        if 0.55 <= r <= 1.7 and phon_ok(t,heb):   # plausible translit AND shares initial sound
            g[t]=heb
    return g

PREFIX=re.compile(r"(?<![֐-ת])([ובלמהשכ])-(?=[֐-ת])")
def merge_prefix(s):  # ה-אקיו -> האקיו (Hebrew prefix + hyphen + Hebrew word)
    return PREFIX.sub(r"\1", s)

def prose_segments(s):
    """yield (text, is_prose) splitting out protected spans."""
    i=0
    for m in PROT.finditer(s):
        if m.start()>i: yield s[i:m.start()], True
        yield m.group(0), False
        i=m.end()
    if i<len(s): yield s[i:], True

def main(apply):
    he=json.loads(HE_PATH.read_text(encoding="utf-8"))
    gloss=build_gloss(he)
    fixable={}   # k -> new value
    requeue=[]   # k needing fleet redo
    leave=0      # only brands / roman / syntax
    echo=0
    for k,v in he.items():
        if not isinstance(v,str) or not HEB.search(v) or KEYNAME.search(k): continue
        # english-echo bug: "<English...>\n<Hebrew...>" where line1 has no Hebrew
        if "\n" in v:
            first=v.split("\n",1)[0]
            if LAT.search(first) and not HEB.search(first) and len(first.strip())>3:
                echo+=1; requeue.append(k); continue
        # walk prose, replace known spells, flag unknowns
        out=[]; unknown=False; changed=False; had_latin=False
        for seg,is_prose in prose_segments(v):
            if not is_prose: out.append(seg); continue
            def repl(m):
                nonlocal unknown,changed,had_latin
                w=m.group(0); wc=w.strip("'-")
                if not LAT.search(w): return w
                had_latin=True
                if wc in KEEP or ROMAN.match(wc): return w
                if wc in gloss:
                    changed=True; return gloss[wc]
                unknown=True; return w
            out.append(LATWORD.sub(repl, seg))
        if not had_latin:
            continue
        if unknown:
            requeue.append(k)
        elif changed:
            fixable[k]=merge_prefix("".join(out))
        else:
            leave+=1   # only brands/roman/syntax -> not a defect
    requeue=sorted(set(requeue))
    print(f"gloss size (spells/creatures): {len(gloss)}")
    print(f"residual lines classified:")
    print(f"  FIXABLE (spell->Hebrew, deterministic): {len(fixable)}")
    print(f"  LEAVE   (only brand/roman/ICU-syntax):  {leave}")
    print(f"  ECHO    (English echo bug -> requeue):  {echo}")
    print(f"  REQUEUE (unknown name -> fleet redo):   {len(requeue)-echo}")
    print("\nsample FIXABLE:")
    for k in list(fixable)[:10]:
        print(f"  {k}\n    - {he[k][:80]!r}\n    + {fixable[k][:80]!r}")
    (HERE/"name_requeue_keys.json").write_text(json.dumps(requeue,ensure_ascii=False,indent=1),encoding="utf-8")
    print(f"\nwrote name_requeue_keys.json ({len(requeue)})")
    if apply and fixable:
        bak=HE_PATH.with_suffix(f".json.bak.name.{time.strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(HE_PATH,bak)
        for k,nv in fixable.items(): he[k]=nv
        HE_PATH.write_text(json.dumps(he,ensure_ascii=False,indent=1),encoding="utf-8")
        print(f"APPLIED {len(fixable)} spell fixes (backup {bak.name})")

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--apply",action="store_true")
    main(ap.parse_args().apply)
