#!/usr/bin/env python3
"""Check the supported Android range and the single-build contract."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
gradle = (ROOT / "app" / "build.gradle.kts").read_text(encoding="utf-8")
workflow = (ROOT / ".github" / "workflows" / "church-prayers.yml").read_text(encoding="utf-8")

expected = {
    "compileSdk": "36",
    "minSdk": "26",
    "targetSdk": "36",
    "versionCode": "50607",
    "versionName": '"5.6.7"',
}
for key, value in expected.items():
    pattern = rf"\b{re.escape(key)}\s*=\s*{re.escape(value)}"
    if not re.search(pattern, gradle):
        raise SystemExit(f"Android contract mismatch: {key} must be {value}")

if workflow.count("\n  build:\n") != 1:
    raise SystemExit("GitHub must expose exactly one build job")
if "Church-Prayers.apk" not in workflow or "Church-Prayers.aab" not in workflow:
    raise SystemExit("GitHub must produce exactly the APK and AAB names")

print("ANDROID_CONTRACT_OK min=26 target=36 compile=36 version=5.6.7 jobs=1")
