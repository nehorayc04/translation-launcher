import json,os,glob,time
# Un-park everything that was struck out by the guard, KEEPING only the genuinely
# unwinnable token-only lines. Those 3 strikes were overwhelmingly `niqqud`, which
# the worker now strips deterministically instead of refusing.
n=0
for f in sorted(glob.glob("ac2_skip_*.json")):
    d=json.load(open(f,encoding='utf-8'))
    if not isinstance(d,dict): continue
    skip=set(d.get('skip',[])); tok=set(d.get('token_only',[]))
    keep=skip & tok
    freed=len(skip)-len(keep)
    json.dump(d, open(f+'.bak-niqqud','w',encoding='utf-8'), ensure_ascii=False)
    json.dump({'skip':sorted(keep),'strikes':{},'token_only':sorted(tok)},
              open(f,'w',encoding='utf-8'), ensure_ascii=False)
    print(f"{f}: parked {len(skip)} -> {len(keep)} (freed {freed})")
    n+=freed
print("TOTAL freed:",n)
