# Card Recognition → 3D Character

Turn a detected 2D image (trading card, product label, poster) into an interactive 3D A-Frame entity — not just a textured plane.

Runnable demo: [`visualizations/card-recognition-spawn/`](../../visualizations/card-recognition-spawn/)  
A-Frame fork target path: `examples/showcase/card-recognition-spawn/` in [afidurko/aframe](https://github.com/afidurko/aframe)

## Why this pattern

Image overlays alone feel flat. The stronger product pattern is:

1. Track / detect the object
2. Resolve a catalog record (what it is, stats, actions, model)
3. Spawn a **3D character + spatial UI** anchored to that pose
4. Drive interaction from the catalog (moves, HP, animations)

## Minimal event contract

```js
// Any detector (MindAR, WebXR + CV, native companion) should emit:
scene.emit('card-detected', { cardId: 'volt-wisp', anchorEl: targetEntity });

// Pipeline resolves catalog and emits:
scene.emit('card-resolved', { card: catalogEntry, anchorEl: targetEntity });

// Spawner creates the 3D visualization:
scene.emit('character-spawned', { card, entity: spawnedRoot });
```

Keep detectors dumb: they only report **ids + anchors**. Visualization never hard-codes recognition math.

## Choosing a detector

| Approach | Best for | A-Frame hook |
|---|---|---|
| [MindAR](https://hiukim.github.io/mind-ar-js-doc/) image targets | Printed cards in mobile browsers | `mindar-image-target` → bridge → `card-detected` |
| [ar-hit-test](https://aframe.io/docs/1.7.0/components/ar-hit-test.html) + classifier | Table placement on XR headsets | Place arena, then inject id from CV |
| External CV (PaddleDetection / companion) | Custom detectors, heavy models | WebSocket → `reportDetection(id, anchor)` |

## Beyond 2D

After identity is known:

- Prefer `gltf-model` + `animation-mixer` for production characters
- Use procedural primitives only for prototypes / IP-safe demos
- Attach HP bars and action buttons as child entities of the spawn root so they follow the card
- Put shared stage geometry (arena) on the table plane once, not per card texture
