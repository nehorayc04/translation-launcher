/* The property the fix turns on: a cover that arrives AFTER the 12s settle
 * timer must still paint. With the old code that was impossible - the timer set
 * imgError, which unmounted the <img>, so the request had nowhere to land and
 * only a remount could recover. Here every image is held for 14s. */
const { chromium } = require('playwright-core');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const HOLD_MS = 14000;                    // > the 12000ms settle timer
const SEL = '[data-tour="game-card"]';

const probe = () => {
  const cards = Array.from(document.querySelectorAll('[data-tour="game-card"]'));
  const imgs = cards.map((c) => c.querySelector('img')).filter(Boolean);
  return {
    cards: cards.length, imgs: imgs.length,
    loaded: imgs.filter((i) => i.complete && i.naturalWidth > 0).length,
    visible: imgs.filter((i) => getComputedStyle(i).opacity === '1').length,
    skeletons: cards.filter((c) => c.querySelector('.skeleton')).length,
  };
};

(async () => {
  const b = await chromium.launch({ executablePath: CHROME, headless: true });
  const p = await b.newPage({ viewport: { width: 1280, height: 780 } });
  // hold every image well past the settle timer
  await p.route('**/*', async (route) => {
    if (route.request().resourceType() === 'image') {
      await new Promise((r) => setTimeout(r, HOLD_MS));
    }
    return route.continue();
  });
  await p.goto('http://localhost:5180/preview.html', { waitUntil: 'domcontentloaded' });
  await p.waitForSelector(SEL, { timeout: 60000 });
  const t0 = Date.now();

  let atSettle = null;
  for (const at of [13000, 20000, 26000]) {
    await p.waitForTimeout(Math.max(0, at - (Date.now() - t0)));
    const s = await p.evaluate(probe);
    console.log(`t=${((Date.now() - t0) / 1000).toFixed(1)}s  ${JSON.stringify(s)}`);
    if (at === 13000) atSettle = s;                 // after settle, before arrival
  }
  const end = await p.evaluate(probe);

  console.log('\n--- assertions ---');
  let fail = 0;
  const chk = (n, c, x = '') => { c ? console.log(`  PASS  ${n}${x ? `  [${x}]` : ''}`)
                                   : (fail++, console.log(`  FAIL  ${n}${x ? `  [${x}]` : ''}`)); };
  chk('at 13s the placeholder HAS settled (shimmer stopped)', atSettle.skeletons === 0, `${atSettle.skeletons}`);
  chk('...and nothing had painted yet', atSettle.loaded === 0, `${atSettle.loaded} loaded`);
  chk('...but the <img> elements SURVIVED the settle', atSettle.imgs === atSettle.cards,
      `${atSettle.imgs}/${atSettle.cards}`);
  chk('THE FIX: the late cover still decodes', end.loaded === end.cards, `${end.loaded}/${end.cards}`);
  chk('...and fades in to full opacity', end.visible === end.cards, `${end.visible}/${end.cards}`);

  await p.screenshot({ path: process.argv[2] || 'late.png' });
  await b.close();
  console.log(fail === 0 ? '\nALL_OK' : `\nFAILURES=${fail}`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error('ERR', e); process.exit(2); });
