import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_runtime_asset_budget():
    subprocess.run([sys.executable,'scripts/validate_runtime_asset_budget.py'],cwd=ROOT,check=True)
