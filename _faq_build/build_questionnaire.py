# -*- coding: utf-8 -*-
"""
Builds ONE self-contained RTL-Hebrew HTML questionnaire from the per-category
JSON files in this folder. The questionnaire asks how the user wants their
admin panel to look + how much public-site customization they want, with:
  - one-question-at-a-time wizard + a side list to jump/edit any question
  - single / multi select + optional free-text per question
  - back / forward navigation, edit any answered question
  - autosave to localStorage + Save-to-file (export JSON) + Load-from-file
  - a final summary that builds a copyable Hebrew spec
No external dependencies; everything is inlined.
"""
import json, glob, os, html

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "שאלון-התאמה-אישית.html")

cats = []
for f in sorted(glob.glob(os.path.join(HERE, "*.json"))):
    d = json.load(open(f, encoding="utf-8"))
    qs = []
    for q in d.get("questions", []):
        opts = [{"label": str(o.get("label", "")).strip(),
                 "desc": str(o.get("desc", "")).strip()}
                for o in q.get("options", []) if str(o.get("label", "")).strip()]
        if not q.get("q") or len(opts) < 2:
            continue
        qs.append({
            "q": str(q.get("q", "")).strip(),
            "help": str(q.get("help", "")).strip(),
            "multi": bool(q.get("multi", False)),
            "allowFree": bool(q.get("allowFree", False)),
            "options": opts,
        })
    if qs:
        cats.append({"id": d.get("categoryId", os.path.basename(f)),
                     "he": d.get("categoryHe", "כללי"),
                     "questions": qs})

total = sum(len(c["questions"]) for c in cats)
bank_json = json.dumps(cats, ensure_ascii=False)

