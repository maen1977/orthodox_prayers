#!/usr/bin/env python3
"""Create the deterministic R19.1 overlay ZIP with repository-root paths."""
from __future__ import annotations

import argparse
import hashlib
import os
import stat
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = (2026, 7, 23, 0, 0, 0)
PATCH_FILES = (
    "CHANGELOG.md",
    "README_AR.md",
    "RELEASE_READINESS_AR.md",
    "SETUP_AR.md",
    "OrthodoxPrayers-5.0.15-r19-sbom.cdx.json",
    "app/build.gradle.kts",
    "app/src/main/assets/data/source_registry.json",
    "app/src/main/java/com/orthodoxprayers/privateapp/AppPreferences.java",
    "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java",
    "app/src/main/java/com/orthodoxprayers/privateapp/data/TranslationCoverage.java",
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/LocalePolicy.java",
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/LanguagePacksScreen.java",
    "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java",
    "app/src/test/java/com/orthodoxprayers/privateapp/data/TranslationCoverageTest.java",
    "app/src/test/java/com/orthodoxprayers/privateapp/ui/LocalePolicyTest.java",
    "canonical/source_native_contract.json",
    "canonical/static_hashes.json",
    "data/sources/source_registry.json",
    "docs/ARCHITECTURE_AR.md",
    "docs/REFINEMENT_REPORT_AR.md",
    "play-store/assets/app-icon-512.png",
    "scripts/build_public_source_registry.py",
    "scripts/create_r19_root_patch.py",
    "scripts/fill_daily_from_native_corpora.py",
    "scripts/generate_sbom.py",
    "scripts/orthodox_integrity.py",
    "scripts/public_domain_scripture.py",
    "scripts/run_quality_gate.py",
    "scripts/source_connectors.py",
    "scripts/verify_r18_patch.py",
    "scripts/verify_r19_patch.py",
    "tests/test_r19_1_patch_application.py",
    "tests/test_r19_refinement.py",
    "tests/test_native_language_contract.py",
    "tests/test_r18_4_dcs_mt_abbreviation_hotfix.py",
    "tests/test_release_contract.py",
)


def write_patch(output: Path) -> str:
    missing = [relative for relative in PATCH_FILES if not (ROOT / relative).is_file()]
    if missing:
        raise SystemExit("R19_PATCH_INPUT_MISSING\n" + "\n".join(missing))

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in sorted(PATCH_FILES):
            source = ROOT / relative
            info = zipfile.ZipInfo(relative, date_time=FIXED_TIME)
            executable = source.name.endswith(".py") and os.access(source, os.X_OK)
            mode = 0o755 if executable else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n",
        encoding="utf-8",
    )
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    digest = write_patch(output)
    print(
        f"R19_ROOT_PATCH_OK files={len(PATCH_FILES)} "
        f"sha256={digest} output={output}"
    )


if __name__ == "__main__":
    main()
