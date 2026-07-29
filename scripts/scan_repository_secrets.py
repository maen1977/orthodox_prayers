#!/usr/bin/env python3
"""Fail when private signing material or likely literal secrets exist in the repository.

Public keys and detached signatures are allowed. GitHub Actions expressions such as
`${{ secrets.NAME }}` are references, not secret values, and are intentionally allowed.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".git", ".gradle", ".idea", "build", "release", "reports", "__pycache__", ".pytest_cache", ".cache"}
FORBIDDEN_SUFFIXES = {".jks", ".keystore", ".p12", ".pfx", ".key", ".pem"}
FORBIDDEN_NAMES = {
    "keystore.properties",
    "github_secrets.txt",
    "secrets.txt",
    ".env",
    ".env.local",
}
PRIVATE_MARKERS = (
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"-----BEGIN EC PRIVATE KEY-----",
    b"-----BEGIN ENCRYPTED PRIVATE KEY-----",
    b"-----BEGIN OPENSSH PRIVATE KEY-----",
)
# These patterns intentionally require a quoted literal and ignore workflow secret references.
LITERAL_SECRET_PATTERNS = (
    re.compile(r"(?i)(?:password|passwd|token|secret)\s*[:=]\s*['\"](?!\$\{\{\s*secrets\.)[^'\"\r\n]{8,}['\"]"),
    re.compile(r"(?i)gh[pousr]_[A-Za-z0-9_]{30,}"),
)


def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        yield path, relative


def main() -> None:
    errors: list[str] = []
    for path, relative in iter_files():
        lower_name = path.name.lower()
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden private-key/keystore suffix: {relative}")
            continue
        if lower_name in FORBIDDEN_NAMES or "private_key" in lower_name:
            errors.append(f"suspicious secret filename: {relative}")
            continue
        data = path.read_bytes()
        if relative == Path("scripts/scan_repository_secrets.py"):
            continue
        if any(marker in data for marker in PRIVATE_MARKERS):
            errors.append(f"private key marker found: {relative}")
            continue
        # Scan text-like files only; avoid false positives in images/JARs.
        if b"\x00" in data[:4096]:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        sanitized = re.sub(r"\$\{\{\s*secrets\.[A-Za-z0-9_]+\s*\}\}", "<GITHUB_SECRET_REFERENCE>", text)
        for pattern in LITERAL_SECRET_PATTERNS:
            if pattern.search(sanitized):
                errors.append(f"possible literal credential: {relative}")
                break
    if errors:
        raise SystemExit("Repository secret scan failed:\n- " + "\n- ".join(sorted(set(errors))))
    print("Repository secret scan passed: no private keys, keystores, or likely literal credentials")


if __name__ == "__main__":
    main()
