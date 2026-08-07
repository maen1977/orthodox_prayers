#!/usr/bin/env python3
"""Keep only the optional app build/release workflow.

Daily church content is generated inside the installed Android application and
must never require a scheduled GitHub Actions workflow.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
KEEP = {"church-prayers.yml"}
removed = []
for pattern in ("*.yml", "*.yaml"):
    for path in WORKFLOWS.glob(pattern):
        if path.name not in KEEP:
            path.unlink()
            removed.append(path.name)

present = {p.name for pattern in ("*.yml", "*.yaml") for p in WORKFLOWS.glob(pattern)}
if present != KEEP:
    raise SystemExit(f"Expected workflows {sorted(KEEP)}, found {sorted(present)}")
print(f"BUILD_WORKFLOW_ONLY_OK kept=church-prayers.yml removed={','.join(sorted(removed)) or 'none'}")
