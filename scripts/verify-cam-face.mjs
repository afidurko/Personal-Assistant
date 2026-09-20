/**
 * Verify illustrated Cam face speech animation (dev only).
 * Requires: npm i -D puppeteer-core
 * Usage: node scripts/verify-cam-face.mjs
 */
import puppeteer from 'puppeteer-core';

const browser = await puppeteer.launch({
  executablePath: '/usr/local/bin/google-chrome',
  headless: true,
  args: ['--no-sandbox', '--disable-gpu', '--window-size=1280,900'],
  defaultViewport: { width: 1280, height: 900 },
});

try {
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:5173/?v=faceverify2', {
    waitUntil: 'networkidle2',
    timeout: 30000,
  });
  await page.waitForSelector('.cam-face-svg', { timeout: 15000 });

  const result = await page.evaluate(async () => {
    const input = document.querySelector('.cam-stage-form input');
    const form = document.querySelector('.cam-stage-form');
    if (!input || !form) return { error: 'no form' };
    const nativeSet = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value',
    ).set;
    nativeSet.call(input, 'Please give a warm multi-sentence greeting');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    form.requestSubmit();

    let best = null;
    const t0 = performance.now();
    while (performance.now() - t0 < 14000) {
      const el = document.querySelector('.cam-face-live');
      const svg = document.querySelector('.cam-face-svg');
      if (el && svg) {
        const sample = {
          t: Math.round(performance.now() - t0),
          cls: el.className,
          hasSvg: true,
          status: document.querySelector('.cam-avatar-status')?.textContent || '',
        };
        if (!best || sample.cls.includes('mouth-open')) best = sample;
        if (sample.cls.includes('expr-speak') && sample.cls.includes('mouth-open')) {
          return { best: sample, caughtOpen: true };
        }
      }
      await new Promise((r) => setTimeout(r, 120));
    }
    return { best, caughtOpen: Boolean(best?.cls.includes('mouth-open')) };
  });

  console.log(JSON.stringify(result, null, 2));
  if (!result.caughtOpen) process.exit(2);
} finally {
  await browser.close();
}
