# AR card battle (phone composite)

Visual recreation of the Instagram AR TCG flow for A-Frame / Cam:

**camera desk → corner brackets → + scan → holographic card → 3D creature on green arena → floating moves / HP / turn panels**

This is the look of the reference clips (wooden table, ACTIVE brackets, frosted HUD, stadium disk, fighters with HP bars, bottom action line). Creature IP is original Arcana Cards—not Pokémon.

## Run

```bash
npx --yes serve -l 5179 visualizations/card-recognition-spawn
```

Open http://localhost:5179/

1. Press **+** (or tap the ACTIVE card) — detects Volt Wisp, lifts a hologram, spawns the 3D fighter on the arena  
2. Press **+** again — opponent joins  
3. Tap **Spark Jab** / **Arc Combo** — action banner + HP update (same beat as “ELECTABUZZ USED LIGHT PUNCH!”)

## A-Frame wiring

Same pipeline events as before (`card-detected` → catalog → spawn). MindAR / WebXR / PaddleDetection should call into this UI shell or the earlier `components/*` spawner once GPU AR is available. Cherry-pick into [afidurko/aframe](https://github.com/afidurko/aframe) under `examples/showcase/card-recognition-spawn/`.
