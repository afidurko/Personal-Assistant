# Aaron — visual identity (enrollment notes)

**Enrolled:** 2026-09-16 · **Subject:** Aaron · **Purpose:** face recognition / photo↔video match

Private originals live under `identity/aaron/local/photos/` (gitignored). This note is the durable description Cam uses.

## Primary face cluster (Aaron)

Sources:
- `aaron-01-mirror-selfie.jpg` — mirror selfie, iPhone Pro, business-casual
- `aaron-02-gym-pair.jpg` — **Aaron = left** (Yankees Baseball tee, yellow belt); right person is not Aaron
- `aaron-03-closeup-glasses.jpg` — close frontal selfie, glasses glare
- `aaron-04-cafe-cap.jpg` — cafe / laptop, hat on

### Stable traits
| Trait | Observation |
|---|---|
| Hair | Dark; curly/wavy with volume **or** short-cropped (gym) |
| Eyes | Dark; often behind glasses (sometimes without) |
| Glasses | Thin rectangular / semi-rimless metal frames; frequent blue screen reflection — **not always worn** |
| Facial hair | Mustache + groomed goatee / short beard, or clean-shaven (gym) |
| Skin | Light–medium / olive |
| Build / style | Young adult male; casual → athletic → business-casual |

### Appearance variation Cam must handle
- With / without glasses
- Curly longer hair vs short athletic cut
- Facial hair present vs reduced
- Smiling wide (gym) vs neutral (selfie / cafe)

### Recognition challenges
- Glasses + screen glare on lenses
- Cap / hat covering hair (`aaron-04`)
- Mirror selfie angle + phone occlusion (`aaron-01`)
- Multi-person frames — only match **Aaron’s** face (`aaron-02` left)

## Non-Aaron in enrolled media
- `aaron-02-gym-pair.jpg` **right**: light buzz cut, arm tattoos, Punch Gear tee — **not Aaron**; ignore for identity match

## Voice / video
None yet. When Aaron adds talking video of the same face, link via photo↔video match.

## Match policy
- Primary cluster = Aaron for `sense.aaron.face`
- Reject faces outside enrolled cluster (including gym-pair right) for `switch.identity`
