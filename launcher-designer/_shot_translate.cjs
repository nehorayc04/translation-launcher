const { chromium } = require('playwright-core');
(async () => {
  const b = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  for (const w of [420, 700, 900]) {
    const p = await b.newPage({ viewport: { width: w, height: 1000 } });
    await p.goto('https://hebrew-translation-hub.com/translate', { waitUntil: 'networkidle', timeout: 60000 });
    await p.waitForTimeout(2500);
    await p.screenshot({ path: `C:/tmp/translate_${w}.png` });
    const info = await p.evaluate(() => Array.from(document.querySelectorAll('div'))
      .filter(d => getComputedStyle(d).display === 'grid' && d.getBoundingClientRect().width > 200)
      .slice(0, 6)
      .map(d => ({ cols: getComputedStyle(d).gridTemplateColumns.split(' ').length, cls: d.className.slice(0, 60) })));
    console.log(w + 'px -> ' + JSON.stringify(info));
    await p.close();
  }
  await b.close();
})();
