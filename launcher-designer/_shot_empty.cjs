const { chromium } = require('playwright-core');
(async () => {
  const b = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  const p = await b.newPage({ viewport: { width: 420, height: 950 } });
  await p.goto('https://hebrew-translation-hub.com/translate', { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(2500);
  // enter the first game's workspace
  const card = p.locator('button, a').filter({ hasText: 'Cyberpunk 2077' }).first();
  await card.click({ timeout: 15000 }).catch(() => {});
  await p.waitForTimeout(3000);
  const m = await p.evaluate(() => {
    const el = Array.from(document.querySelectorAll('div'))
      .find(d => /כדי להתחיל|לא נמצאו שורות/.test(d.textContent || '') && d.children.length <= 3 && d.className.includes('text-center'));
    if (!el) return { found: false };
    const r = el.getBoundingClientRect();
    return { found: true, left: Math.round(r.left), right: Math.round(r.right),
             center: Math.round(r.left + r.width / 2), vw: window.innerWidth };
  });
  console.log(JSON.stringify(m));
  await p.screenshot({ path: 'C:/tmp/translate_empty.png' });
  await b.close();
})();
