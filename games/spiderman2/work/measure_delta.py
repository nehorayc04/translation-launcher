import json, time, os
from datetime import datetime
base = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\spiderman2\work\dialogue_he.json"
subs = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\spiderman2\work\subtitles_he.json"

def count(path):
    try:
        with open(path,'r',encoding='utf-8') as f:
            j=json.load(f)
            if isinstance(j, dict):
                return len(j)
            return 0
    except Exception as e:
        return None

print('timestamp_start:', datetime.utcnow().isoformat())
start_d=count(base)
start_s=count(subs)
print('start_dialogue_count:', start_d)
print('start_subtitles_count:', start_s)
print('sleeping 90s...')
for i in range(9):
    time.sleep(10)
    print('.',end='',flush=True)
print('\nreading again...')
end_d=count(base)
end_s=count(subs)
print('timestamp_end:', datetime.utcnow().isoformat())
print('end_dialogue_count:', end_d)
print('end_subtitles_count:', end_s)
if start_d is not None and end_d is not None:
    delta_d = end_d - start_d
    rate_per_hour = (delta_d / 90.0) * 3600.0
    print(f'delta_dialogue: {delta_d} in 90s -> {rate_per_hour:.1f} items/hour')
else:
    print('could not read dialogue file counts')
if start_s is not None and end_s is not None:
    delta_s = end_s - start_s
    rate_sh = (delta_s / 90.0) * 3600.0
    print(f'delta_subtitles: {delta_s} in 90s -> {rate_sh:.1f} items/hour')
else:
    print('could not read subtitles file counts')
print('done')
