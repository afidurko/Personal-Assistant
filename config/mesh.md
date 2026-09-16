# Mesh namespaces

Shared across every agent. Backed by nulltickets `/store`.

| namespace | purpose |
|---|---|
| `mesh/prefs` | preferences from questionnaire |
| `mesh/facts` | durable facts about you / world |
| `mesh/people` | people graph notes |
| `mesh/projects` | active projects |
| `mesh/research` | research briefs + source lists |
| `mesh/careers` | job search state |
| `mesh/docs` | document index / templates |
| `mesh/runs` | distilled run outcomes |
| `mesh/open-questions` | unresolved questions for the team |

## Write rules

- Distill; do not dump raw chat transcripts
- Tag sensitivity: `public` | `team` | `private`
- Private never leaves local store / approved channels
- Curator dedupes conflicting facts; human resolves ties

## Read rules

- Before claiming work, search relevant namespaces
- Cite mesh keys used in run events for auditability
