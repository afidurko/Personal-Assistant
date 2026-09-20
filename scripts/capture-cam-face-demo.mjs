/**
 * Capture illustrated Cam speaking face frames → mp4 demo.
 * Requires: npm i -D puppeteer-core
 * Usage: node scripts/capture-cam-face-demo.mjs
 */
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const FRAMES = '/tmp/cam-face-frames';
const OUT_MP4 = '/opt/cursor/artifacts/cam_illustrated_face_speak.mp4';
const OUT_IDLE = '/opt/cursor/artifacts/screenshots/cam_illustrated_idle.png';
const OUT_SPEAK = '/opt/cursor/artifacts/screenshots/cam_illustrated_speaking.png';

fs.rmSync(FRAMES, { recursive: true, force: true });
fs.mkdirSync(FRAMES, { recursive: true });
fs.mkdirSync(path.dirname(OUT_MP4), { recursive: true });

const browser = await puppeteer.launch({
  executablePath: '/usr/local/bin/google-chrome',
  headless: true,
  args: ['--no-sandbox', '--disable-gpu', '--window-size=1280,900'],
  defaultViewport: { width: 1280, height: 900 },
});

try {
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:5173/?v=illustrated', {
    waitUntil: 'networkidle2',
    timeout: 30000,
  });
  await page.waitForSelector('.cam-face-svg', { timeout: 15000 });

  const wrap = await page.$('.cam-avatar-face-wrap');
  if (wrap) await wrap.screenshot({ path: OUT_IDLE, type: 'png' });

  await page.evaluate(() => {
    const input = document.querySelector('.cam-stage-form input');
    const form = document.querySelector('.cam-stage-form');
    const nativeSet = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value',
    ).set;
    nativeSet.call(
      input,
      'Please give a warm multi-sentence greeting so I can watch you speak',
    );
    input.dispatchEvent(new Event('input', { bubbles: true }));
    form.requestSubmit();
  });

  let i = 0;
  let savedOpen = false;
  const t0 = Date.now();
  while (Date.now() - t0 < 13000) {
    const stage = await page.$('.cam-avatar-stage');
    if (stage) {
      const file = path.join(FRAMES, `f_${String(i).padStart(4, '0')}.png`);
      await stage.screenshot({ path: file, type: 'png' });
      i += 1;
    }
    const info = await page.evaluate(() => {
      const el = document.querySelector('.cam-face-live');
      return el
        ? {
            cls: el.className,
            status: document.querySelector('.cam-avatar-status')?.textContent || '',
          }
        : null;
    });
    if (info && !savedOpen && info.cls.includes('mouth-open')) {
      const face = await page.$('.cam-avatar-face-wrap');
      if (face) await face.screenshot({ path: OUT_SPEAK, type: 'png' });
      savedOpen = true;
    }
    await new Promise((r) => setTimeout(r, 110));
  }

  const ff = spawnSync(
    'ffmpeg',
    [
      '-y',
      '-framerate',
      '9',
      '-i',
      path.join(FRAMES, 'f_%04d.png'),
      '-c:v',
      'libx264',
      '-pix_fmt',
      'yuv420p',
      '-movflags',
      '+faststart',
      OUT_MP4,
    ],
    { encoding: 'utf8' },
  );
  if (ff.status !== 0) {
    console.error(ff.stderr);
    process.exit(1);
  }
  console.log(
    JSON.stringify({
      frames: i,
      savedOpen,
      mp4: OUT_MP4,
      idle: OUT_IDLE,
      speak: savedOpen ? OUT_SPEAK : null,
      size: fs.statSync(OUT_MP4).size,
    }),
  );
} finally {
  await browser.close();
}
