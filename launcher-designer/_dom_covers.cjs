/* Reproduce the user's recording against the REAL App:
 *   open → let the splash lift → DO NOT SCROLL for >12s (the settle timer) →
 *   then scroll to the home "תרגומים מובילים" row.
 * The regression was that the <img> elements were GONE by then, so the covers
 * could never load and only a remount (menu out-and-back) brought them back. */
const { chromium } = require('playwright-core');
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const SEL = '[data-tour="game-card"]';

const probe = () => {
  const cards = Array.from(document.querySelectorAll('[data-tour="game-card"]'));
  const imgs  = cards.map((c) => c.querySelector('img')).filter(Boolean);
  return {
    cards: cards.length,
    imgs: imgs.length,
    loaded: imgs.filter((i) => i.complete && i.naturalWidth > 0).length,
    visible: imgs.filter((i) => getComputedStyle(i).opacity === '1').length,
    lazy: imgs.filter((i) => i.getAttribute('loading') === 'lazy').length,
    eager: imgs.filter((i) => i.getAttribute('loading') === 'eager').length,
    skeletons: cards.filter((c) => c.querySelector('.skeleton')).length,
  };
};

(async () => {
  const b = await chromium.launch({ executablePath: CHROME, headless: true });
  const p = await b.newPage({ viewport: { width: 1280, height: 780 } });
  const errs = [];
  p.on('pageerror', (e) => errs.push(String(e)));
  await p.goto('http://localhost:5180/preview.html', { waitUntil: 'domcontentloaded' });

  await p.waitForSelector(SEL, { timeout: 45000 });
  const t0 = Date.now();
  console.log('t=0.0s  cards mounted:', JSON.stringify(await p.evaluate(probe)));

  // THE SCENARIO: sit still, well past the 12s settle timer.
  for (const at of [5000, 12500, 15000]) {
    await p.waitForTimeout(Math.max(0, at - (Date.now() - t0)));
    console.log(`t=${((Date.now() - t0) / 1000).toFixed(1)}s  `, JSON.stringify(await p.evaluate(probe)));
  }

  const afterWait = await p.evaluate(probe);
  console.log('\n--- assertions ---');
  let fail = 0;
  const chk = (n, c, x = '') => { c ? console.log(`  PASS  ${n}${x ? `  [${x}]` : ''}`)
                                   : (fail++, console.log(`  FAIL  ${n}${x ? `  [${x}]` : ''}`)); };

  chk('cards rendered', afterWait.cards > 0, `${afterWait.cards} cards`);
  chk('THE REGRESSION: every <img> still in the DOM 15s after mount, unscrolled',
      afterWait.imgs === afterWait.cards, `${afterWait.imgs}/${afterWait.cards}`);
  chk('the settle timer removed the shimmer (no endless animation)',
      afterWait.skeletons === 0, `${afterWait.skeletons} skeletons left`);
  chk('the home featured row does not rely on lazy',
      afterWait.lazy === 0 && afterWait.eager === afterWait.imgs,
      `eager=${afterWait.eager} lazy=${afterWait.lazy}`);

  // now scroll to them, exactly as the user did
  await p.evaluate(() => document.querySelector('[data-tour="game-card"]')
                          ?.scrollIntoView({ block: 'center' }));
  await p.waitForTimeout(4000);
  const afterScroll = await p.evaluate(probe);
  console.log('\nafter scrolling to the row:', JSON.stringify(afterScroll));
  chk('covers are decoded', afterScroll.loaded > 0, `${afterScroll.loaded}/${afterScroll.imgs}`);
  chk('...and actually visible (opacity 1)', afterScroll.visible > 0, `${afterScroll.visible}/${afterScroll.imgs}`);
  chk('no page errors', errs.length === 0, errs.slice(0, 2).join(' | '));

  await p.screenshot({ path: process.argv[2] || 'covers.png' });
  await b.close();
  console.log(fail === 0 ? '\nALL_OK' : `\nFAILURES=${fail}`);
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error('ERR', e); process.exit(2); });
