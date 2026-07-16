#!/usr/bin/env python3
"""Verify that the committed Gradle wrapper exactly matches Gradle 8.9."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "gradle/wrapper/gradle-wrapper.jar"
POSIX_SCRIPT = ROOT / "gradlew"
WINDOWS_SCRIPT = ROOT / "gradlew.bat"
PROPERTIES = ROOT / "gradle/wrapper/gradle-wrapper.properties"
EXPECTED_WRAPPER_SHA256 = "498495120a03b9a6ab5d155f5de3c8f0d986a449153702fb80fc80e134484f17"
EXPECTED_POSIX_SCRIPT_SHA256 = "9cbbb4d68ff7fb5211c4d58f598ac9d8664c05fdcd1e5f59b7f2c3ac1ee00af0"
EXPECTED_WINDOWS_SCRIPT_SHA256 = "0f3ed8f03b50934cb8c48b15a470d5c20a30a5385825e48b55bcc8ea3d8f8e18"
EXPECTED_DISTRIBUTION_SHA256 = "d725d707bfabd4dfdc958c624003b3c80accc03f7037b5122c4b1d0ef15cecab"
EXPECTED_DISTRIBUTION = "https\\://services.gradle.org/distributions/gradle-8.9-bin.zip"


def canonical_text_bytes(path: Path) -> bytes:
    """Return deterministic LF bytes regardless of Git checkout line endings."""
    data = path.read_bytes()
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def main() -> None:
    if not WRAPPER.is_file():
        raise SystemExit("Missing gradle/wrapper/gradle-wrapper.jar")
    if not PROPERTIES.is_file():
        raise SystemExit("Missing gradle/wrapper/gradle-wrapper.properties")

    actual = hashlib.sha256(WRAPPER.read_bytes()).hexdigest()
    if actual != EXPECTED_WRAPPER_SHA256:
        raise SystemExit(
            "Gradle wrapper JAR checksum mismatch: "
            f"expected {EXPECTED_WRAPPER_SHA256}, got {actual}"
        )

    for path, expected in (
        (POSIX_SCRIPT, EXPECTED_POSIX_SCRIPT_SHA256),
        (WINDOWS_SCRIPT, EXPECTED_WINDOWS_SCRIPT_SHA256),
    ):
        if not path.is_file():
            raise SystemExit(f"Missing {path.relative_to(ROOT)}")
        actual_script = hashlib.sha256(canonical_text_bytes(path)).hexdigest()
        if actual_script != expected:
            raise SystemExit(
                f"Gradle wrapper script checksum mismatch for {path.name}: "
                f"expected {expected}, got {actual_script}"
            )

    properties = PROPERTIES.read_text(encoding="utf-8")
    required = {
        f"distributionUrl={EXPECTED_DISTRIBUTION}",
        f"distributionSha256Sum={EXPECTED_DISTRIBUTION_SHA256}",
        "validateDistributionUrl=true",
    }
    missing = sorted(item for item in required if item not in properties)
    if missing:
        raise SystemExit("Gradle wrapper properties mismatch:\n- " + "\n- ".join(missing))

    print(
        "Gradle wrapper verified: Gradle 8.9 JAR, POSIX/Windows scripts, and "
        "binary distribution checksums match the pinned contract"
    )


if __name__ == "__main__":
    main()
