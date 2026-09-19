# Card Recognition → 3D Character

Turn a detected 2D image (trading card, product label, poster) into an interactive AR entity — not just a textured plane — then control it with pupil / gaze.

Runnable demo: [`visualizations/card-recognition-spawn/`](../../visualizations/card-recognition-spawn/)  
Pupil policy: [`config/integrations/pupil.md`](../../config/integrations/pupil.md)

## Why this pattern

1. Track / detect the object  
2. Resolve a catalog record (what it is, stats, actions, model)  
3. Spawn a **3D character + spatial UI** anchored to that pose  
4. Drive interaction from **gaze** (Cam Pupil / iris / pointer dwell)

## Gaze control

```bash
python3 scripts/pupil-gaze-bridge.py   # GET :8766/gaze
npx serve -l 5179 visualizations/card-recognition-spawn
```

Choose **Use Cam Pupil gaze** (or webcam iris / pointer fallback). Dwell on `+` and moves.

## Minimal event contract

```js
// Any detector should emit:
scene.emit('card-detected', { cardId: 'volt-wisp', anchorEl: targetEntity });
```

Keep detectors dumb: they only report **ids + anchors**. Visualization never hard-codes recognition math.
