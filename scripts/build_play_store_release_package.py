#!/usr/bin/env python3
"""Assemble a deterministic Play Console upload package from validated release outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise SystemExit(f"required Play release file is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aab", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--support-email", required=True)
    parser.add_argument(
        "--privacy-url",
        default="https://maen1977.github.io/orthodox_prayers/privacy/",
    )
    args = parser.parse_args()
    if not EMAIL.fullmatch(args.support_email.strip()):
        raise SystemExit("PLAY_SUPPORT_EMAIL must be a valid public support address")
    if not args.privacy_url.startswith("https://"):
        raise SystemExit("privacy policy URL must use HTTPS")

    output = args.output_dir
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    copy_file(args.aab, output / args.aab.name)
    copy_file(ROOT / "play-store/assets/app-icon-512.png", output / "graphics/app-icon-512.png")
    copy_file(ROOT / "play-store/assets/feature-graphic-1024x500.png", output / "graphics/feature-graphic-1024x500.png")
    screenshots = ROOT / "play-store/assets/screenshots"
    if not screenshots.is_dir():
        raise SystemExit("automated screenshots are missing")
    shutil.copytree(screenshots, output / "screenshots")
    for language in ("AR", "EN", "EL"):
        copy_file(ROOT / f"play-store/STORE_LISTING_{language}.md", output / f"listing/STORE_LISTING_{language}.md")
    for relative in (
        "play-store/DATA_SAFETY_AR.md",
        "play-store/PLAY_CONSOLE_CHECKLIST_AR.md",
        "CONTENT_RIGHTS.md",
        "PRIVACY.md",
        "docs/privacy/index.html",
    ):
        copy_file(ROOT / relative, output / "compliance" / Path(relative).name)

    metadata = {
        "schema_version": 1,
        "application_id": "com.orthodoxprayers.privateapp",
        "support_email": args.support_email.strip(),
        "privacy_policy_url": args.privacy_url,
        "languages": ["ar", "en", "el"],
        "screenshots_generated_by_android_instrumentation": True,
        "human_religious_review_required": False,
    }
    (output / "PLAY_RELEASE_METADATA.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(output).as_posix()}")
    (output / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"PLAY_RELEASE_PACKAGE_OK files={len(lines)} output={output}")


if __name__ == "__main__":
    main()
