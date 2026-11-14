// Rendert eine 3D-Szene (schaubild/drei.py) im eingebauten Chromium: node render3d.js <auftrag.json> <ausgabeordner>
// auftrag.json = {size, elemente, bilder: [{t, st, kamera}, ...]} -> <ordner>/b_00000.png … + lage.json
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const [auftragPfad, aus] = process.argv.slice(2);
  const auftrag = JSON.parse(fs.readFileSync(auftragPfad, 'utf8'));
  fs.mkdirSync(aus, { recursive: true });
  const opts = { args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] };
  if (process.env.CUDI_CHROMIUM) opts.executablePath = process.env.CUDI_CHROMIUM;
  const browser = await chromium.launch(opts);
  const page = await browser.newPage({ viewport: { width: auftrag.size, height: auftrag.size } });
  const fehler = [];
  page.on('pageerror', (e) => fehler.push(e.message));
  await page.goto('file://' + path.join(__dirname, 'szene3d.html'));
  const ok = await page.evaluate((d) => window.init(d), { size: auftrag.size, elemente: auftrag.elemente });
  if (!ok || fehler.length) throw new Error('3D-Bühne startet nicht: ' + fehler.join('; '));
  const lagen = [];
  const N = 12;                                           // Bilder je Aufruf
  for (let i = 0; i < auftrag.bilder.length; i += N) {
    const teil = await page.evaluate((l) => window.bilder(l), auftrag.bilder.slice(i, i + N));
    teil.forEach((b, j) => {
      fs.writeFileSync(path.join(aus, `b_${String(i + j).padStart(5, '0')}.png`), Buffer.from(b.png.split(',')[1], 'base64'));
      lagen.push(b.lage);
    });
    if (fehler.length) throw new Error('3D-Bühne: ' + fehler.join('; '));
  }
  fs.writeFileSync(path.join(aus, 'lage.json'), JSON.stringify(lagen));
  await browser.close();
  console.log('OK ' + auftrag.bilder.length);
})().catch((e) => { console.error('FEHLER ' + (e && e.message || e)); process.exit(1); });
