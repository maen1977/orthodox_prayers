#!/usr/bin/env python3
"""Keep only the simple app build workflow and the separate daily update workflow."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
KEEP = {"church-prayers.yml", "update.yml"}
removed = []
for pattern in ("*.yml", "*.yaml"):
    for path in WORKFLOWS.glob(pattern):
        if path.name not in KEEP:
            path.unlink()
            removed.append(path.name)

present = {p.name for pattern in ("*.yml", "*.yaml") for p in WORKFLOWS.glob(pattern)}
if present != KEEP:
    raise SystemExit(f"Expected workflows {sorted(KEEP)}, found {sorted(present)}")
print(f"TWO_WORKFLOWS_OK kept={','.join(sorted(KEEP))} removed={','.join(sorted(removed)) or 'none'}")
