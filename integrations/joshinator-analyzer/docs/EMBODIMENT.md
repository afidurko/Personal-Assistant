# IP-safe 3D Embodiment

## Goal

After OCR identifies a sports card, Joshinator spawns a **3D arena champion**
beside the live stream — going beyond a flat 2D card preview.

## Pipeline

```text
frame → OCR / audio fusion → card_info
      → embodiment_service.resolve(card_info)
      → analysis_result.embodiment
      → EmbodimentViewer (Three.js procedural mesh)
```

## Copyright / IP rules (hard)

This feature **must not**:

- Ship or load Pokémon, Nintendo, or any other franchise character meshes
- Embed team logos, league marks, or manufacturer trade dress as 3D assets
- Download third-party GLB/GLTF character packs into the repo

This feature **does**:

- Use **original** archetype names (`Diamond Arc`, `Court Pulse`, …)
- Render **procedural primitives** only (capsule / cone / sphere / ring / fins)
- Tint colors from a **stable hash** of card identity (not brand palettes)
- Label athletes by factual OCR `player_name` text only

Every payload includes:

```json
{
  "source": "joshinator-original-catalog",
  "license_note": "Original procedural embodiment. No third-party character IP, logos, or franchise assets."
}
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/embodiment/catalog` | List original archetypes |
| `POST` | `/api/embodiment/resolve` | `{ card_info, confidence }` → spawn payload |

Socket.IO `analysis_result` now includes optional `embodiment`.

## Extending safely

1. Add a new entry to `embodiment_catalog.py` with original naming.
2. Keep `mesh_defaults` as primitive recipes — never file URLs to character IP.
3. Prefer licensed-original or CC0 assets only if you later leave procedural mode;
   document provenance in this file before merging.
