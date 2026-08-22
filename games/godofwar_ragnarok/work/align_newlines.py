# -*- coding: utf-8 -*-
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

def align_string(orig, trans):
    # Find all occurrences of actual newlines and literal newlines in orig
    # We can do this by finding all matches of '\n' and '\\n'
    # To avoid regex confusion, let's scan the string character by character
    orig_types = []
    i = 0
    while i < len(orig):
        if orig[i] == '\n':
            orig_types.append('actual')
            i += 1
        elif i + 1 < len(orig) and orig[i] == '\\' and orig[i+1] == 'n':
            orig_types.append('literal')
            i += 2
        else:
            i += 1

    # Now find all occurrences of actual or literal newlines in trans
    trans_segments = []
    i = 0
    while i < len(trans):
        if trans[i] == '\n':
            trans_segments.append(('actual', i))
            i += 1
        elif i + 1 < len(trans) and trans[i] == '\\' and trans[i+1] == 'n':
            trans_segments.append(('literal', i))
            i += 2
        else:
            i += 1

    if len(orig_types) != len(trans_segments):
        # Mismatch in count, cannot align simply by order. Return as is.
        return trans

    # Reconstruct trans using the types from orig
    new_trans = ""
    last_idx = 0
    for idx, (seg_type, trans_pos) in enumerate(trans_segments):
        # Add the text before this newline
        new_trans += trans[last_idx:trans_pos]
        # Add the correct newline type from orig
        if orig_types[idx] == 'actual':
            new_trans += '\n'
        else:
            new_trans += '\\n'
        
        # Advance last_idx past the original newline in trans
        if seg_type == 'actual':
            last_idx = trans_pos + 1
        else:
            last_idx = trans_pos + 2
            
    new_trans += trans[last_idx:]
    return new_trans

def main():
    for part in range(1, 5):
        orig_file = os.path.join(HERE, f"batch_part{part}.json")
        trans_file = os.path.join(HERE, f"trans_part_{part}.json")
        if not os.path.exists(orig_file) or not os.path.exists(trans_file):
            continue
            
        orig_data = json.load(open(orig_file, encoding="utf-8"))
        trans_data = json.load(open(trans_file, encoding="utf-8"))
        
        modified = 0
        for k, orig_val in orig_data.items():
            if k in trans_data:
                old_val = trans_data[k]
                new_val = align_string(orig_val, old_val)
                if old_val != new_val:
                    trans_data[k] = new_val
                    modified += 1
                    
        if modified > 0:
            print(f"Part {part}: Aligned newlines for {modified} strings.")
            with open(trans_file, "w", encoding="utf-8") as f:
                json.dump(trans_data, f, ensure_ascii=False, indent=2)
        else:
            print(f"Part {part}: No alignment needed.")

if __name__ == "__main__":
    main()
