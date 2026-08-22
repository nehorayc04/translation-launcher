"""Print FULL logical + RTL visual for the 13 'real defect' candidates, paragraph
by paragraph, so we can hand-judge whether each reads correctly RTL."""
import json, os, re
from bidi.algorithm import get_display
HERE=os.path.dirname(os.path.abspath(__file__))
RLM="‏"
def has_heb(s): return any("א"<=c<="ת" for c in s)
def strip(s):
    s=re.sub(r"<[^>]+>","",s); s=re.sub(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;","",s); return s
def visline(s,b): return get_display(s,base_dir=b)

KEYS=['HELP_FNSM_SWITCH_MILES_MKB','HELP_PROWLERTECH_CIRCUITBOXES',
'HELP_PROWLERTECH_CIRCUITBOXES_MKB','SETTING_3D_AUDIO_ENABLED_DESC_PC',
'SETTING_AUDIO_OUTPUT_DEVICE_DESC','SETTING_PHOTOCOLLECTUSEPLAYERPHOTO_DESC',
'SETTING_TRICKMODE_OPTION_AUTO_DESC','SETTING_TRICKMODE_OPTION_MAINTAIN_DESC',
'SKILL_WEBWHIP_DESC','MENU_ENGLISH_VO_DESC','TEXT_CONNECT_TO_PSN_BODY',
'AUDIO_CONTROLLER_AUDIOHAPTICS_ENABLED_DESC','PCDISPLAYSETTINGS_FRAMEGEN_DESC']

descs={}
for fn in ["settings_he.json"]+[f"menus{n}_he.json" for n in range(2,14)]+["menus_he.json"]:
    p=os.path.join(HERE,fn)
    if not os.path.exists(p): continue
    for k,v in json.load(open(p,encoding="utf-8")).items():
        descs.setdefault(k,v) if False else None
        if isinstance(v,str): descs.setdefault(k,v)

for k in KEYS:
    raw=descs.get(k)
    if not raw: print(f"### {k}: NOT FOUND"); continue
    t=strip(raw[len(RLM):] if raw.startswith(RLM) else raw)
    print(f"### {k}")
    # split into UBA paragraphs and render each — note count of paragraphs
    paras=re.split(r"[\n\r]",t)
    print(f"   paragraphs (split on \\n\\r): {len(paras)}")
    for i,para in enumerate(paras):
        vr=visline(RLM+para,"R").replace(RLM,"")
        # the rightmost ~5 chars of the visual = what is read FIRST (RTL)
        print(f"   [P{i}] LOGICAL: {para}")
        print(f"        RTLVIS : {vr}")
        # what reads first (right edge) vs the logical start
        logical_start=para.lstrip()[:12]
        print(f"        logical-starts: {logical_start!r}   visual-right-edge: {vr[-14:]!r}")
    print()
