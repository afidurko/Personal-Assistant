# Aaron-only voice gate

Cam listens to **Aaron only**. In noisy rooms or when others are talking, non-Aaron speech is rejected.

- Config: `config/identity/aaron-voice-gate.json`
- Enroll once (~10s) in the companion / home UI
- Threshold: 0.85 quiet · 0.88 noisy
- Check: `python3 scripts/aaron-voice-gate-check.py`

Authorized by Aaron 2026-09-19.
