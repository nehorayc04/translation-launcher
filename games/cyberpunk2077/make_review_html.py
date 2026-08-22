"""
make_review_html.py — build a one-file review UI for word_anomalies.jsonl.

Generates review.html (self-contained, findings embedded — just double-click).
Per finding: the Hebrew line (suspicious word highlighted) + English source.
  1 / קליק "תקין"      = the row is fine (reject fix)
  2 / קליק "לא תקין"   = needs fixing (approve fix)
  0 = skip,  Z = undo,  arrows navigate, category tabs filter.
Decisions persist in localStorage; "ייצוא" downloads review_decisions.json —
hand that file back and the approved rows go into the fix queue.

Re-run after每 new scan: python make_review_html.py
"""
import os, json, html

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "word_anomalies.jsonl")
OUT = os.path.join(HERE, "review.html")

rows = [json.loads(l) for l in open(SRC, encoding="utf-8") if l.strip()]

# exclude findings already settled by the AI judges (Claude/gemma verdicts
# 'ok' or an applied 'fix') — the user should only review what's still open
_judged = {}
_qpath = os.path.join(HERE, "claude_queue.jsonl")
if os.path.exists(_qpath):
    _queue = {json.loads(l)["n"]: json.loads(l) for l in open(_qpath, encoding="utf-8") if l.strip()}
    for fn in ("claude_judgments.jsonl", "local_judgments.jsonl"):
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            for l in open(p, encoding="utf-8"):
                try:
                    v = json.loads(l)
                    _judged.setdefault(v["n"], v["verdict"])
                except Exception:
                    pass
    settled = set()
    for n, verdict in _judged.items():
        if verdict in ("ok", "fix") and n in _queue:
            for ref in _queue[n]["refs"]:
                proj, sec, pk, fld = ref.split("|", 3)
                settled.add((sec, pk, fld, _queue[n]["category"], _queue[n].get("word", "")))
    before = len(rows)
    rows = [r for r in rows if (r["section"], r["pk"], r["field"], r["category"], r.get("word", "")) not in settled]
    print(f"filtered {before - len(rows)} findings already settled by the AI judges")

for i, r in enumerate(rows):
    r["id"] = f'{r["project"]}|{r["section"]}|{r["pk"]}|{r["field"]}|{r["category"]}|{r.get("word","")}'

data_json = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")

