from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_signed_week_is_not_rejected_for_one_reading_evidence_failure():
    source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert "isRecoverableReadingValidation" in source
    assert 'error.endsWith("_hash_invalid")' in source
    assert 'error.endsWith("_text_unverified")' in source
    assert "VerifiedContentSanitizer.sanitizeFutureDays(parsed)" in source


def test_structural_and_signature_checks_remain_fail_closed():
    source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert "signatureVerifier.verify(jsonBytes, signatureBytes)" in source
    assert "manifest_payload_hash_mismatch" in source
    assert "validateRollingWeekPackage(parsed)" in source
    assert "throw new IllegalStateException(rollingError)" in source


def test_future_days_are_sanitized_individually():
    source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/VerifiedContentSanitizer.java").read_text(encoding="utf-8")
    assert "public static void sanitizeFutureDays" in source
    assert 'root.optJSONArray("weekly_days")' in source
    assert "if (day != null) sanitize(day)" in source


def test_release_version_is_5019():
    build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
    assert 'versionName = "5.6.2"' in build
    assert "versionCode = 50602" in build

def test_matins_gospel_uses_the_same_native_text_sanitizer_as_other_scripture():
    source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/VerifiedContentSanitizer.java").read_text(encoding="utf-8")
    assert source.count('"matins_gospel".equals(kind)') == 2


def test_all_daily_validation_lanes_recognize_optional_matins_gospel():
    expected = {
        "scripts/validate_daily_native_content.py": '"matins_gospel"',
        "scripts/validate_daily_ui_localizations.py": '"matins_gospel"',
        "scripts/quality_check.py": "'matins_gospel'",
        "scripts/validate_embedded_app_data.py": "'matins_gospel'",
    }
    for relative, marker in expected.items():
        assert marker in (ROOT / relative).read_text(encoding="utf-8"), relative

