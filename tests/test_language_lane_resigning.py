from __future__ import annotations

import base64
import shutil
import subprocess
import sys
from pathlib import Path


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=cwd, check=check, text=True, capture_output=True)


def test_resign_script_repairs_stale_lane_signatures(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[1]
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "canonical/signing").mkdir(parents=True)
    (repo / "data/daily/2026-07-15").mkdir(parents=True)
    (repo / "data/daily/current").mkdir(parents=True)
    shutil.copy2(source_root / "scripts/sign_language_lanes.py", repo / "scripts/sign_language_lanes.py")

    private_key = tmp_path / "private.pem"
    public_key = repo / "canonical/signing/data_signing_public_key.pub"
    run("openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key), cwd=repo)
    run("openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key), cwd=repo)

    dated = repo / "data/daily/2026-07-15/el.json"
    current = repo / "data/daily/current/el.json"
    original = b'{"date_iso":"2026-07-15","language":"el"}\n'
    changed = b'{"date_iso":"2026-07-15","language":"el","changed":true}\n'
    dated.write_bytes(original)
    current.write_bytes(original)

    for payload in (dated, current):
        raw = tmp_path / f"{payload.parent.name}.sig.bin"
        run("openssl", "dgst", "-sha256", "-sign", str(private_key), "-out", str(raw), str(payload), cwd=repo)
        Path(str(payload) + ".sig").write_bytes(base64.b64encode(raw.read_bytes()) + b"\n")
        payload.write_bytes(changed)

    stale_raw = tmp_path / "stale.sig.bin"
    stale_raw.write_bytes(base64.b64decode(Path(str(dated) + ".sig").read_bytes().strip()))
    stale = run(
        "openssl", "dgst", "-sha256", "-verify", str(public_key), "-signature", str(stale_raw), str(dated),
        cwd=repo, check=False,
    )
    assert stale.returncode != 0

    repaired = run(
        sys.executable,
        "scripts/sign_language_lanes.py",
        "--date", "2026-07-15",
        "--language", "el",
        "--private-key", str(private_key),
        cwd=repo,
    )
    assert "LANGUAGE_LANES_RESIGNED el" in repaired.stdout

    for payload in (dated, current):
        raw = tmp_path / f"verified-{payload.parent.name}.sig.bin"
        raw.write_bytes(base64.b64decode(Path(str(payload) + ".sig").read_bytes().strip()))
        verified = run(
            "openssl", "dgst", "-sha256", "-verify", str(public_key), "-signature", str(raw), str(payload),
            cwd=repo, check=False,
        )
        assert verified.returncode == 0
