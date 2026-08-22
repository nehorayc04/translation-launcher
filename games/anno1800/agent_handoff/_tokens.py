"""Shared token extractor for the Anno 1800 handoff scripts. NOT a translator.

Anno's preservable tokens are:
  - tags:        <br/>, <... > (any <...> run)
  - printf:      %i %d %s ...   (rare)
  - data-binds:  [ ... ]  with ARBITRARY NESTING of [ ] and ( ) inside,
                 e.g. [AssetData([RefGuid] Text)], [Participants Current ... Text]
These must survive verbatim (same multiset) in the translation. Only the prose
OUTSIDE them is translated.
"""
import re

_TAG = re.compile(r"<[^>]+>")
_PCT = re.compile(r"%[0-9.]*[sdifuxX]")


def tokens(s):
    raw_tags = _TAG.findall(s)
    cleaned_tags = [re.sub(r'=\s*(["\'])(.*?)\1', r'=""', t) for t in raw_tags]
    toks = cleaned_tags + _PCT.findall(s)
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "[":
            depth = 0
            j = i
            while j < n:
                if s[j] == "[":
                    depth += 1
                elif s[j] == "]":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            toks.append(s[i:j + 1])
            i = j + 1
        else:
            i += 1
    return toks


def strip_tokens(s):
    for t in tokens(s):
        s = s.replace(t, "")
    return s
