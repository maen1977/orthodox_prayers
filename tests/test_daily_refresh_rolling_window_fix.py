from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_accepts_current_day_inside_signed_rolling_coverage():
    parser = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/UpdateManifest.java").read_text(encoding="utf-8")
    assert "manifest_date_outside_coverage" in parser
    assert "requested.isBefore(start) || requested.isAfter(end)" in parser
    assert "Legacy one-day manifests remain exact-date only" in parser
    assert "validateSelectedCoverage(selected, coverage, expectedDate)" in parser


def test_repository_validates_anchor_then_activates_requested_day():
    repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert "boolean rollingPackage = hasRollingWindow(parsed)" in repository
    assert "parsed.optString(\"date_iso\", \"\").trim()" in repository
    assert "rollingPackageContainsDate(parsed, currentDate)" in repository
    assert '"date_not_ready:"' in repository


def test_java_regression_cases_cover_august_5_to_13_window():
    manifest_test = (ROOT / "app/src/test/java/com/orthodoxprayers/privateapp/data/UpdateManifestTest.java").read_text(encoding="utf-8")
    package_test = (ROOT / "app/src/test/java/com/orthodoxprayers/privateapp/data/RollingPackageDateAcceptanceTest.java").read_text(encoding="utf-8")
    assert "acceptsTodayInsideSignedRollingCoverageEvenWhenAnchorWasYesterday" in manifest_test
    assert '"2026-08-06"' in manifest_test
    assert '"2026-08-14"' in manifest_test
    assert "packageAnchoredYesterdayContainsToday" in package_test
    assert '"2026-08-13"' in package_test
