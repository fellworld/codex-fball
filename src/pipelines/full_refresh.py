"""Run the standard model, simulation, and report refresh pipeline."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"


@dataclass(frozen=True)
class PipelineStep:
    title: str
    module: str


STEPS = (
    PipelineStep("Build model inputs", "features.model_input_builder"),
    PipelineStep("Simulate match score probabilities", "simulation.poisson_match_simulator"),
    PipelineStep("Simulate group stage", "simulation.group_stage_simulator"),
    PipelineStep("Generate pre-match reports and inject intelligence", "reports.generate_prematch_reports"),
)


def run_step(step: PipelineStep) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_ROOT)
    argv = (sys.executable, "-m", step.module)
    print(f"\n=== {step.title} ===")
    print("$ " + " ".join(argv))
    started = time.time()
    completed = subprocess.run(
        argv,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    elapsed = time.time() - started
    print(f"Finished {step.module} with exit code {completed.returncode} in {elapsed:.2f}s.")
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> int:
    started = time.time()
    for step in STEPS:
        run_step(step)
    print(f"\nFull refresh completed in {time.time() - started:.2f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
