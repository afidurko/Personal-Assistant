/**
 * Verify TalkingHead 3D Cam face loads and lip-syncs while speaking.
 * Requires: npm i -D puppeteer-core + running Vite on :5173
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
    '--use-fake-ui-for-media-stream',
    '--use-fake-device-for-media-stream',
    '--autoplay-policy=no-user-gesture-required',
    '--window-size=1280,900',
  ],
  defaultViewport: { width: 1280, height: 900 },
});

try {
  const page = await browser.newPage();
  page.on('console', (msg) => {
    const t = msg.type();
    if (t === 'error' || t === 'warning') {
      console.log(`[browser.${t}]`, msg.text().slice(0, 240));
    }
  });
  page.on('pageerror', (err) => console.log('[pageerror]', err.message));

  await page.goto('http://127.0.0.1:5173/?v=th-verify', {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  });
  await page.waitForSelector('.cam-stage', { timeout: 30000 });

  // Wait for TalkingHead canvas (or fallback)
  await page.waitForFunction(
    () => {
      const canvas = document.querySelector('.cam-face-th-mount canvas');
      const fallback = document.querySelector('.cam-face-fallback');
      const ready = document.querySelector('.cam-face-live.ready');
      return Boolean(canvas || fallback || ready);
    },
    { timeout: 45000 },
  );

  // User gesture to unlock AudioContext
  await page.click('.cam-stage', { delay: 20 }).catch(() => {});

  const boot = await page.evaluate(() => {
    const canvas = document.querySelector('.cam-face-th-mount canvas');
    const live = document.querySelector('.cam-face-live');
    const fallback = document.querySelector('.cam-face-fallback');
    return {
      hasCanvas: Boolean(canvas),
      canvasW: canvas?.width || 0,
      canvasH: canvas?.height || 0,
      ready: live?.classList.contains('ready') || false,
      fallback: Boolean(fallback),
      cls: live?.className || '',
    };
  });
  console.log('boot', JSON.stringify(boot));

  if (!boot.hasCanvas || boot.fallback) {
    console.error('TalkingHead did not mount a WebGL canvas');
    process.exit(3);
  }

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

    let best = null;
    const t0 = performance.now();
    while (performance.now() - t0 < 90000) {
      const el = document.querySelector('.cam-face-live');
      const canvas = document.querySelector('.cam-face-th-mount canvas');
      const status = document.querySelector('.cam-avatar-status')?.textContent || '';
      if (el && canvas) {
        const sample = {
          t: Math.round(performance.now() - t0),
          cls: el.className,
          status,
          ready: el.classList.contains('ready'),
          mouthOpen: el.classList.contains('mouth-open'),
          speaking: el.classList.contains('expr-speak'),
        };
        if (sample.mouthOpen) {
          return { best: sample, caughtSpeak: true };
        }
        if (!best || sample.speaking) best = sample;
      }
      await new Promise((r) => setTimeout(r, 200));
    }
    return { best, caughtSpeak: Boolean(best?.mouthOpen) };
  });

  console.log(JSON.stringify(result, null, 2));
  if (!result.caughtSpeak) process.exit(2);
} finally {
  await browser.close();
}
