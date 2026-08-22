import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    src_path = os.path.join(HERE, "to_translate.json")
    skip_path = os.path.join(HERE, "skip.json")
    
    if not os.path.exists(src_path):
        print("to_translate.json not found!")
        return

    with open(src_path, encoding="utf-8") as f:
        src = json.load(f)

    if os.path.exists(skip_path):
        try:
            with open(skip_path, encoding="utf-8") as f:
                skip = set(json.load(f))
        except Exception:
            skip = set()
    else:
        skip = set()

    known_names = {
        'Michael', 'Franklin', 'Trevor', 'Lester', 'Lamar', 'Los Santos', 'Blaine County', 
        'Ammu-Nation', 'LSPD', 'FIB', 'Lifeinvader', 'Social Club', 'GTA Online', 'Minisub',
        'GTA V', 'GTA 5', 'Adder', 'Buffalo', 'Pegassi', 'Cheetah', 'Infernus', 'Banshee',
        'Sentinel', 'Futo', 'Coquette', 'Zentorno', 'Massacro', 'Jester', 'Turismo R', 
        'Elegy', 'Bati 801', 'Akuma', 'Double T', 'Ruffian', 'Sanchez', 'Faggio', 'Blazer',
        'Benson', 'Pounder', 'Mule', 'Phantom', 'Hauler', 'Packer', 'Flatbed', 'Rubble',
        'Mixer', 'Tioga', 'Burrito', 'Pony', 'Speedo', 'Rumpo', 'Youga', 'Surge', 'Voltic',
        'Khamelion', 'Weazel News', 'Pounders', 'FlyUS', "Cluckin' Bell", 'Sprunk', 'eCola',
        'Burger Shot', 'Up-n-Atom', 'Taco Bomb', 'Bleeder', 'Pisswasser', 'Logger Light',
        'Maze Bank', 'Fleeca', 'Union Depository', 'Humane Labs', 'Merryweather', 'Karin',
        'Dinka', 'Albany', 'Vapid', 'Declasse', 'Pfister', 'Obey', 'Truffade', 'Grotti', 
        'Overflod', 'Cheetah', 'Akuma'
    }

    # Safer regex patterns
    symbol_pattern = re.compile(r'^[~%$ \t\r\n0-9.,;:!?()\'\"\\\[\]<>/*#+=&$@\-]*$')
    
    # Uppercase code patterns like CHAR_..., HUD_..., or purely uppercase words with underscores
    # (e.g. CHAR_STRIPPER_SAPPHIRE, RC_VEHICLE, etc.)
    code_pattern = re.compile(r'^[A-Z0-9_]+_[A-Z0-9_]+$')
    
    # Pure uppercase short abbreviations that are not English words (e.g. DLC, ISO, FPS, LSPD, FIB, GPS, HUD, TV, UI, PC)
    abbreviation_pattern = re.compile(r'^(DLC|ISO|FPS|LSPD|FIB|GPS|HUD|TV|UI|PC|CCTV|RTL|SMS|US|USA|UK|ID|IP|CPU|GPU|RAM|OS|API|URL|HTML|2D|3D|HD|SD|4K|AM|PM|FM|AC|DC|MC|CEO|VIP|XP|RP|MP|COOP|VS|CTF|DM|TDM|HEIST|HUD_COLOUR_[A-Z_]+)$')

    new_skips = 0
    for k, v in src.items():
        if k in skip:
            continue
            
        v_strip = v.strip()
        
        # Check conditions
        should_skip = False
        
        # 1. Symbol/Number/Placeholder
        if symbol_pattern.match(v_strip):
            should_skip = True
        # 2. Known name
        elif v_strip in known_names:
            should_skip = True
        # 3. System code pattern
        elif code_pattern.match(v_strip):
            should_skip = True
        # 4. Pure abbreviation
        elif abbreviation_pattern.match(v_strip.upper()):
            should_skip = True
            
        if should_skip:
            skip.add(k)
            new_skips += 1

    with open(skip_path, "w", encoding="utf-8") as f:
        json.dump(sorted(list(skip)), f, ensure_ascii=False, indent=1)

    print(f"Done. Added {new_skips} new skips. Total skips: {len(skip)}")

if __name__ == "__main__":
    main()
