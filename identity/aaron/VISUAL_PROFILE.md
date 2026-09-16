# Aaron — visual identity (enrollment notes)

**Enrolled:** 2026-09-16 · **Subject:** Aaron · **Purpose:** face recognition / photo↔video match

Private originals live under `identity/aaron/local/photos/` (gitignored). This note is the durable description Cam uses.

## Primary face cluster (high confidence = Aaron)

Sources:
- `aaron-01-mirror-selfie.jpg` — mirror selfie, iPhone Pro, business-casual
- `aaron-03-closeup-glasses.jpg` — close frontal selfie, glasses glare
- `aaron-04-cafe-cap.jpg` — cafe / laptop, hat on

### Stable traits
| Trait | Observation |
|---|---|
| Hair | Dark, thick, curly / wavy; volume on top |
| Eyes | Dark; often behind glasses |
| Glasses | Thin rectangular / semi-rimless metal frames; frequent blue screen reflection on lenses |
| Facial hair | Mustache + groomed goatee / short beard (varies by photo) |
| Skin | Light–medium / olive |
| Build / style | Young adult male; casual → business-casual |

### Recognition challenges to train for
- Glasses + screen glare on lenses
- Cap / hat covering hair (`aaron-04`)
- Mirror selfie angle + phone occlusion (`aaron-01`)
- Orientation / couch angle (`aaron-03`)

## Multi-person photo — needs Aaron label

- `aaron-02-gym-pair.jpg` — **two faces** (gym / “THE EMPIRE” certificate, yellow belt)
  - Left: dark short hair, no glasses, Yankees Baseball Nike tee, yellow belt
  - Right: light buzz cut, tattoos on left arm, Punch Gear tee
  - **Not auto-enrolled as Aaron** until Aaron marks which person (or both if neither is primary)

## Voice / video
None yet. When Aaron adds talking video of the same face, link via `scripts/aaron-enroll-manifest.py` photo↔video match.

## Match policy
- Primary cluster (01, 03, 04) = Aaron for `sense.aaron.face`
- Reject faces outside enrolled cluster as non-Aaron for `switch.identity`
- Do not treat gym-pair faces as Aaron until labeled
