import json
import re

with open('to_translate.json', encoding='utf-8') as f:
    src = json.load(f)

known_names = {
    'Michael', 'Franklin', 'Trevor', 'Lester', 'Lamar', 'Los Santos', 'Blaine County', 
    'Ammu-Nation', 'LSPD', 'FIB', 'Lifeinvader', 'Social Club', 'GTA Online', 'Minisub',
    'GTA V', 'GTA 5', 'Adder', 'Buffalo', 'Pegassi', 'Cheetah', 'Infernus', 'Banshee',
    'Sentinel', 'Futo', 'Coquette', 'Zentorno', 'Massacro', 'Jester', 'Turismo R', 
    'Elegy', 'Bati 801', 'Akuma', 'Double T', 'Ruffian', 'Sanchez', 'Faggio', 'Blazer',
    'Benson', 'Pounder', 'Mule', 'Phantom', 'Hauler', 'Packer', 'Flatbed', 'Rubble',
    'Mixer', 'Tioga', 'Burrito', 'Pony', 'Speedo', 'Rumpo', 'Youga', 'Surge', 'Voltic',
    'Khamelion', 'Weazel News', 'Pounders', 'FlyUS', 'Cluckin\' Bell', 'Sprunk', 'eCola',
    'Burger Shot', 'Up-n-Atom', 'Taco Bomb', 'Bleeder', 'Pisswasser', 'Logger Light',
    'Maze Bank', 'Fleeca', 'Union Depository', 'Humane Labs', 'Merryweather', 'Karin',
    'Dinka', 'Albany', 'Vapid', 'Declasse', 'Pfister', 'Obey', 'Truffade', 'Grotti', 
    'Overflod', 'Cheetah', 'Akuma'
}

skipped = {}
reasons = {}

# Compile regexes
# 1. Pure numbers/symbols/placeholders (e.g. "12", "$100", "%d", "~1~", "10/10")
symbol_pattern = re.compile(r'^[~%$ \t\r\n0-9.,;:!?()\'\"\\\[\]<>/*#+=&$@\-]*$')
# 2. Key/code pattern (e.g. "0x000abc", "DLC_X", "RADIO_X", "A_B_C_D")
code_pattern = re.compile(r'^[A-Z0-9_]{3,}$')

for k, v in src.items():
    v_strip = v.strip()
    
    # 1. Only symbols/numbers/placeholders
    if symbol_pattern.match(v_strip):
        skipped[k] = v
        reasons[k] = "symbol/number/placeholder"
        continue
        
    # 2. Pure known name/brand
    if v_strip in known_names:
        skipped[k] = v
        reasons[k] = "known name"
        continue
        
    # 3. Pure code
    if code_pattern.match(v_strip):
        skipped[k] = v
        reasons[k] = "code/uppercase key"
        continue

print(f"Total keys in src: {len(src)}")
print(f"Found {len(skipped)} keys to skip.")

# Print some of each type
types = {}
for k, v in skipped.items():
    r = reasons[k]
    types.setdefault(r, []).append((k, v))

for r, items in types.items():
    print(f"\nReason: {r} (Count: {len(items)})")
    for k, v in items[:15]:
        print(f"  {k}: {repr(v)}")
