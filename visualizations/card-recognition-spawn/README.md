# Card recognition → 3D spawn (A-Frame)

Adapt the “scan a physical card → learn what it is → spawn more than a 2D overlay” pattern with [A-Frame](https://github.com/afidurko/aframe).

This visualization mirrors AR trading-card demos:

1. **Detect** a 2D image target (printed card)
2. **Identify** it against a catalog (name, stats, moves, model recipe)
3. **Transform** into a spatial experience: floating digital card, **3D character**, arena, HP bar, move buttons

Original “Arcana Cards” art is included (no third-party character IP).

## Quick start (lab mode — no camera)

Serve the repo (or just this folder) over HTTP:

```bash
npx --yes serve -l 5179 visualizations/card-recognition-spawn
```

Open http://localhost:5179/ and tap a card on the table.

Event bus:

`card-detected` → `card-resolved` → `character-spawned` → `move-selected`

## Pipeline map

| Stage | Component | Event | Responsibility |
|---|---|---|---|
| Detect | `card-detector` | `card-detected` | Emit `{ cardId, anchorEl }` from lab click, MindAR, or external CV |
| Identify | `card-catalog` | `catalog-ready` | Load `catalog.json`, `resolve(id)` |
| Orchestrate | `recognition-pipeline` | `card-resolved` | Join detection + catalog |
| Visualize | `character-spawner` + `procedural-creature` | `character-spawned` | Digital card + 3D body + HP + moves |
| Stage | `battle-arena` | listens to spawn | Table-scale arena ring |
| Interact | move buttons | `move-selected` | Punch animation + damage demo |

The leap past “2D VR”: after identity is known, spawn a **separate 3D entity** at the card pose, then attach spatial UI that follows that anchor.

## Wiring real object recognition

### A) MindAR image tracking

1. Print the SVGs in `assets/`
2. Compile with the [MindAR compiler](https://hiukim.github.io/mind-ar-js-doc/tools/compile) → `targets/targets.mind`
3. Open `mindar.html` on a phone (HTTPS)

`mindar-bridge` maps `targetIndex` → catalog id and calls `card-detector.reportDetection()`.

### B) WebXR hit-test + classifier

Use A-Frame `ar-hit-test` to place the arena, then feed frames to a classifier. When you get an id:

```js
scene.components['card-detector'].reportDetection('volt-wisp', anchorEntity);
```

### C) Cam / PaddleDetection

Keep detection in `integrations/paddledetection` (or a companion). Stream `{ id, pose }` into the page and call `reportDetection`. A-Frame owns visualization only.

## Upstream to afidurko/aframe

This folder is structured to drop into:

`examples/showcase/card-recognition-spawn/`

in [afidurko/aframe](https://github.com/afidurko/aframe). A matching docs guide lives at
`docs/guides/card-recognition-to-3d-character.md` in this PR for Cam’s vault/docs mirror;
cherry-pick into the A-Frame fork when write access is available.

## Extending past procedural shapes

```html
<a-entity gltf-model="#volt-wisp-glb" animation-mixer="clip: idle"></a-entity>
```

Add `model` URLs on catalog entries and prefer glTF in `character-spawner` when present.
