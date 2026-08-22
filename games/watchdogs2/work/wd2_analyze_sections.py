"""
Analyze the oasisstrings XML to find all sections and their LineIds.
Also cross-reference with the decoded loc.txt to identify which strings
belong to BarkSubtitles (dialogue) vs UI.
"""
import xml.etree.ElementTree as ET
import sys, os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

XML_PATH = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\en_oasis\languages\english\oasisstrings_converted.xml"
LOC_TXT = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\main_english.loc.txt"

# Parse XML
print("Parsing XML...")
tree = ET.parse(XML_PATH)
root = tree.getroot()

# Collect all sections and their LineIds
sections = {}
bark_ids = set()
all_xml_ids = set()

for section in root:
    name = section.attrib.get("name", section.tag)
    ids = []
    for child in section:
        lid = child.attrib.get("LineId")
        if lid:
            lid_int = int(lid)
            ids.append(lid_int)
            all_xml_ids.add(lid_int)
            if name == "BarkSubtitles":
                bark_ids.add(lid_int)
    sections.setdefault(name, []).extend(ids)

print(f"\nSections found: {len(sections)}")
for name, ids in sorted(sections.items()):
    print(f"  {name}: {len(ids)} strings (IDs {min(ids) if ids else 'N/A'}..{max(ids) if ids else 'N/A'})")

print(f"\nTotal XML strings: {len(all_xml_ids)}")
print(f"BarkSubtitles: {len(bark_ids)} strings")
print(f"Non-BarkSubtitles: {len(all_xml_ids) - len(bark_ids)} strings")

# Load loc.txt
print(f"\nLoading loc.txt...")
loc_strings = {}
with open(LOC_TXT, "r", encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\r\n")
        if "=" in line:
            k, v = line.split("=", 1)
            if k.isdigit():
                loc_strings[int(k)] = v

print(f"Total loc strings: {len(loc_strings)}")

# Cross-reference
in_bark = sum(1 for lid in loc_strings if lid in bark_ids)
in_xml_not_bark = sum(1 for lid in loc_strings if lid in all_xml_ids and lid not in bark_ids)
not_in_xml = sum(1 for lid in loc_strings if lid not in all_xml_ids)

print(f"\nLoc strings in BarkSubtitles: {in_bark}")
print(f"Loc strings in other XML sections: {in_xml_not_bark}")
print(f"Loc strings NOT in XML at all: {not_in_xml}")

# Check patch2 XML too
PATCH2_XML = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\patch2_en\languages\english\oasisstrings_converted.xml"
if os.path.exists(PATCH2_XML):
    print(f"\n--- Patch2 XML ---")
    tree2 = ET.parse(PATCH2_XML)
    root2 = tree2.getroot()
    p2_sections = {}
    p2_bark = set()
    p2_all = set()
    for section in root2:
        name = section.attrib.get("name", section.tag)
        ids = []
        for child in section:
            lid = child.attrib.get("LineId")
            if lid:
                lid_int = int(lid)
                ids.append(lid_int)
                p2_all.add(lid_int)
                if name == "BarkSubtitles":
                    p2_bark.add(lid_int)
        p2_sections.setdefault(name, []).extend(ids)
    
    print(f"Patch2 sections: {len(p2_sections)}")
    for name, ids in sorted(p2_sections.items()):
        print(f"  {name}: {len(ids)} strings")
    
    # Combine
    combined_bark = bark_ids | p2_bark
    combined_all = all_xml_ids | p2_all
    print(f"\nCombined BarkSubtitles: {len(combined_bark)}")
    print(f"Combined all XML: {len(combined_all)}")
    
    in_bark_c = sum(1 for lid in loc_strings if lid in combined_bark)
    in_xml_not_bark_c = sum(1 for lid in loc_strings if lid in combined_all and lid not in combined_bark)
    not_in_xml_c = sum(1 for lid in loc_strings if lid not in combined_all)
    
    print(f"\nLoc strings in combined BarkSubtitles: {in_bark_c}")
    print(f"Loc strings in other combined sections: {in_xml_not_bark_c}")
    print(f"Loc strings NOT in combined XML: {not_in_xml_c}")
    print(f"=> UI candidates (non-bark): {in_xml_not_bark_c + not_in_xml_c}")

# Save the bark IDs for the translator
bark_ids_path = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\bark_subtitle_ids.txt"
combined_bark_all = bark_ids
if os.path.exists(PATCH2_XML):
    combined_bark_all = bark_ids | p2_bark

with open(bark_ids_path, "w") as f:
    for lid in sorted(combined_bark_all):
        f.write(f"{lid}\n")
print(f"\nSaved {len(combined_bark_all)} bark IDs to {bark_ids_path}")

# Save UI-only strings
ui_path = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2\extract\ui_strings_english.txt"
ui_count = 0
with open(ui_path, "w", encoding="utf-8") as f:
    for lid in sorted(loc_strings.keys()):
        if lid not in combined_bark_all:
            f.write(f"{lid}={loc_strings[lid]}\n")
            ui_count += 1
print(f"Saved {ui_count} UI strings to {ui_path}")
