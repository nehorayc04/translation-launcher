#!/usr/bin/env python3
"""build_full_gxt2.py — build the WHOLE-GAME Hebrew american_rel (all 610 gxt2).

The UI beta translated only global.gxt2 (the menu/HUD table). This builds the FULL
text layer: every one of the 610 gxt2 files inside american_rel.rpf (global + all
per-mission / per-area subtitle + dialogue tables), translated EN->Hebrew, gloss-
stripped, visual-reversed, byte-faithful.

Translation sources (both keyed by the ENGLISH source string):
  * agent_handoff_full/reuse_he.json          — 49,521 EN->HE reused from the UI run
  * agent_handoff_full/chunks/he_*.json        — the new dialogue/subtitle translations
                                                  the Gemini agent writes (300 each).
Untranslated keys (names/codes/still-pending) stay vanilla English = a clean fallback,
so the build is always shippable at whatever coverage exists.

Per source file: read_gxt2 -> for each (hash, EN) replace with visual_line(strip_gloss)
when a translation exists -> write_gxt2 -> work/full_build/american_rel/<name>.gxt2.

  python build_full_gxt2.py            # build all 610 + coverage report
  python build_full_gxt2.py --oiv      # + assemble the FULL install/restore OIVs
"""
import json, os, re, sys, uuid, zipfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gtav_gxt2 as G

HERE = os.path.dirname(os.path.abspath(__file__))
GTAV = os.path.normpath(os.path.join(HERE, ".."))
SRC_DIR = os.path.join(GTAV, "_fonts_src", "american_rel.rpf")          # 610 vanilla gxt2
AH = os.path.join(GTAV, "agent_handoff_full")
REUSE = os.path.join(AH, "reuse_he.json")
HEBREW = os.path.join(AH, "hebrew.json")          # loop accumulator {EN: HE}
CHUNKS = os.path.join(AH, "chunks")
STAGE = os.path.join(HERE, "full_build", "american_rel")
REL = os.path.join(GTAV, "release")
GAME = r"F:\Games\Grand Theft Auto V Legacy"
ORIG = os.path.join(GTAV, "_originals")

HEB = re.compile("[א-ת]")
LAT = re.compile("[A-Za-z]")
PAR = re.compile(r"\s*\(([^()]+)\)")
TOK = re.compile(r"~[^~]*~|</?[A-Za-z][^>]*>|%[0-9]*[sdifx%]")  # GTA tokens/tags/printf


def _toks(s):
    return sorted(TOK.findall(s))


def strip_gloss(he, en):
    """Remove agent-added Latin-only '(English)' glosses. Identical rule to
    build_superset.strip_gloss (kept in lockstep): literal whole-source removal first
    (nested-paren safe), then per-paren Latin-only removal; revert if all Hebrew lost."""
    out = he
    ens = (en or "").strip()
    if ens and HEB.search(out):
        for g in (" (" + ens + ")", "(" + ens + ")"):
            if g in out:
                out = out.replace(g, "")

    def repl(m):
        inner = m.group(1)
        if any(c in inner for c in "~<>%"):
            return m.group(0)
        if not LAT.search(inner) or HEB.search(inner):
            return m.group(0)
        if ("(" + inner + ")") in en:
            return m.group(0)
        return ""

    out = PAR.sub(repl, out)
    if not HEB.search(out):
        return he
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([.,!?:;])", r"\1", out)
    return out.strip()


