const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const [dir, outDir, px] = process.argv.slice(2); const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: +px, height: +px } });
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.svg'))) {
    const svg = fs.readFileSync(dir + '/' + f, 'utf8').replace(/width="\d+" height="\d+"/, `width="${px}" height="${px}"`);
    await p.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
    await p.screenshot({ path: outDir + '/' + f.replace('.svg', '.png'), omitBackground: true, clip: { x: 0, y: 0, width: +px, height: +px } });
  }
  await b.close();
})();