TPL = r"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>שאלון התאמה אישית — לוח הניהול והאתר</title>
<style>
  :root{
    --bg:#070710; --panel:rgba(255,255,255,.035); --panel2:rgba(255,255,255,.06);
    --line:rgba(255,255,255,.12); --txt:#e8e8f2; --mut:#9aa0b4; --acc:#00ffe0; --acc2:#fff700;
    --good:#34d399; --bad:#f87171;
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{
    background:radial-gradient(circle at 80% -10%,#1a0d40 0%,#070710 55%) fixed,var(--bg);
    color:var(--txt); font-family:"Segoe UI",Arial,system-ui,sans-serif; line-height:1.55;
    min-height:100vh;
  }
  a{color:var(--acc)}
  .wrap{max-width:1180px;margin:0 auto;padding:18px 16px 60px}
  header.top{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:14px}
  .logo{width:40px;height:40px;border-radius:11px;background:var(--acc2);display:grid;place-items:center;
    color:#0a0a14;font-weight:900;font-size:22px;box-shadow:0 6px 18px -6px rgba(255,247,0,.5)}
  h1{font-size:20px;margin:0}
  .sub{color:var(--mut);font-size:12px}
  .bar{height:8px;border-radius:99px;background:rgba(255,255,255,.08);overflow:hidden;margin:6px 0 2px}
  .bar > i{display:block;height:100%;background:linear-gradient(90deg,var(--acc),var(--acc2));transition:width .3s}
  .toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 16px}
  button{font-family:inherit;cursor:pointer;border-radius:10px;border:1px solid var(--line);
    background:var(--panel);color:var(--txt);padding:9px 14px;font-size:13px;font-weight:600;transition:.15s}
  button:hover{background:var(--panel2)}
  button:disabled{opacity:.35;cursor:not-allowed}
  button.primary{background:var(--acc2);color:#0a0a14;border-color:transparent;
    box-shadow:0 6px 16px -6px rgba(255,247,0,.5)}
  button.ghost{background:transparent}
  button.danger{border-color:rgba(248,113,113,.4);background:rgba(248,113,113,.10);color:#fca5a5}
  .layout{display:grid;grid-template-columns:300px 1fr;gap:18px;align-items:start}
  @media(max-width:880px){.layout{grid-template-columns:1fr}}
  .side{position:sticky;top:14px;max-height:84vh;overflow:auto;border:1px solid var(--line);
    border-radius:16px;background:var(--panel);padding:8px}
  .side h3{font-size:11px;letter-spacing:.18em;color:var(--mut);margin:8px 8px 6px;text-transform:uppercase}
  .qrow{display:flex;align-items:center;gap:8px;width:100%;text-align:start;padding:7px 9px;border-radius:9px;
    border:none;background:transparent;font-size:12.5px;color:var(--mut)}
  .qrow:hover{background:var(--panel2)}
  .qrow.active{background:rgba(0,255,224,.10);color:#bff;border:1px solid rgba(0,255,224,.35)}
  .qrow .dot{width:9px;height:9px;border-radius:99px;border:1px solid var(--line);flex:none}
  .qrow.done .dot{background:var(--good);border-color:transparent}
  .card{border:1px solid var(--line);border-radius:18px;background:var(--panel);padding:20px 18px}
  .catlabel{font-size:11px;letter-spacing:.16em;color:var(--acc);text-transform:uppercase;margin-bottom:8px}
  .q{font-size:21px;font-weight:800;margin:0 0 6px}
  .help{color:var(--mut);font-size:13.5px;margin:0 0 16px}
  .opts{display:flex;flex-direction:column;gap:9px}
  .opt{display:flex;gap:11px;align-items:flex-start;border:1px solid var(--line);border-radius:12px;
    padding:11px 13px;background:rgba(255,255,255,.015);cursor:pointer;transition:.12s}
  .opt:hover{background:var(--panel2);border-color:rgba(255,255,255,.25)}
  .opt.sel{border-color:var(--acc);background:rgba(0,255,224,.08);box-shadow:0 0 0 1px var(--acc) inset}
  .opt .box{width:20px;height:20px;border-radius:6px;border:2px solid var(--line);flex:none;margin-top:2px;
    display:grid;place-items:center;font-size:13px;color:#0a0a14}
  .opt.sel .box{background:var(--acc);border-color:var(--acc)}
  .opt .lab{font-weight:700;font-size:14.5px}
  .opt .desc{color:var(--mut);font-size:12.5px;margin-top:2px}
  .free{margin-top:13px}
  .free label{display:block;font-size:12px;color:var(--mut);margin-bottom:5px}
  textarea,input[type=text]{width:100%;border-radius:11px;border:1px solid var(--line);background:rgba(0,0,0,.25);
    color:var(--txt);padding:10px 12px;font-family:inherit;font-size:13.5px}
  textarea{min-height:70px;resize:vertical}
  .nav{display:flex;justify-content:space-between;gap:8px;margin-top:18px}
  .pill{font-size:12px;color:var(--mut);padding:5px 10px;border:1px solid var(--line);border-radius:99px}
  .hidden{display:none}
  /* summary */
  .sumcat{border:1px solid var(--line);border-radius:14px;background:var(--panel);margin-bottom:12px;overflow:hidden}
  .sumcat > h4{margin:0;padding:11px 14px;background:rgba(255,255,255,.04);font-size:14px}
  .sumq{padding:10px 14px;border-top:1px solid var(--line);cursor:pointer}
  .sumq:hover{background:var(--panel2)}
  .sumq .qt{font-weight:600;font-size:13.5px}
  .sumq .at{color:var(--acc);font-size:13px;margin-top:3px}
  .sumq .na{color:var(--mut);font-size:12.5px;margin-top:3px;font-style:italic}
  .note{font-size:12px;color:var(--mut);background:rgba(255,247,0,.06);border:1px solid rgba(255,247,0,.25);
    border-radius:10px;padding:9px 12px;margin:10px 0}
  .toast{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:#11131f;border:1px solid var(--line);
    color:var(--txt);padding:10px 16px;border-radius:12px;font-size:13px;opacity:0;transition:.25s;pointer-events:none;z-index:50}
  .toast.show{opacity:1}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="logo">ת</div>
    <div style="flex:1">
      <h1>שאלון התאמה אישית — לוח הניהול והאתר</h1>
      <div class="sub">בחרו איך תרצו שלוח הניהול ייראה, וכמה שליטה תרצו על האתר הציבורי. הכול נשמר אצלכם בדפדפן.</div>
    </div>
  </header>

  <div class="bar"><i id="prog"></i></div>
  <div class="toolbar">
    <span class="pill" id="counter">—</span>
    <button class="ghost" id="btnSummary">סיכום הבחירות</button>
    <button class="ghost" id="btnSave">💾 שמירה לקובץ</button>
    <button class="ghost" id="btnLoad">📂 טעינה מקובץ</button>
    <button class="ghost" id="btnCopy">📋 העתק סיכום טקסט</button>
    <button class="danger" id="btnReset">איפוס</button>
    <input type="file" id="fileInput" accept="application/json,.json" class="hidden">
  </div>

  <div class="layout">
    <aside class="side" id="side"></aside>
    <main>
      <section id="qview" class="card"></section>
      <section id="sumview" class="hidden"></section>
    </main>
  </div>
</div>
<div class="toast" id="toast"></div>

<script id="bank" type="application/json">__BANK__</script>
<script>
(function(){
  "use strict";
  var BANK = JSON.parse(document.getElementById('bank').textContent);
  var LS = 'faqQuestionnaire.v1';

  // Flatten into a single ordered list, each with a STABLE key.
  var FLAT = [];
  BANK.forEach(function(cat){
    cat.questions.forEach(function(q, li){
      FLAT.push({ key: cat.id + '#' + li, cat: cat.he, catId: cat.id, q: q });
    });
  });
  var TOTAL = FLAT.length;

  var state = load() || { answers: {}, cur: 0 };
  if (typeof state.cur !== 'number' || state.cur < 0 || state.cur >= TOTAL) state.cur = 0;
  if (!state.answers) state.answers = {};
  var mode = 'q'; // 'q' | 'summary'

  function load(){ try { var r = localStorage.getItem(LS); return r ? JSON.parse(r) : null; } catch(e){ return null; } }
  function save(){ try { localStorage.setItem(LS, JSON.stringify(state)); } catch(e){} }
  function ans(key){ return state.answers[key] || { selected: [], free: '' }; }
  function isDone(key){ var a = state.answers[key]; return !!a && ((a.selected && a.selected.length) || (a.free && a.free.trim())); }
  function answeredCount(){ var n=0; FLAT.forEach(function(it){ if(isDone(it.key)) n++; }); return n; }
  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]);}); }

  function toast(msg){
    var t=document.getElementById('toast'); t.textContent=msg; t.classList.add('show');
    clearTimeout(t._t); t._t=setTimeout(function(){ t.classList.remove('show'); }, 1900);
  }

  function setSelected(key, label, multi){
    var a = ans(key); var sel = a.selected.slice();
    var i = sel.indexOf(label);
    if (multi){ if (i>=0) sel.splice(i,1); else sel.push(label); }
    else { sel = (i>=0 && sel.length===1) ? [] : [label]; }
    state.answers[key] = { selected: sel, free: a.free || '' };
    save();
  }
  function setFree(key, val){ var a = ans(key); state.answers[key] = { selected: a.selected||[], free: val }; save(); }

  function renderProgress(){
    var done = answeredCount();
    document.getElementById('prog').style.width = (TOTAL? (done/TOTAL*100):0) + '%';
    document.getElementById('counter').textContent = 'נענו ' + done + ' מתוך ' + TOTAL;
  }

  function renderSide(){
    var side = document.getElementById('side'); var h = '';
    BANK.forEach(function(cat){
      h += '<h3>' + esc(cat.he) + '</h3>';
      cat.questions.forEach(function(q, li){
        var key = cat.id + '#' + li;
        var gi = FLAT.findIndex(function(it){ return it.key===key; });
        var cls = 'qrow' + (isDone(key)?' done':'') + ((mode==='q'&&gi===state.cur)?' active':'');
        h += '<button class="'+cls+'" data-gi="'+gi+'"><span class="dot"></span><span>'+esc(q.q)+'</span></button>';
      });
    });
    side.innerHTML = h;
    Array.prototype.forEach.call(side.querySelectorAll('.qrow'), function(b){
      b.addEventListener('click', function(){ goto(parseInt(b.getAttribute('data-gi'),10)); });
    });
  }

  function renderQ(){
    mode='q';
    document.getElementById('sumview').classList.add('hidden');
    var view = document.getElementById('qview'); view.classList.remove('hidden');
    var it = FLAT[state.cur]; var q = it.q; var a = ans(it.key);
    var h = '';
    h += '<div class="catlabel">'+esc(it.cat)+' · שאלה '+(state.cur+1)+' מתוך '+TOTAL+'</div>';
    h += '<p class="q">'+esc(q.q)+'</p>';
    if (q.help) h += '<p class="help">'+esc(q.help)+'</p>';
    h += '<div class="opts">';
    q.options.forEach(function(o){
      var on = a.selected.indexOf(o.label) >= 0;
      h += '<div class="opt'+(on?' sel':'')+'" data-label="'+esc(o.label)+'">'
         +   '<div class="box">'+(on?(q.multi?'✓':'●'):'')+'</div>'
         +   '<div><div class="lab">'+esc(o.label)+'</div>'
         +   (o.desc?'<div class="desc">'+esc(o.desc)+'</div>':'')+'</div>'
         + '</div>';
    });
    h += '</div>';
    h += '<div class="'+(q.multi?'note':'note hidden')+'">אפשר לבחור כמה תשובות בשאלה הזו.</div>';
    if (q.allowFree){
      h += '<div class="free"><label>תשובה חופשית משלך (לא חובה):</label>'
         + '<textarea id="freeBox" placeholder="הוסיפו פירוט או רעיון משלכם…">'+esc(a.free||'')+'</textarea></div>';
    }
    h += '<div class="nav">'
       + '<button class="ghost" id="prev">‹ הקודם</button>'
       + '<div style="display:flex;gap:8px">'
       +   '<button class="ghost" id="skip">דלג</button>'
       +   '<button class="primary" id="next">'+(state.cur===TOTAL-1?'סיום ›':'הבא ›')+'</button>'
       + '</div></div>';
    view.innerHTML = h;

    Array.prototype.forEach.call(view.querySelectorAll('.opt'), function(el){
      el.addEventListener('click', function(){ setSelected(it.key, el.getAttribute('data-label'), q.multi); renderQ(); renderSide(); renderProgress(); });
    });
    var fb = document.getElementById('freeBox');
    if (fb) fb.addEventListener('input', function(){ setFree(it.key, fb.value); renderProgress(); renderSide(); });
    document.getElementById('prev').disabled = state.cur===0;
    document.getElementById('prev').addEventListener('click', function(){ goto(state.cur-1); });
    document.getElementById('skip').addEventListener('click', function(){ goto(state.cur+1); });
    document.getElementById('next').addEventListener('click', function(){
      if (state.cur===TOTAL-1) renderSummary(); else goto(state.cur+1);
    });
    renderSide();
  }

  function goto(i){
    if (i<0) i=0; if (i>=TOTAL){ renderSummary(); return; }
    state.cur=i; save(); renderQ();
  }

  function renderSummary(){
    mode='summary';
    document.getElementById('qview').classList.add('hidden');
    var v = document.getElementById('sumview'); v.classList.remove('hidden');
    var done = answeredCount();
    var h = '<div class="card"><div class="catlabel">סיכום</div>'
          + '<p class="q">הבחירות שלכם</p>'
          + '<p class="help">נענו '+done+' מתוך '+TOTAL+' שאלות. לחצו על כל שורה כדי לחזור ולערוך. אפשר לשמור לקובץ או להעתיק סיכום טקסט להעביר אליי.</p></div>';
    BANK.forEach(function(cat){
      h += '<div class="sumcat"><h4>'+esc(cat.he)+'</h4>';
      cat.questions.forEach(function(q, li){
        var key = cat.id+'#'+li; var gi = FLAT.findIndex(function(it){return it.key===key;});
        var a = state.answers[key];
        var aTxt = '';
        if (a){ var parts=(a.selected||[]).slice(); if(a.free&&a.free.trim()) parts.push('✎ '+a.free.trim()); aTxt=parts.join('  ·  '); }
        h += '<div class="sumq" data-gi="'+gi+'"><div class="qt">'+esc(q.q)+'</div>'
           + (aTxt? '<div class="at">'+esc(aTxt)+'</div>' : '<div class="na">לא נענתה — לחצו לעריכה</div>')
           + '</div>';
      });
      h += '</div>';
    });
    v.innerHTML = h;
    Array.prototype.forEach.call(v.querySelectorAll('.sumq'), function(el){
      el.addEventListener('click', function(){ goto(parseInt(el.getAttribute('data-gi'),10)); });
    });
    renderSide();
  }

  function buildText(){
    var lines = ['# שאלון התאמה אישית — סיכום בחירות', '# נענו '+answeredCount()+' מתוך '+TOTAL, ''];
    BANK.forEach(function(cat){
      var any = cat.questions.some(function(q,li){ return isDone(cat.id+'#'+li); });
      if(!any) return;
      lines.push('## '+cat.he);
      cat.questions.forEach(function(q, li){
        var key=cat.id+'#'+li; if(!isDone(key)) return;
        var a=state.answers[key]; var parts=(a.selected||[]).slice();
        if(a.free&&a.free.trim()) parts.push('('+a.free.trim()+')');
        lines.push('- '+q.q+' → '+parts.join(' | '));
      });
      lines.push('');
    });
    return lines.join('\n');
  }

  // toolbar
  document.getElementById('btnSummary').addEventListener('click', renderSummary);
  document.getElementById('btnSave').addEventListener('click', function(){
    var blob = new Blob([JSON.stringify({ meta:{ tool:'faq-customization', total:TOTAL, answered:answeredCount() }, answers: state.answers }, null, 2)], {type:'application/json'});
    var a=document.createElement('a'); a.href=URL.createObjectURL(blob);
    a.download='התאמה-אישית-בחירות.json'; document.body.appendChild(a); a.click();
    setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); }, 500);
    toast('נשמר לקובץ');
  });
  document.getElementById('btnLoad').addEventListener('click', function(){ document.getElementById('fileInput').click(); });
  document.getElementById('fileInput').addEventListener('change', function(e){
    var f=e.target.files[0]; if(!f) return; var r=new FileReader();
    r.onload=function(){ try{ var d=JSON.parse(r.result); state.answers = d.answers || d || {}; save(); toast('נטען מהקובץ');
      if(mode==='summary') renderSummary(); else renderQ(); renderProgress(); renderSide();
    }catch(err){ toast('קובץ לא תקין'); } };
    r.readAsText(f); e.target.value='';
  });
  document.getElementById('btnCopy').addEventListener('click', function(){
    var txt=buildText();
    function done(){ toast('הסיכום הועתק — אפשר להדביק'); }
    if(navigator.clipboard && navigator.clipboard.writeText){ navigator.clipboard.writeText(txt).then(done, fallback); } else fallback();
    function fallback(){ var ta=document.createElement('textarea'); ta.value=txt; document.body.appendChild(ta); ta.select(); try{document.execCommand('copy');}catch(e){} ta.remove(); done(); }
  });
  document.getElementById('btnReset').addEventListener('click', function(){
    if(!confirm('לאפס את כל התשובות? הפעולה לא הפיכה.')) return;
    state={answers:{},cur:0}; save(); renderQ(); renderProgress(); renderSide(); toast('אופס');
  });

  renderProgress(); renderQ();
})();
</script>
</body>
</html>
"""

out_html = TPL.replace("__BANK__", bank_json)
open(OUT, "w", encoding="utf-8").write(out_html)
print("WROTE", OUT)
print("categories =", len(cats), " questions =", total, " bytes =", len(out_html))
