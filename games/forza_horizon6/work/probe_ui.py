"""Probe the FH6 XAML UI layer: font references, FlowDirection/RTL support,
language handling, and hardcoded (non-string-table) text."""
import os, re, sys, zipfile, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UI = r"C:\Games\Forza Horizon 6\media\UI.zip"

z = zipfile.ZipFile(UI)
names = [i.filename for i in z.infolist()]
blobs = {n: z.read(n).decode("utf-8", "replace") for n in names}
all_text = "\n".join(blobs.values())
print(f"UI.zip: {len(names)} files, {len(all_text):,} chars")

def count(label, rx, sample=6):
    m = re.findall(rx, all_text)
    c = collections.Counter(m)
    print(f"\n{label}: {len(m)} occ / {len(c)} distinct")
    for k, v in c.most_common(sample):
        print(f"    {v:6d}  {k!r}")

count("FontFamily",       r'FontFamily\s*=\s*"([^"]+)"')
count("FlowDirection",    r'FlowDirection\s*=\s*"([^"]+)"')
count("Horizon_ font ref", r'(Horizon_[A-Za-z_]+)')
count("TextAlignment",    r'TextAlignment\s*=\s*"([^"]+)"')

for kw in ("RightToLeft", "IsRtl", "Bidi", "Arabic", "Hebrew", "Language",
           "Mirror", "xml:lang"):
    n = len(re.findall(kw, all_text, re.I))
    print(f"  keyword {kw:<14s} {n}")

# hardcoded literal Text="..." that is NOT a string-table reference
lits = re.findall(r'Text\s*=\s*"([^"{}]{3,})"', all_text)
real = [s for s in lits if re.search(r"[A-Za-z]{3,}", s)]
print(f"\nhardcoded Text=\"...\" literals: {len(lits)} ({len(set(real))} distinct with words)")
for s, c in collections.Counter(real).most_common(15):
    print(f"    {c:4d}  {s[:70]!r}")

# how string-table entries are referenced from XAML
for rx, lbl in [(r'\{\s*[Ss]tr(?:ing)?\s+([^}\s]+)', 'Str binding'),
                (r'IDS_[A-Za-z0-9_]+', 'IDS_ id'),
                (r'StringId\s*=\s*"([^"]+)"', 'StringId=')]:
    m = re.findall(rx, all_text)
    print(f"\n{lbl}: {len(m)} occ")
    for k, v in collections.Counter(m).most_common(5):
        print(f"    {v:5d}  {k!r}")