def load_translations():
    """EN-source -> logical Hebrew, merged from reuse + every he_*.json chunk
    (chunks win on the rare overlap). Empty values are dropped (still untranslated)."""
    tr = {}
    if os.path.isfile(REUSE):
        for en, he in json.load(open(REUSE, encoding="utf-8")).items():
            if str(he).strip():
                tr[en] = he
    # legacy he_*.json chunks (folded into hebrew.json, kept for safety/back-compat)
    n_chunks = 0
    if os.path.isdir(CHUNKS):
        for fn in sorted(os.listdir(CHUNKS)):
            if not (fn.startswith("he_") and fn.endswith(".json")):
                continue
            try:
                d = json.load(open(os.path.join(CHUNKS, fn), encoding="utf-8"))
            except Exception as e:
                print(f"  !! skip {fn}: {e}")
                continue
            n_chunks += 1
            for en, he in d.items():
                if str(he).strip():
                    tr[en] = he
    # the live loop accumulators win over everything: hebrew.json + any per-slot
    # hebrew_<N>.json (parallel-agent outputs).
    import glob as _glob
    n_heb = 0
    acc = [HEBREW] + sorted(_glob.glob(os.path.join(AH, "hebrew_*.json")))
    for path in acc:
        if not os.path.isfile(path):
            continue
        for en, he in json.load(open(path, encoding="utf-8")).items():
            if str(he).strip():
                tr[en] = he
                n_heb += 1
    print(f"translations: reuse + {n_chunks} chunks + {len(acc)} accum({n_heb:,}) -> {len(tr):,} EN->HE")
    return tr


