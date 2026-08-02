"""Shared pytest path setup for directly importable repository scripts.

Production scripts are intentionally executable both as ``python scripts/x.py``
and as modules loaded by tests. Adding the scripts directory once makes every
test file independent of execution order and avoids relying on an earlier test
to mutate ``sys.path``.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