page = """<!DOCTYPE html>
<html dir="rtl" lang="he"><head><meta charset="utf-8">
<title>סקירת אנומליות תרגום</title>
<style>
 body{background:#15171c;color:#e8e8e8;font-family:Segoe UI,Arial;margin:0;padding:16px}
 .tabs{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
 .tab{padding:6px 10px;border-radius:6px;background:#262a33;cursor:pointer;font-size:13px}
 .tab.on{background:#3b82f6;color:#fff}
 .card{background:#1e222a;border-radius:10px;padding:22px;max-width:880px;margin:0 auto}
 .he{font-size:22px;line-height:1.6;direction:rtl;unicode-bidi:plaintext;margin:14px 0}
 .he mark{background:#b91c1c;color:#fff;border-radius:4px;padding:0 3px}
 .en{font-size:14px;color:#9ca3af;direction:ltr;text-align:left;unicode-bidi:plaintext}
 .meta{font-size:12px;color:#6b7280;margin-bottom:6px}
 .word{font-size:15px;color:#fbbf24}
 .btns{display:flex;gap:10px;margin-top:18px;justify-content:center}
 button{font-size:17px;padding:10px 26px;border:0;border-radius:8px;cursor:pointer;font-family:inherit}
 .ok{background:#16a34a;color:#fff}.bad{background:#dc2626;color:#fff}
 .skip{background:#374151;color:#ddd}.undo{background:#262a33;color:#9ca3af;font-size:13px}
 .bar{max-width:880px;margin:10px auto;display:flex;justify-content:space-between;align-items:center;font-size:14px;color:#9ca3af}
 .export{background:#3b82f6;color:#fff;font-size:13px;padding:7px 14px}
 .stat b{color:#e8e8e8}
 kbd{background:#262a33;border-radius:4px;padding:1px 6px;font-size:12px}
 .done-banner{font-size:20px;text-align:center;padding:40px;color:#16a34a}
</style></head><body>
<div class="tabs" id="tabs"></div>
<div class="bar">
 <span class="stat" id="stat"></span>
 <span>מקשים: <kbd>1</kbd> תקין · <kbd>2</kbd> לא תקין · <kbd>0</kbd> דלג · <kbd>Z</kbd> בטל</span>
 <span>
   <button class="export" onclick="savePortable()">💾 שמור קובץ נייד</button>
   <button class="export" onclick="exportDecisions()">⬇ ייצוא החלטות</button>
 </span>
</div>
<div class="card" id="card"></div>
<script id="seed" type="application/json">{}</script>
<script>
const DATA = __DATA__;
// decisions live BOTH in the file (seed) and in localStorage; the seed makes
// the file portable — "שמור קובץ נייד" bakes current decisions into a copy.
const seedRaw = JSON.parse(document.getElementById('seed').textContent||'{}');
const seedD = seedRaw.d || (seedRaw.n===undefined ? seedRaw : {});   // back-compat
const seedN = seedRaw.n || {};
let decisions = Object.assign({}, seedD, JSON.parse(localStorage.getItem('tm_rv2')||'{}'));
let notes = Object.assign({}, seedN, JSON.parse(localStorage.getItem('tm_rv2_notes')||'{}'));
let cat = localStorage.getItem('tm_rv2_cat')||'all';
let idxByCat = JSON.parse(localStorage.getItem('tm_rv2_idx')||'{}');
let hist = [];
const cats = ['all',...new Set(DATA.map(r=>r.category))];

function list(){ return DATA.filter(r=>cat==='all'||r.category===cat); }
function save(){
  localStorage.setItem('tm_rv2',JSON.stringify(decisions));
  localStorage.setItem('tm_rv2_idx',JSON.stringify(idxByCat));
  localStorage.setItem('tm_rv2_notes',JSON.stringify(notes));
}
function saveNote(id,val){
  if(val.trim()) notes[id]=val; else delete notes[id];
  save();
}
function getIdx(){ const l=list(); let i=idxByCat[cat]||0; return Math.min(Math.max(i,0),Math.max(l.length-1,0)); }
function setIdx(i){ idxByCat[cat]=i; save(); render(); }

function renderTabs(){
  document.getElementById('tabs').innerHTML = cats.map(c=>{
    const tot=c==='all'?DATA.length:DATA.filter(r=>r.category===c).length;
    const done=c==='all'?Object.keys(decisions).length:DATA.filter(r=>r.category===c&&(r.id in decisions)).length;
    return `<div class="tab ${c===cat?'on':''}" onclick="setCat('${c}')">${c} (${done}/${tot})</div>`;
  }).join('');
}
function setCat(c){ cat=c; localStorage.setItem('tm_rv2_cat',c); render(); }

function esc(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
const VLAB = {ok:'<span style="color:#16a34a">✔ סומן: תקין</span>',
              bad:'<span style="color:#dc2626">✘ סומן: לא תקין</span>',
              skip:'<span style="color:#9ca3af">⏭ דולג</span>'};
function render(){
  renderTabs();
  const l = list();
  const i = getIdx();
  const left = l.filter(r=>!(r.id in decisions)).length;
  const ok = Object.values(decisions).filter(v=>v==='ok').length;
  const bad = Object.values(decisions).filter(v=>v==='bad').length;
  document.getElementById('stat').innerHTML =
    `${i+1}/${l.length} · נותרו <b>${left}</b> · תקין <b style="color:#16a34a">${ok}</b> · לא תקין <b style="color:#dc2626">${bad}</b>`;
  const el = document.getElementById('card');
  if(!l.length){ el.innerHTML='<div class="done-banner">אין ממצאים בקטגוריה</div>'; return; }
  const r = l[i];
  let he = esc(r.hebrew);
  if(r.word){ const w=esc(r.word); he = he.split(w).join('<mark>'+w+'</mark>'); }
  const v = decisions[r.id];
  el.innerHTML = `
   <div class="meta">${r.category} · [${r.project}/${esc(r.section)}] pk=${r.pk} (${r.field})
     ${v?` · <b>${VLAB[v]}</b>`:' · <span style="color:#fbbf24">טרם הוחלט</span>'}</div>
   ${r.word?`<div class="word">מילה חשודה: ${esc(r.word)}</div>`:''}
   <div class="he">${he}</div>
   ${r.english?`<div class="en">EN: ${esc(r.english)}</div>`:''}
   <div class="btns">
     <button class="skip" onclick="nav(-1)" title="ArrowRight">→ הקודם</button>
     <button class="ok" onclick="decide('ok')">תקין (1)</button>
     <button class="bad" onclick="decide('bad')">לא תקין (2)</button>
     <button class="skip" onclick="decide('skip')">דלג (0)</button>
     <button class="skip" onclick="nav(1)" title="ArrowLeft">הבא ←</button>
   </div>
   <textarea id="note" rows="2" placeholder="הערה לשורה הזו (לא חובה)"
     style="width:100%;margin-top:14px;background:#15171c;color:#e8e8e8;border:1px solid #374151;border-radius:8px;padding:8px;font-family:inherit;font-size:14px;direction:rtl"></textarea>
   <div class="btns">
     <button class="undo" onclick="undo()">בטל אחרון (Z)</button>
     <button class="undo" onclick="firstPending()">קפוץ לראשון שטרם הוחלט (P)</button>
   </div>`;
  const ta = el.querySelector('#note');
  ta.value = notes[r.id] || '';
  ta.addEventListener('input', e => saveNote(r.id, e.target.value));
}
function nav(d){ const l=list(); setIdx(Math.min(Math.max(getIdx()+d,0),l.length-1)); }
function firstPending(){
  const l=list(); const j=l.findIndex(r=>!(r.id in decisions));
  if(j>=0) setIdx(j);
}
function decide(v){
  const l=list(); if(!l.length) return;
  const r = l[getIdx()];
  decisions[r.id]=v; hist.push(r.id); save();
  // auto-advance to the NEXT undecided after current (wraps to plain next)
  const i=getIdx();
  let j=l.findIndex((x,k)=>k>i&&!(x.id in decisions));
  if(j<0) j=Math.min(i+1,l.length-1);
  setIdx(j);
}
function undo(){
  const id = hist.pop(); if(!id) return;
  delete decisions[id]; save();
  const l=list(); const j=l.findIndex(r=>r.id===id);
  if(j>=0) setIdx(j); else render();
}
function exportDecisions(){
  const out = DATA.filter(r=>(decisions[r.id]&&decisions[r.id]!=='skip')||notes[r.id])
    .map(r=>({id:r.id,project:r.project,section:r.section,pk:r.pk,field:r.field,
              category:r.category,word:r.word,verdict:decisions[r.id]||'',
              note:notes[r.id]||''}));
  const blob = new Blob([JSON.stringify(out,null,1)],{type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download='review_decisions.json'; a.click();
}
function savePortable(){
  // bake current decisions+notes into the seed element, then download THIS page
  document.getElementById('seed').textContent = JSON.stringify({d:decisions,n:notes});
  const html = '<!DOCTYPE html>\\n' + document.documentElement.outerHTML;
  const blob = new Blob([html],{type:'text/html'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download='review.html'; a.click();
}
document.addEventListener('keydown',e=>{
  if(e.target && e.target.tagName==='TEXTAREA') return;   // typing a note
  if(e.key==='1') decide('ok');
  else if(e.key==='2') decide('bad');
  else if(e.key==='0') decide('skip');
  else if(e.key==='z'||e.key==='Z') undo();
  else if(e.key==='ArrowLeft') nav(1);
  else if(e.key==='ArrowRight') nav(-1);
  else if(e.key==='p'||e.key==='P') firstPending();
});
render();
</script></body></html>"""

page = page.replace("__DATA__", data_json)
open(OUT, "w", encoding="utf-8").write(page)
print(f"built {OUT} with {len(rows):,} findings ({os.path.getsize(OUT)/1e6:.1f} MB)")
