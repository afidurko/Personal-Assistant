# PaddleDetection integration

Source: [afidurko/PaddleDetection](https://github.com/afidurko/PaddleDetection) (`release/2.9`)  
Path: [`integrations/paddledetection`](../../integrations/paddledetection) (git submodule)

## Role in the team

PaddleDetection is the **vision tool layer** — object detection, instance
segmentation, tracking, pose, face/person analysis toolkits. It replaces the
old Lucida IMM/FACE/DIG *idea* with a modern, maintained stack.

It is **not** the brain and **not** always-on surveillance.

| Concern | Owner |
|---|---|
| Thinking / planning / subagents | nullclaw |
| Task queue / persistence | nulltickets |
| Scheduling | nullboiler |
| Human override | nullhub |
| Local CLI utilities | Jarvis |
| Vision inference on images/video you provide | **PaddleDetection** |

The `vision` role (and subagents summoned by `docs` / `ops` / `research`) may
run inference on **explicitly provided** media. Camera capture, continuous
monitoring, or analyzing other people’s photos without consent are
**approval-gated** (see `identity/BOUNDARIES.md`).

## Install (on your machine — heavy)

```bash
git submodule update --init --recursive
cd integrations/paddledetection
# follow upstream README_en.md / docs for PaddlePaddle + requirements
pip install -r requirements.txt
# download chosen model weights as needed (not stored in this repo)
```

Prefer lightweight deployed models (e.g. PicoDet) when the assistant only needs
quick object/document layout cues. Keep large training workflows offline and
human-initiated.

## Mesh bridge

Inference summaries (not raw tensors) go to `mesh/vision`:

```bash
python3 scripts/pack-vision-result.py \
  --image path/to/input.jpg \
  --detections path/to/bbox.json \
  --out /tmp/mesh-vision.json
```

When nulltickets is up, curator/`vision` `PUT`s that document under `mesh/vision`.

## Useful entry points (upstream)

- `tools/infer.py` — single-image inference
- `deploy/` — deployment / prediction demos
- `configs/` — model zoo (PP-YOLOE, PicoDet, RT-DETR, TinyPose, PP-Human, …)

## Privacy defaults

- No background camera loop
- No FaceTime/video call content analysis unless you explicitly request it for that session
- Distill labels + boxes + confidence into mesh; do not retain raw frames unless you ask