def build_all():
    tr = load_translations()
    os.makedirs(STAGE, exist_ok=True)
    files = sorted(f for f in os.listdir(SRC_DIR) if f.endswith(".gxt2"))
    tot_entries = tot_tr = tot_en = 0
    deviations = []                                                      # token-multiset drift
    for fn in files:
        src = G.read_gxt2(open(os.path.join(SRC_DIR, fn), "rb").read())   # {hash: EN}
        out = {}
        for h, en in src.items():
            he = tr.get(en)
            if he is not None:
                if _toks(he) != _toks(en):
                    deviations.append({"file": fn, "en": en, "he": he,
                                       "en_tok": _toks(en), "he_tok": _toks(he)})
                out[h] = G.visual_line(strip_gloss(he, en))
                tot_tr += 1
            else:
                out[h] = en                                              # vanilla fallback
                if HEB.search(en):                                       # already-He (shared)
                    tot_tr += 1
                else:
                    tot_en += 1
            tot_entries += 1
        data = G.write_gxt2(out)
        assert G.read_gxt2(data) == out, fn                              # round-trip guard
        open(os.path.join(STAGE, fn), "wb").write(data)
    pct = 100.0 * tot_tr / tot_entries if tot_entries else 0
    print(f"built {len(files)} files | entries={tot_entries:,} "
          f"translated/he={tot_tr:,} ({pct:.1f}%) english-fallback={tot_en:,}")
    # de-dup deviations by EN (a string recurs across files) and report.
    uniq = {d["en"]: d for d in deviations}
    rep = os.path.join(HERE, "full_build", "token_deviations.json")
    json.dump(list(uniq.values()), open(rep, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"token-deviations: {len(deviations):,} entries / {len(uniq):,} unique -> {rep}")
    print(f"staged -> {STAGE}")
    return files


# --------------------------------------------------------------------------- #
# OIV assembly (all 610 files into update2's american_rel.rpf, + full restore)
# --------------------------------------------------------------------------- #
HE_EFIGS = os.path.join(ORIG, "font_lib_efigs_HEBREW.gfx")
HE_PC = os.path.join(ORIG, "font_lib_efigs_pc_HEBREW.gfx")
HE_WEB = os.path.join(ORIG, "font_lib_web_HEBREW.gfx")
FSRC = os.path.join(GTAV, "_fonts_src")
VAN_EFIGS = os.path.join(FSRC, "scaleform_generic.rpf", "font_lib_efigs.gfx")
VAN_PC = os.path.join(FSRC, "scaleform_platform_pc.rpf", "font_lib_efigs_pc.gfx")
VAN_WEB = os.path.join(FSRC, "scaleform_generic.rpf", "font_lib_web.gfx")


def _adds(files, src_dir):
    """610 <add> lines mapping content/<name> -> <name> inside american_rel.rpf."""
    return "\n".join(f'        <add source="al_{fn}">{fn}</add>' for fn in files)


def _amrel_archive(inner_adds):
    return ('    <archive path="update\\update2.rpf" createIfNotExist="True" type="RPF7">\n'
            '      <archive path="x64\\data\\lang\\american_rel.rpf" createIfNotExist="True" type="RPF7">\n'
            + inner_adds + "\n"
            '      </archive>\n'
            '    </archive>\n')


def _fonts_archive(efigs, web, pc):
    return ('    <archive path="update\\update.rpf" createIfNotExist="True" type="RPF7">\n'
            '      <archive path="x64\\data\\cdimages\\scaleform_generic.rpf" createIfNotExist="True" type="RPF7">\n'
            f'        <add source="{efigs}">font_lib_efigs.gfx</add>\n'
            f'        <add source="{web}">font_lib_web.gfx</add>\n'
            '      </archive>\n'
            '      <archive path="x64\\data\\cdimages\\scaleform_platform_pc.rpf" createIfNotExist="True" type="RPF7">\n'
            f'        <add source="{pc}">font_lib_efigs_pc.gfx</add>\n'
            '      </archive>\n'
            '    </archive>\n')


def _pkg(out_name, title, desc, color, content, file_map):
    guid = "{" + str(uuid.uuid4()).upper() + "}"
    asm = ('<?xml version="1.0" encoding="utf-8"?>\n'
           f'<package version="2.2" id="{guid}" target="Five">\n'
           '  <metadata>\n'
           f'    <name>{title}</name>\n'
           '    <version><major>1</major><minor>0</minor></version>\n'
           '    <author><displayName>Game Translator</displayName></author>\n'
           f'    <description><![CDATA[{desc}]]></description>\n'
           '  </metadata>\n'
           '  <colors>\n'
           f'    <headerBackground useBlackTextColor="False">{color}</headerBackground>\n'
           '    <iconBackground>$FF2E2E2E</iconBackground>\n'
           '  </colors>\n'
           '  <content>\n' + content + '  </content>\n'
           '</package>\n')
    os.makedirs(REL, exist_ok=True)
    out = os.path.join(REL, out_name)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("assembly.xml", asm)
        for arc, srcpath in file_map.items():
            z.write(srcpath, "content/" + arc)
    if os.path.isdir(GAME):
        shutil.copy2(out, os.path.join(GAME, out_name))
    print(f"built {out_name} ({os.path.getsize(out):,} B)")


def build_oiv(files):
    # INSTALL: 610 Hebrew files + 3 Hebrew fonts.
    he_map = {f"al_{fn}": os.path.join(STAGE, fn) for fn in files}
    he_map["fe.gfx"], he_map["fw.gfx"], he_map["fp.gfx"] = HE_EFIGS, HE_WEB, HE_PC
    install_content = (_amrel_archive(_adds(files, STAGE))
                       + _fonts_archive("fe.gfx", "fw.gfx", "fp.gfx"))
    _pkg("gtav_hebrew_FULLTEXT.oiv",
         "GTA V Hebrew - FULL TEXT (all subtitles + UI)",
         "Full Hebrew for the WHOLE game: all 610 american_rel text tables (menus, HUD, "
         "phone, map, mission text, store, browser AND every dialogue subtitle), visual "
         "RTL, into the update2 base layer + Hebrew Scaleform fonts. Install to the MODS "
         "folder; set the game language to American.",
         "$FF1565C0", install_content, he_map)

    # RESTORE: the 610 vanilla files + vanilla fonts (file-level, mod-safe).
    van_map = {f"al_{fn}": os.path.join(SRC_DIR, fn) for fn in files}
    van_map["fe.gfx"], van_map["fw.gfx"], van_map["fp.gfx"] = VAN_EFIGS, VAN_WEB, VAN_PC
    restore_content = (_amrel_archive(_adds(files, SRC_DIR))
                       + _fonts_archive("fe.gfx", "fw.gfx", "fp.gfx"))
    _pkg("gtav_restore_FULLTEXT.oiv",
         "GTA V - RESTORE vanilla (full text, mod-safe)",
         "Reverts ONLY the files this mod touched (all 610 american_rel tables + 3 fonts) "
         "to byte-exact vanilla. Other mods in the same archives are untouched. Install to "
         "the MODS folder.",
         "$FFB71C1C", restore_content, van_map)


def main():
    files = build_all()
    if "--oiv" in sys.argv:
        build_oiv(files)


if __name__ == "__main__":
    main()
