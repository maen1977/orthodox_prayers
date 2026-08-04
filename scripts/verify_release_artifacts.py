#!/usr/bin/env python3
"""Verify release APK/AAB structure, metadata, secrets, signing, and hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DEX_APK = re.compile(r"(?:^|/)classes(?:\d+)?\.dex$")
DEX_AAB = re.compile(r"^base/dex/classes(?:\d+)?\.dex$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_checked(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"Command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result.stdout.strip()


def verify_zip(path: Path, kind: str, policy: dict) -> dict:
    if not path.is_file():
        raise ValueError(f"Missing {kind}: {path}")
    if not zipfile.is_zipfile(path):
        raise ValueError(f"{kind} is not a ZIP-compatible Android artifact: {path}")

    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"{kind} contains duplicate entries: {duplicates[:10]}")

        total_compressed = 0
        total_uncompressed = 0
        forbidden: list[str] = []
        unsafe: list[str] = []
        encrypted: list[str] = []
        symlinks: list[str] = []
        suffixes = tuple(str(value).lower() for value in policy["forbidden_suffixes"])
        forbidden_names = {str(value).lower() for value in policy["forbidden_names"]}

        for info in infos:
            name = info.filename
            posix = PurePosixPath(name)
            total_compressed += info.compress_size
            total_uncompressed += info.file_size
            if name.startswith("/") or ".." in posix.parts or "\\" in name:
                unsafe.append(name)
            leaf = posix.name.lower()
            lower = name.lower()
            if leaf in forbidden_names or lower.endswith(suffixes) or "/.git/" in f"/{lower}/":
                forbidden.append(name)
            if info.flag_bits & 0x1:
                encrypted.append(name)
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                symlinks.append(name)

        if unsafe:
            raise ValueError(f"{kind} contains unsafe paths: {unsafe[:10]}")
        if forbidden:
            raise ValueError(f"{kind} contains forbidden secret-like files: {forbidden[:10]}")
        if encrypted:
            raise ValueError(f"{kind} contains encrypted entries: {encrypted[:10]}")
        if symlinks:
            raise ValueError(f"{kind} contains symbolic links: {symlinks[:10]}")

        for required in policy[f"{kind}_required_entries"]:
            if required not in names:
                raise ValueError(f"{kind} missing required entry: {required}")
        dex_pattern = DEX_APK if kind == "apk" else DEX_AAB
        if not any(dex_pattern.search(name) for name in names):
            raise ValueError(f"{kind} contains no application DEX entry")

        maximum = int(policy["max_total_uncompressed_bytes"])
        if total_uncompressed > maximum:
            raise ValueError(f"{kind} uncompressed size {total_uncompressed} exceeds {maximum}")
        ratio = total_uncompressed / max(total_compressed, 1)
        max_ratio = float(policy["max_compression_ratio"])
        if ratio > max_ratio:
            raise ValueError(f"{kind} compression ratio {ratio:.2f} exceeds {max_ratio:.2f}")

    return {
        "path": str(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "entry_count": len(names),
        "compressed_bytes": total_compressed,
        "uncompressed_bytes": total_uncompressed,
        "compression_ratio": round(ratio, 3),
    }


def verify_apk_metadata(apk: Path, apkanalyzer: Path | None, policy: dict) -> dict:
    if apkanalyzer is None:
        return {"status": "DEFERRED", "reason": "apkanalyzer not supplied"}
    if not apkanalyzer.is_file() or not os.access(apkanalyzer, os.X_OK):
        raise ValueError(f"apkanalyzer is not executable: {apkanalyzer}")
    application_id = run_checked([str(apkanalyzer), "manifest", "application-id", str(apk)])
    version_name = run_checked([str(apkanalyzer), "manifest", "version-name", str(apk)])
    version_code = run_checked([str(apkanalyzer), "manifest", "version-code", str(apk)])
    expected = {
        "application_id": str(policy["application_id"]),
        "version_name": str(policy["version_name"]),
        "version_code": str(policy["version_code"]),
    }
    actual = {
        "application_id": application_id,
        "version_name": version_name,
        "version_code": version_code,
    }
    if actual != expected:
        raise ValueError(f"APK metadata mismatch: expected={expected} actual={actual}")
    return {"status": "PASS", **actual}


def verify_apk_signature(apk: Path, apksigner: Path | None) -> dict:
    if apksigner is None:
        return {"status": "DEFERRED", "reason": "apksigner not supplied"}
    if not apksigner.is_file() or not os.access(apksigner, os.X_OK):
        raise ValueError(f"apksigner is not executable: {apksigner}")
    output = run_checked([str(apksigner), "verify", "--verbose", "--print-certs", str(apk)])
    digest = None
    for line in output.splitlines():
        if "certificate SHA-256 digest:" in line:
            digest = line.split(":", 1)[1].strip()
            break
    return {"status": "PASS", "certificate_sha256": digest, "details": output.splitlines()[:12]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--aab", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=ROOT / "config/release-artifact-policy.json")
    parser.add_argument("--apkanalyzer", type=Path)
    parser.add_argument("--apksigner", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    report = {
        "schema_version": 1,
        "status": "PASS",
        "policy": str(args.policy),
        "application": {
            "application_id": policy["application_id"],
            "version_name": policy["version_name"],
            "version_code": policy["version_code"],
            "min_sdk": policy["min_sdk"],
            "target_sdk": policy["target_sdk"],
        },
    }
    try:
        report["apk"] = verify_zip(args.apk, "apk", policy)
        report["aab"] = verify_zip(args.aab, "aab", policy)
        report["apk_metadata"] = verify_apk_metadata(args.apk, args.apkanalyzer, policy)
        report["apk_signature"] = verify_apk_signature(args.apk, args.apksigner)
    except Exception as exc:
        report["status"] = "FAIL"
        report["error"] = str(exc)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(str(exc))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "RELEASE_ARTIFACTS_OK "
        f"apk_sha256={report['apk']['sha256']} aab_sha256={report['aab']['sha256']}"
    )


if __name__ == "__main__":
    main()
