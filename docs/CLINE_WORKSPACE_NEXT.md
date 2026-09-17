# Suggestive implementations (post-merge)

Standing ideas that improve Cam↔Cline workspace integration further.
None block merge; implement when Aaron wants the next slice.

1. **Live nulltickets PUT** — `export-cline-tickets.py --put` when nulltickets HTTP is up.
2. **Hub zen mode** — `run-cline.py --zen` for long background coding with menubar notify.
3. **Per-role model defaults** — registry field `preferred_model` per workspace.
4. **Diff gate** — refuse `--yolo` on `main` unless `switch.autonomy` standing + ticket exists.
5. **Workspace watch** — filesystem watcher that refreshes registry `exists` + last git SHA into mesh.
6. **Schedule delivery** — wire `sync-cline-schedules.py` `--delivery-adapter` to Cam converse/Tailscale.
7. **Team templates** — `config/workspaces/teams.json` for named multi-repo Cline teams.
8. **CI artifact upload** — attach `ci-sim-1m.json` + unit junit to PR checks.
