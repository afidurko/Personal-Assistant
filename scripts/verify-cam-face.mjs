/**
 * One-shot Cam face lip-sync verification (dev only).
 * Usage: node scripts/verify-cam-face.mjs
 */
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';

const OUT = '/opt/cursor/artifacts/screenshots';
fs.mkdirSync(OUT, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: '/usr/local/bin/google-chrome',
  headless: true,
  args: ['--no-sandbox', '--disable-gpu', '--window-size=1280,900'],
  defaultViewport: { width: 1280, height: 900 },
});

try {
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:5173/?v=faceverify', {
    waitUntil: 'networkidle2',
    timeout: 30000,
  });
  await page.waitForSelector('.cam-face-live', { timeout: 15000 });
  await page.screenshot({
    path: path.join(OUT, 'cam_face_verify_idle.png'),
    type: 'png',
  });

  const result = await page.evaluate(async () => {
    const input = document.querySelector('.cam-stage-form input');
    const form = document.querySelector('.cam-stage-form');
    if (!input || !form) return { error: 'no form' };
    const nativeSet = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value',
    ).set;
    nativeSet.call(input, 'Please give a warm multi-sentence greeting so I can watch you speak');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    form.requestSubmit();

    let best = null;
    let openShot = null;
    const t0 = performance.now();
    while (performance.now() - t0 < 16000) {
      const el = document.querySelector('.cam-face-live');
      const mouth = document.querySelector('.cam-face-mouth');
      if (el && mouth) {
        const open = Number(getComputedStyle(el).getPropertyValue('--mouth-open') || 0);
        const rect = mouth.getBoundingClientRect();
        const sample = {
          t: Math.round(performance.now() - t0),
          open,
          h: Math.round(rect.height),
          w: Math.round(rect.width),
          cls: el.className,
          status: document.querySelector('.cam-avatar-status')?.textContent || '',
        };
        if (!best || sample.h > best.h) best = sample;
        if (!openShot && sample.cls.includes('mouth-open') && sample.h >= 18) {
          openShot = sample;
          break;
        }
      }
      await new Promise((r) => setTimeout(r, 120));
    }
    return { best, openShot, caughtOpen: Boolean(openShot) };
  });

  // If we caught open mid-loop break, take screenshot now while still speaking
  if (result.caughtOpen) {
    await page.screenshot({
      path: path.join(OUT, 'cam_face_verify_speaking.png'),
      type: 'png',
    });
    const face = await page.$('.cam-avatar-face-wrap');
    if (face) {
      await face.screenshot({
        path: path.join(OUT, 'cam_face_verify_speaking_close.png'),
        type: 'png',
      });
    }
    // Hold a bit more of the utterance for a second screenshot
    await new Promise((r) => setTimeout(r, 800));
    await page.screenshot({
      path: path.join(OUT, 'cam_face_verify_speaking2.png'),
      type: 'png',
    });
  } else {
    await page.screenshot({
      path: path.join(OUT, 'cam_face_verify_end.png'),
      type: 'png',
    });
  }

  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
