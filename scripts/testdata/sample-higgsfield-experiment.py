"""Sample Higgsfield-style experiment for Cam dry-run validation.

This fixture is intentionally free of torch/deepspeed imports so
scripts/higgsfield-run.py can AST-scan it offline.
"""

from higgsfield.experiment import experiment, param


@experiment("cam_alpaca_smoke")
@param("lr", default=1e-5)
@param("max_steps", default=10)
def train(params):
    """Placeholder train loop — never executed by Cam dry-run."""
    lr = params.lr
    steps = params.max_steps
    for _ in range(steps):
        loss = 0.0 * lr
        _ = loss
