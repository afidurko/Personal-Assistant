/**
 * Verify Cam’s Audio2Face photo mesh loads and speaks (mouth-open).
 */
import puppeteer from 'puppeteer-core';

const browser = await puppeteer.launch({
  executablePath: '/usr/local/bin/google-chrome',
  headless: 'new',
  args: [
    '--no-sandbox',
    '--use-gl=angle',
    '--use-angle=swiftshader-webgl',
    '--enable-webgl',
    '--ignore-gpu-blocklist',
    '--enable-unsafe-swiftshader',
    '--autoplay-policy=no-user-gesture-required',
    '--window-size=1280,900',
  ],
  defaultViewport: { width: 1280, height: 900 },
});

try {
  const page = await browser.newPage();
  page.on('pageerror', (err) => console.log('[pageerror]', err.message));
  await page.goto('http://127.0.0.1:5173/?v=a2f-verify', {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  });
  await page.waitForSelector('.cam-stage', { timeout: 30000 });
  await page.waitForFunction(
    () =>
      document.querySelector('.cam-face-live.ready') ||
      document.querySelector('.cam-face-fallback img'),
    { timeout: 45000 },
  );

  const boot = await page.evaluate(() => {
    const canvas = document.querySelector('.cam-face-th-mount canvas');
    const live = document.querySelector('.cam-face-live');
    const fallback = document.querySelector('.cam-face-fallback img');
    return {
      hasCanvas: Boolean(canvas),
      canvasW: canvas?.width || 0,
      ready: live?.classList.contains('ready') || false,
      fallback: Boolean(fallback),
      engine: live?.classList.contains('ready') ? 'audio2face' : 'still',
    };
  });
  console.log('boot', JSON.stringify(boot));
  if (!boot.hasCanvas && !boot.fallback) {
    console.error('Cam avatar did not mount');
    process.exit(3);
  }

  await page.click('.cam-stage').catch(() => {});
  const result = await page.evaluate(async () => {
    const input = document.querySelector('.cam-stage-form input');
    const form = document.querySelector('.cam-stage-form');
    if (!input || !form) return { error: 'no form' };
    const nativeSet = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value',
    ).set;
    nativeSet.call(input, 'hi');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    form.requestSubmit();

    const t0 = performance.now();
    let best = null;
    while (performance.now() - t0 < 90000) {
      const el = document.querySelector('.cam-face-live');
      const sample = {
        t: Math.round(performance.now() - t0),
        cls: el?.className || '',
        status: document.querySelector('.cam-avatar-status')?.textContent || '',
        mouthOpen: el?.classList.contains('mouth-open') || false,
        ready: el?.classList.contains('ready') || false,
      };
      if (sample.mouthOpen) return { best: sample, caughtSpeak: true };
      if (!best || sample.cls.includes('expr-speak')) best = sample;
      await new Promise((r) => setTimeout(r, 200));
    }
    return { best, caughtSpeak: false };
  });
  console.log(JSON.stringify(result, null, 2));
  if (!result.caughtSpeak) process.exit(2);
} finally {
  await browser.close();
}
