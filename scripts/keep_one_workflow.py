#!/usr/bin/env python3
"""Keep exactly one simple GitHub Actions workflow for Church Prayers."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
KEEP = "church-prayers.yml"


def main() -> None:
    WORKFLOWS.mkdir(parents=True, exist_ok=True)
    removed: list[str] = []
    for pattern in ("*.yml", "*.yaml"):
        for path in sorted(WORKFLOWS.glob(pattern)):
            if path.name == KEEP:
                continue
            if path.is_file() or path.is_symlink():
                path.unlink()
                removed.append(path.name)

    kept = WORKFLOWS / KEEP
    if not kept.is_file():
        raise SystemExit(f"Required workflow is missing: {kept.relative_to(ROOT)}")

    removed_text = ",".join(removed) if removed else "none"
    print(f"ONE_WORKFLOW_OK kept={KEEP} removed={removed_text}")


if __name__ == "__main__":
    main()
