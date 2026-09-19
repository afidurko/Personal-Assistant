# SwiftGuide integration — knowledge cartography cortex

Source: [afidurko/SwiftGuide](https://github.com/afidurko/SwiftGuide)  
Path: [`integrations/swiftguide`](../../integrations/swiftguide) (git submodule)

## What it adds to Cam’s brain map

SwiftGuide is a long-lived **Markdown → mind-map** knowledge project for the Swift
open-source ecosystem. Cam does **not** treat it as another agent runtime. It is a
**cartography cortex**: structured, hierarchical engrams Cam can browse the way
SwiftGuide presents Classification vs Application-Architecture maps.

| Capability | Role in Cam |
|---|---|
| Hierarchical mind maps (MindNode-export Markdown) | Dual-lens brain map: CNS anatomy **and** knowledge tree |
| Classification map | Taxonomy of tools / domains (like sensory/center/motor inventories) |
| Application-architecture map | How pieces compose a real app (iOS companion stack) |
| 2026 ecosystem report | Curated local-first / SwiftUI / Markdown-asset picks |
| DeMinds-style longevity | Pattern for keeping vault notes as maintainable map assets |

## Not this

- Not Cam’s executive brain (that’s nullclaw + chief)
- Not freeform vault search (that’s smart-second-brain)
- Not a second task-giver

## Connectome wiring

| Piece | Id |
|---|---|
| Sense | `sense.swiftguide.map` |
| Center | `center.cartography` |
| Hotspots | `hotspot.knowledge_map`, `hotspot.ios_stack` |
| Motors | `motor.vault`, `motor.mesh`, `motor.docs` (stack briefs) |

Live viz: `visualizations/connectome/` — toggle **Nervous system** ↔ **Mind map**.

## When Cam should use it

1. Aaron asks how to structure knowledge / maps in the vault  
2. iOS companion architecture or Swift stack choices  
3. Research that needs a **taxonomy** (browseable tree), not only RAG hits  
4. Distilling long Markdown corpora into maintainable map assets  

Distillates live under `vault/03-Projects/` and `vault/04-Research/`.
