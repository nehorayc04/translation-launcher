#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, re

STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
LOWERW = re.compile(r'[a-z]{2,}')
HEB = re.compile(r'[א-ת]')

batch = json.load(open('current_batch.json', encoding='utf-8'))
tt = json.load(open('to_translate.json', encoding='utf-8'))
he = json.load(open('hebrew.json', encoding='utf-8'))

def is_namey(en):
    core = STRUCT.sub(' ', en).strip()
    if not LOWERW.search(core):
        return True
    words = re.findall(r"[A-Za-z']+", core)
    return bool(words) and len(words) <= 4 and all(w[:1].isupper() for w in words)

for k, v in batch.items():
    if k in he:
        continue
    if k not in tt:
        continue
    hebrew = v if isinstance(v, str) else v.get('he', '')
    en = tt[k]['en']
    if not HEB.search(hebrew):
        nm = is_namey(en)
        eq = hebrew.strip() == en.strip()
        print(f'{k}: namey={nm}, verbatim={eq}')
        print(f'  he={repr(hebrew[:80])}')
        print(f'  en={repr(en[:80])}')
