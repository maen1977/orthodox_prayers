from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.today_path = ROOT / "data/calendar/today.json"
        cls.asset_path = ROOT / "app/src/main/assets/data/today.json"
        cls.today = json.loads(cls.today_path.read_text(encoding="utf-8"))

    def test_version_and_release_hardening(self):
        build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        self.assertIn('versionName = "5.0.14"', build)
        self.assertIn("versionCode = 50014", build)
        contract = json.loads((ROOT / "canonical/update_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(50013, contract["minimum_app_version_code"])
        self.assertIn("compileSdk = 36", build)
        self.assertIn("targetSdk = 36", build)
        self.assertIn("isMinifyEnabled = true", build)
        self.assertIn("isShrinkResources = true", build)
        self.assertIn('System.getenv("ANDROID_KEYSTORE_FILE")', build)
        self.assertIn('signingConfigs.findByName("release")', build)

    def test_next_sunday_schedule_sync_runs_after_native_fill(self):
        rebuild = (ROOT / "scripts/rebuild_daily_services.py").read_text(encoding="utf-8")
        update = (ROOT / "scripts/update.py").read_text(encoding="utf-8")
        self.assertIn("synchronize_next_sunday_schedule(data, next_readings)", rebuild)
        integrity = (ROOT / "scripts/orthodox_integrity.py").read_text(encoding="utf-8")
        self.assertIn("require_complete=False", integrity)
        self.assertNotIn("require_complete=False", rebuild)
        schedule = (ROOT / "scripts/update_liturgical_data.py").read_text(encoding="utf-8")
        self.assertIn("require_complete: bool | None = None", schedule)
        self.assertIn("require_complete = source is None", schedule)
        self.assertIn('PIPELINE_PATCH_LEVEL = "R18.4"', update)
        self.assertIn("verify_pipeline_patch()", update)
        self.assertLess(
            update.index('run("scripts/fill_daily_from_native_corpora.py"'),
            update.index('run("scripts/rebuild_daily_services.py"'),
        )


    def test_native_corpus_preparation_preserves_localized_prokeimenon(self):
        scripts = ROOT / "scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        import orthodox_integrity as integrity
        import update_liturgical_data as update_liturgical

        info = update_liturgical.day_info(update_liturgical.date(2026, 7, 20))
        prokeimenon = update_liturgical.default_prokeimenon(info, update_liturgical.date(2026, 7, 20))
        original = json.loads(json.dumps(prokeimenon, ensure_ascii=False))
        readings = [
            prokeimenon,
            {"kind": "epistle", "reference": {"ar": "قديم", "en": "old", "el": "παλαιό"}},
            {"kind": "gospel", "reference": {"ar": "قديم", "en": "old", "el": "παλαιό"}},
        ]
        prepared = integrity.prepare_native_corpus_readings(
            readings, "1 Corinthians 9:13-18", "Matthew 16:1-6", "official_greek_orthodox"
        )
        self.assertEqual(original, prepared[0])
        for language in ("ar", "en", "el"):
            self.assertTrue(prepared[0]["reference"][language].strip())
            self.assertTrue(prepared[0]["body"][language].strip())
        self.assertEqual("1CO.9.13-18", prepared[1]["integrity"]["canonical_reference"])
        self.assertEqual("MAT.16.1-6", prepared[2]["integrity"]["canonical_reference"])

    def test_daily_schema_and_provenance(self):
        schema = json.loads((ROOT / "schemas/daily_data.schema.json").read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(self.today))
        self.assertEqual([], errors)
        metadata = self.today["content_metadata"]
        self.assertEqual("old_calendar_julian", metadata["calendar_system"])
        self.assertEqual("jerusalem_patriarchate_usage", metadata["jurisdiction"])
        self.assertFalse(metadata["human_review_required"])
        self.assertEqual("automatic_native_language_policy_enforced", metadata["review_status"])
        self.assertEqual("CONTENT_RIGHTS.md", metadata["rights_notice"])

    def test_integrity_schema_accepts_compatible_overlapping_envelopes(self):
        schema = json.loads((ROOT / "schemas/daily_data.schema.json").read_text(encoding="utf-8"))
        integrity_schema = schema["properties"]["integrity"]
        validator = Draft202012Validator(integrity_schema)

        native_only = {
            "native_text_contract": "canonical/source_native_contract.json",
            "legacy_arabic_scripture_snapshot": "QUARANTINED_NOT_PUBLICATION_AUTHORITY",
        }
        verified_only = {
            "status": "VERIFIED_OFFICIAL_SOURCES",
            "ai_scripture_translation_used": False,
            "ai_liturgical_translation_used": False,
        }
        combined = {**native_only, **verified_only}

        self.assertEqual([], list(validator.iter_errors(native_only)))
        self.assertEqual([], list(validator.iter_errors(verified_only)))
        self.assertEqual([], list(validator.iter_errors(combined)))
        self.assertNotEqual([], list(validator.iter_errors({})))
        self.assertIn("anyOf", integrity_schema)
        self.assertNotIn("oneOf", integrity_schema)

    def test_canonical_asset_and_signatures_are_identical(self):
        self.assertEqual(self.today_path.read_bytes(), self.asset_path.read_bytes())
        canonical_sig = ROOT / "data/calendar/today.json.sig"
        asset_sig = ROOT / "app/src/main/assets/data/today.json.sig"
        self.assertTrue(canonical_sig.is_file())
        self.assertEqual(canonical_sig.read_bytes(), asset_sig.read_bytes())

    def test_application_rejects_unsigned_or_tampered_data(self):
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        verifier = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataSignatureVerifier.java").read_text(encoding="utf-8")
        crypto = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/CryptoVerifier.java").read_text(encoding="utf-8")
        self.assertIn("signatureVerifier.verify(jsonBytes, signatureBytes)", repository)
        self.assertIn("parseTrustedCandidate", repository)
        self.assertIn("SHA256withRSA", crypto)
        self.assertIn("signature_invalid", crypto)
        self.assertIn("R.raw.data_signing_public_key", verifier)
        self.assertIn("VerifiedContentSanitizer.sanitize(candidate)", repository)
        sanitizer = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/VerifiedContentSanitizer.java").read_text(encoding="utf-8")
        self.assertIn("VERIFIED_EXACT_NATIVE_SOURCE", sanitizer)
        self.assertIn("unverified_scripture_native_text", sanitizer)
        self.assertIn("new String[]{\"ar\", \"en\", \"el\"}", sanitizer)
        self.assertIn("text_sha256", sanitizer)

    def test_json_is_not_stored_in_shared_preferences(self):
        preferences = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/AppPreferences.java").read_text(encoding="utf-8")
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        self.assertNotIn("saveRemoteCache", preferences)
        self.assertNotIn("saveRemoteCache", repository)
        self.assertIn('remove("cache_today_json")', preferences)
        self.assertIn("DailyDataStore", repository)

    def test_atomic_generation_store_retains_last_known_good(self):
        store = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DailyDataStore.java").read_text(encoding="utf-8")
        self.assertIn("generation-", store)
        self.assertIn("current.ref", store)
        self.assertIn("backup.ref", store)
        self.assertIn("ATOMIC_MOVE", store)
        self.assertIn("getFD().sync()", store)
        self.assertIn("cleanupUnreferencedGenerations", store)
        self.assertIn("archive", store)
        self.assertIn("RETAINED_DAYS_PER_LANGUAGE", store)
        self.assertIn("normalizeLanguage", store)
        self.assertIn("afterBackupCommitted", store)
        self.assertLess(store.index("writeReferenceAtomically(backupReference"), store.index("writeReferenceAtomically(currentReference"))
        self.assertTrue((ROOT / "app/src/test/java/com/orthodoxprayers/privateapp/data/DailyDataStoreTest.java").is_file())

    def test_single_application_repository_and_unique_work(self):
        manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        app = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/OrthodoxPrayersApp.java").read_text(encoding="utf-8")
        main = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java").read_text(encoding="utf-8")
        coordinator = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/update/UpdateCoordinator.java").read_text(encoding="utf-8")
        self.assertIn('android:name=".OrthodoxPrayersApp"', manifest)
        self.assertEqual(1, app.count("new DataRepository("))
        self.assertIn("app.repository()", main)
        self.assertNotIn("new DataRepository(", main)
        self.assertIn("enqueueUniqueWork", coordinator)
        self.assertIn("DAILY_SCHEDULE_WORK", coordinator)
        self.assertIn("MIDNIGHT_EXECUTION_WORK", coordinator)
        self.assertIn("ExistingWorkPolicy.REPLACE", coordinator)
        self.assertIn("ExistingWorkPolicy.KEEP", coordinator)
        self.assertNotIn("enqueueUniquePeriodicWork", coordinator)

    def test_predictive_back_uses_androidx_dispatcher(self):
        source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java").read_text(encoding="utf-8")
        build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        self.assertIn("extends ComponentActivity", source)
        self.assertIn("import android.app.Activity;", source)
        self.assertIn("getOnBackPressedDispatcher().addCallback", source)
        self.assertIn("new OnBackPressedCallback(true)", source)
        self.assertIn("handleOnBackPressed", source)
        self.assertNotIn("public void onBackPressed()", source)
        self.assertNotIn("getOnBackInvokedDispatcher()", source)
        self.assertIn('androidx.activity:activity:1.10.1', build)

    def test_fixed_bottom_navigation_and_system_insets_remain(self):
        source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java").read_text(encoding="utf-8")
        self.assertIn("shell.addView(contentHost, new LinearLayout.LayoutParams(-1, 0, 1f))", source)
        self.assertIn("shell.addView(bottomNav", source)
        self.assertIn("setDecorFitsSystemWindows(false)", source)
        self.assertIn("getSystemWindowInsetBottom()", source)
        for label in ("الرئيسية", "الصلوات", "القداس", "الإعدادات"):
            self.assertIn(label, source)

    def test_reader_is_virtualized(self):
        source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java").read_text(encoding="utf-8")
        self.assertIn("RecyclerView", source)
        self.assertIn("ReaderAdapter", source)


    def test_reader_uses_stable_sibling_layout_and_preserves_exact_position(self):
        reader = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java").read_text(encoding="utf-8")
        preferences = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/AppPreferences.java").read_text(encoding="utf-8")
        policy = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/ReaderControlsPolicy.java").read_text(encoding="utf-8")
        policy_test = (ROOT / "app/src/test/java/com/orthodoxprayers/privateapp/ui/ReaderControlsPolicyTest.java").read_text(encoding="utf-8")

        self.assertIn("LinearLayout root = new LinearLayout", reader)
        self.assertIn("root.addView(controlsPanel", reader)
        self.assertIn("root.addView(recycler, new LinearLayout.LayoutParams(-1, 0, 1f))", reader)
        self.assertNotIn("FrameLayout", reader)
        self.assertNotIn("setTranslationY", reader)
        self.assertNotIn("controlsHeightPx", reader)
        self.assertNotIn("recycler.setPadding(0, controls", reader)
        self.assertIn("controlsPanel.setVisibility(controlsExpanded ? View.VISIBLE : View.GONE)", reader)
        self.assertIn("segments == null || segments.length() == 0", reader)
        self.assertIn("تم منع فتح صفحة بيضاء", reader)
        self.assertIn("readerOffset(serviceId)", reader)
        self.assertIn("setReaderPosition(serviceId, position, offset)", reader)
        self.assertIn("migrateReaderLayoutState(READER_LAYOUT_VERSION)", reader)
        self.assertIn("reader_offset_", preferences)
        self.assertIn("reader_layout_version", preferences)
        self.assertIn("AUTO_COLLAPSE_DISTANCE_DP", reader)
        self.assertIn("AUTO_EXPAND_DISTANCE_DP", reader)
        self.assertIn("enum Action", policy)
        self.assertIn("collapsesOnlyAfterEnoughUserScroll", policy_test)
        self.assertIn("expandsOnlyAfterDeliberateReverseScroll", policy_test)

    def test_reader_ui_smoke_test_covers_blank_viewport_and_controls_toggle(self):
        smoke = (ROOT / "app/src/androidTest/java/com/orthodoxprayers/privateapp/ReaderSmokeTest.java").read_text(encoding="utf-8")
        build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        self.assertIn("Reader has no visible child rows", smoke)
        self.assertIn("Reader reserves too much blank top padding", smoke)
        self.assertIn('assertReader(scenario, "divine_liturgy", 200)', smoke)
        self.assertIn('assertReader(scenario, "next_sunday_full_liturgy", 200)', smoke)
        self.assertIn("Collapsing controls should not reduce the reading area", smoke)
        self.assertIn('testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"', build)
        self.assertIn("androidTestImplementation", build)

    def test_all_three_languages_are_enabled_without_arabic_masquerading_as_translation(self):
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        adapter = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/ReaderAdapter.java").read_text(encoding="utf-8")
        self.assertIn('addLanguageButton(languages, "العربية", "ar")', settings)
        self.assertIn('addLanguageButton(languages, "English", "en")', settings)
        self.assertIn('addLanguageButton(languages, "Ελληνικά", "el")', settings)
        self.assertNotIn("isReviewedEnough()", settings)
        self.assertNotIn("اللغات غير المكتملة معطلة", settings)
        self.assertIn("unavailableTranslationText", repository)
        self.assertIn("TranslationCoverage.isValidTargetText", repository)
        self.assertIn("Official native text unavailable", adapter)
        self.assertIn("It must never fall back to Arabic, English, or Greek from another lane", adapter)
        detail = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReadingDetailScreen.java").read_text(encoding="utf-8")
        self.assertNotIn('optString("ar", "").trim()', detail)
        self.assertTrue((ROOT / "app/src/main/res/values-en/strings.xml").is_file())
        self.assertTrue((ROOT / "app/src/main/res/values-el/strings.xml").is_file())

    def test_native_language_libraries_are_separate_official_source_packs(self):
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        self.assertIn('data/native/library_ar.json', repository)
        self.assertIn('data/native/library_el.json', repository)
        self.assertIn('data/native/library_en.json', repository)
        registry = json.loads((ROOT / "canonical/native_language_sources.json").read_text(encoding="utf-8"))
        self.assertEqual("CONFIRMED_BY_PROJECT_OWNER", registry["permission_basis"]["status"])
        for lang in ("ar", "el", "en"):
            pack_path = ROOT / "data/services/native" / f"library_{lang}.json"
            asset_path = ROOT / "app/src/main/assets/data/native" / f"library_{lang}.json"
            pack = json.loads(pack_path.read_text(encoding="utf-8"))
            self.assertEqual(pack_path.read_bytes(), asset_path.read_bytes())
            self.assertEqual(lang, pack["language"])
            self.assertFalse(pack["machine_translation_used"])
            self.assertEqual("OFFICIAL_NATIVE_SOURCE_TEXT_ONLY", pack["content_mode"])
        self.assertEqual("THREE_STRICTLY_INDEPENDENT_OFFICIAL_NATIVE_LANGUAGE_LANES", self.today["language_content_mode"])
        self.assertFalse(self.today["machine_translation_used"])
        self.assertEqual("DISABLED_NO_CROSS_LANGUAGE_FALLBACK", self.today["translation_fallback_policy"])

    def test_settings_show_free_app_provider_and_phone(self):
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        self.assertIn("هذا البرنامج مجاني، ومقدم من معن حنونة للستلايت.", settings)
        self.assertIn("00962788272988", settings)
        self.assertIn('local("عن البرنامج", "About the app", "Περὶ τῆς ἐφαρμογῆς")', settings)
        self.assertIn("freeNotice.setTextIsSelectable(true)", settings)
        self.assertNotIn("الاتصال بالرقم", settings)
        self.assertNotIn("Call phone number", settings)
        self.assertNotIn("سياسة الخصوصية", settings)
        self.assertNotIn("Privacy policy", settings)
        self.assertNotIn("maen1977.github.io/orthodox_prayers/privacy", settings)
        self.assertIn("كل لغة تُقرأ من مكتبتها الكنسية الأصلية المستقلة", settings)

        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        self.assertIn('new String[]{"ar", "en", "el"}', repository)
        self.assertIn("searchIndex()", repository)
        self.assertTrue((ROOT / "docs/privacy/index.html").is_file())
        self.assertTrue((ROOT / "play-store/STORE_LISTING_EN.md").is_file())
        self.assertTrue((ROOT / "play-store/STORE_LISTING_EL.md").is_file())

    def test_required_reader_services_are_nonempty_and_large_texts_are_not_blank(self):
        required = {
            "divine_liturgy",
            "vespers",
            "orthros",
            "morning_prayer",
            "evening_prayer",
            "small_compline",
            "next_sunday_full_liturgy",
        }
        for path in (ROOT / "data/calendar/today.json", ROOT / "app/src/main/assets/data/today.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            services = {item["id"]: item for item in payload["services"]}
            self.assertTrue(required.issubset(services), path)
            for service_id in required:
                service = services[service_id]
                self.assertTrue(service.get("title", {}).get("ar", "").strip(), service_id)
                self.assertGreater(len(service.get("segments", [])), 0, service_id)
                for segment in service["segments"]:
                    key = "title" if segment.get("type") == "section" else "text"
                    self.assertTrue(any(str(value).strip() for value in segment.get(key, {}).values()), (service_id, segment))

        today = json.loads((ROOT / "data/calendar/today.json").read_text(encoding="utf-8"))
        services = {item["id"]: item for item in today["services"]}
        self.assertEqual("divine_liturgy", services["divine_liturgy"]["extends_service_id"])
        self.assertEqual("divine_liturgy", services["next_sunday_full_liturgy"]["extends_service_id"])
        self.assertLess(len(services["divine_liturgy"]["segments"]), 20)
        self.assertLess(len(services["next_sunday_full_liturgy"]["segments"]), 20)
        self.assertTrue(services["divine_liturgy"]["segment_replacements"])
        self.assertTrue(services["next_sunday_full_liturgy"]["segment_replacements"])

    def test_repository_accepts_valid_partial_daily_payload_without_cross_language_fallback(self):
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        self.assertIn("readings_missing", repository)
        self.assertIn("scripture_reference_missing", repository)
        self.assertIn("text_unverified", repository)
        self.assertIn("validateServices(services)", repository)
        self.assertIn('new String[]{"ar", "en", "el"}', repository)

    def test_three_independent_signed_language_lanes(self):
        workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        endpoint_policy = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DailyDataEndpointPolicy.java").read_text(encoding="utf-8")
        preferences = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/AppPreferences.java").read_text(encoding="utf-8")
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        for marker in ("lane_ar", "lane_el", "lane_en", "Update Arabic lane", "Update Greek lane", "Update English lane"):
            self.assertIn(marker, workflow)
        self.assertIn("rm -rf", workflow)
        self.assertIn("data/daily/current", workflow)
        for script in ("update_language_lane.py", "verify_language_lanes.py"):
            self.assertTrue((ROOT / "scripts" / script).is_file())
        self.assertIn('"/data/daily/" + date + "/" + lane + ".json"', endpoint_policy)
        self.assertIn('"/data/daily/current/" + lane + ".json"', endpoint_policy)
        self.assertIn("preferences.effectiveLanguage()", repository)
        self.assertIn("language_lane_mismatch", repository)
        self.assertIn("language_lane_schema_unsupported", repository)
        self.assertIn("language_lane_services_missing", repository)
        self.assertIn("cachedEtag(jsonUrl)", repository)
        self.assertIn("cache_today_etag_endpoint", preferences)
        self.assertIn("reloadForSelectedLanguage", settings)

    def test_play_store_submission_files_and_privacy_are_present(self):
        manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        release = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        self.assertIn('applicationId = "com.orthodoxprayers.privateapp"', build)
        self.assertIn("targetSdk = 36", build)
        self.assertIn("bundleRelease", release)
        self.assertIn("app-release.aab", release)
        self.assertIn('android:usesCleartextTraffic="false"', manifest)
        self.assertTrue((ROOT / "PRIVACY.md").is_file())
        for filename in (
            "PLAY_CONSOLE_CHECKLIST_AR.md",
            "STORE_LISTING_AR.md",
            "DATA_SAFETY_AR.md",
        ):
            self.assertTrue((ROOT / "play-store" / filename).is_file(), filename)

    def test_daily_refresh_runs_at_amman_midnight_with_safe_fallback(self):
        manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        main = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java").read_text(encoding="utf-8")
        policy = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/update/RefreshPolicy.java").read_text(encoding="utf-8")
        coordinator = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/update/UpdateCoordinator.java").read_text(encoding="utf-8")
        receiver = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/update/MidnightUpdateReceiver.java").read_text(encoding="utf-8")
        restore = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/update/ScheduleRestoreReceiver.java").read_text(encoding="utf-8")
        worker = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/work/DailyUpdateWorker.java").read_text(encoding="utf-8")
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
        self.assertNotIn("registerNetworkCallback", main)
        self.assertNotIn("FOREGROUND_TICK_MS", main)
        self.assertIn("scheduleNextAmmanDayCheck", main)
        self.assertIn("scheduleDailyRefresh", main)
        self.assertIn("refreshVisibleScreenPreservingScroll", main)
        self.assertIn("rebindEntryToCurrentData", main)
        self.assertIn("if (current) return false", policy)
        self.assertIn("STALE_RETRY_INTERVAL_MS", policy)
        self.assertIn('ZoneId.of("Asia/Amman")', coordinator)
        self.assertIn("DAILY_REFRESH_MINUTE = 5", coordinator)
        self.assertIn("setInitialDelay", coordinator)
        self.assertIn("DAILY_SCHEDULE_WORK", coordinator)
        self.assertIn("setRequiredNetworkType(NetworkType.CONNECTED)", coordinator)
        self.assertIn("setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)", coordinator)
        self.assertIn("putBoolean(INPUT_FORCE, true)", coordinator)
        self.assertNotIn("AlarmManager", coordinator)
        self.assertNotIn("setExactAndAllowWhileIdle", coordinator)
        self.assertNotRegex(coordinator, r"12,\s+TimeUnit\.HOURS")
        self.assertIn("SAME_DAY_RECHECK_INTERVAL_MS", policy)
        self.assertIn("manifest_unavailable_after_acceptance", (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8"))
        self.assertIn("enqueueMidnightRefresh", receiver)
        self.assertIn("scheduleDailyRefresh", restore)
        self.assertIn("scheduleDailyRefresh", worker)
        self.assertNotIn("SCHEDULE_EXACT_ALARM", manifest)
        self.assertIn(".update.MidnightUpdateReceiver", manifest)
        self.assertIn("RECEIVE_BOOT_COMPLETED", manifest)
        self.assertIn("TIMEZONE_CHANGED", manifest)
        self.assertIn("00:05", settings)
        self.assertIn("30 minutes", settings)
        self.assertIn("ui.infoBadge", home)


    def test_v420_user_features_are_wired(self):
        manifest = (ROOT / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
        preferences = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/AppPreferences.java").read_text(encoding="utf-8")
        main = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java").read_text(encoding="utf-8")
        reader = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java").read_text(encoding="utf-8")
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        app = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/OrthodoxPrayersApp.java").read_text(encoding="utf-8")
        self.assertIn("POST_NOTIFICATIONS", manifest)
        self.assertIn("lineSpacingMultiplier", preferences)
        self.assertIn("recentServices", preferences)
        self.assertIn("favoriteFolder", preferences)
        self.assertIn("pendingReminderKind", preferences)
        self.assertIn("offlineLanguageEnabled", preferences)
        self.assertIn('case "calendar"', main)
        self.assertIn('case "history"', main)
        self.assertIn('case "language_packs"', main)
        self.assertIn("autoScrollTick", reader)
        self.assertIn("recordRecentService", reader)
        self.assertIn("addReminder", settings)
        self.assertIn("ReminderScheduler", app)
        self.assertIn("onRequestPermissionsResult", main)
        reminder_worker = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/work/PrayerReminderWorker.java").read_text(encoding="utf-8")
        calendar = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/CalendarScreen.java").read_text(encoding="utf-8")
        self.assertIn("translationUnavailable", reminder_worker)
        self.assertIn("julianLabel", calendar)
        self.assertTrue((ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/CalendarScreen.java").is_file())
        self.assertTrue((ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/work/PrayerReminderWorker.java").is_file())
        self.assertTrue((ROOT / "scripts/merge_authorized_native_services.py").is_file())
        self.assertTrue((ROOT / "scripts/export_missing_native_fields.py").is_file())
        self.assertTrue((ROOT / "docs/native_missing_en.json").is_file())
        self.assertTrue((ROOT / "docs/native_missing_el.json").is_file())

    def test_gradle_wrapper_contract(self):
        wrapper = ROOT / "gradle/wrapper/gradle-wrapper.jar"
        properties = (ROOT / "gradle/wrapper/gradle-wrapper.properties").read_text(encoding="utf-8")
        self.assertTrue((ROOT / "gradlew").exists())
        subprocess.run(
            [sys.executable, "scripts/ensure_gradlew_executable.py"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertTrue((ROOT / "gradlew").stat().st_mode & 0o111)
        self.assertTrue((ROOT / "gradlew.bat").exists())
        def canonical_text_bytes(path):
            return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")

        self.assertEqual(
            "9cbbb4d68ff7fb5211c4d58f598ac9d8664c05fdcd1e5f59b7f2c3ac1ee00af0",
            hashlib.sha256(canonical_text_bytes(ROOT / "gradlew")).hexdigest(),
        )
        self.assertEqual(
            "0f3ed8f03b50934cb8c48b15a470d5c20a30a5385825e48b55bcc8ea3d8f8e18",
            hashlib.sha256(canonical_text_bytes(ROOT / "gradlew.bat")).hexdigest(),
        )
        self.assertEqual(
            "498495120a03b9a6ab5d155f5de3c8f0d986a449153702fb80fc80e134484f17",
            hashlib.sha256(wrapper.read_bytes()).hexdigest(),
        )
        self.assertIn("gradle-8.13-bin.zip", properties)
        self.assertIn("distributionSha256Sum=20f1b1176237254a6fc204d8434196fa11a4cfb387567519c61556e8710aed78", properties)

    def test_workflows_cover_build_verified_data_security_and_signed_release(self):
        workflows = ROOT / ".github/workflows"
        expected = {"build.yml", "update.yml"}
        self.assertEqual(expected, {path.name for path in workflows.glob("*.yml")})

        build = (workflows / "build.yml").read_text(encoding="utf-8")
        self.assertIn("name: Android unit tests", build)
        self.assertIn("testDebugUnitTest --stacktrace", build)
        self.assertIn("name: Android debug lint", build)
        self.assertIn("lintDebug --stacktrace", build)
        self.assertIn("name: Build debug APK", build)
        self.assertIn("assembleDebug --stacktrace", build)
        self.assertIn("app/build/outputs/apk/debug/app-debug.apk", build)
        self.assertIn("SHA256SUMS.txt", build)
        self.assertIn("Import latest signed published data for debug APK", build)
        self.assertIn("origin/verified-data", build)
        self.assertIn('python scripts/verify.py --expected-date "$PUBLISHED_DATE" --allow-missing-manifest', build)
        self.assertGreaterEqual(
            build.count('python scripts/clean_legacy_calendar_snapshots.py --root "$VERIFIED_DIR"'),
            2,
        )
        self.assertIn("chmod +x ./gradlew", build)
        self.assertNotIn("connectedDebugAndroidTest", build)
        self.assertNotIn("android-emulator-runner@", build)
        self.assertNotIn("github/codeql-action/", build)
        self.assertNotIn("assembleDebugAndroidTest", build)

        update = (workflows / "update.yml").read_text(encoding="utf-8")
        self.assertIn("DATA_SIGNING_PRIVATE_KEY_B64", update)
        self.assertIn("environment: production-data-signing", update)
        self.assertIn("scripts/update.py", update)
        self.assertIn("--unsigned", update)
        self.assertIn("Generate and validate today without signing key", update)
        self.assertIn("Validate unsigned language lanes independently", update)
        self.assertIn("Prepare publication worktree before restoring key", update)
        self.assertIn("Remove private key before commit or network publication", update)
        self.assertNotRegex(update, r"scripts/update\.py[^\n]*--private-key")
        self.assertNotRegex(update, r"scripts/update_language_lane\.py[^\n]*--private-key")
        ordered = [
            update.index("Generate and validate today without signing key"),
            update.index("Validate unsigned language lanes independently"),
            update.index("Prepare publication worktree before restoring key"),
            update.index("Restore and match the one signing key"),
            update.index("Sign and verify generated data"),
            update.index("Remove private key before commit or network publication"),
            update.index("Commit, verify Git blobs, and publish verified-data"),
        ]
        self.assertEqual(sorted(ordered), ordered)
        updater = (ROOT / "scripts/update.py").read_text(encoding="utf-8")
        self.assertIn("scripts/rebuild_daily_services.py", updater)
        self.assertIn("--require-complete", updater)
        self.assertTrue((ROOT / "scripts/public_domain_scripture.py").is_file())
        self.assertTrue((ROOT / "scripts/rebuild_daily_services.py").is_file())
        self.assertIn("scripts/verify.py", update)
        self.assertIn("verified-data", update)
        self.assertIn('timezone: "Asia/Amman"', update)
        self.assertIn('cron: "0 0 * * *"', update)
        self.assertNotIn('cron: "15 0 * * *"', update)
        self.assertIn("canonical/signing/data_signing_public_key.pub", update)
        self.assertIn("cmp -s", update)
        self.assertIn("The GitHub secret does not match the public key", update)
        self.assertIn("Verify from origin after publishing", update)
        self.assertIn("scripts/build_update_manifest.py", update)
        self.assertIn("scripts/sign_update_manifest.py", update)
        self.assertIn("scripts/verify_update_manifest.py", update)
        self.assertIn("scripts/validate_publication_consistency.py", update)
        self.assertIn('python "$SOURCE/scripts/clean_legacy_calendar_snapshots.py" --root "$TARGET"', update)
        self.assertIn("Open failure alert", update)
        self.assertNotIn("gh pr create", update)
        self.assertNotIn("pull-requests: write", update)
        self.assertNotIn("HEAD:main", update)
        self.assertNotIn("reports/", update)
        self.assertNotIn("\n  push:\n", update)
        self.assertFalse((ROOT / ".github/dependabot.yml").exists())

        release = build
        for secret in ("ANDROID_KEYSTORE_B64", "ANDROID_KEYSTORE_PASSWORD", "ANDROID_KEY_ALIAS", "ANDROID_KEY_PASSWORD"):
            self.assertIn(secret, release)
        self.assertIn("assembleRelease bundleRelease", release)
        self.assertIn("apksigner", release.lower())
        self.assertIn("chmod +x ./gradlew", release)
        self.assertIn("RELEASE_VERSION", release)
        self.assertNotRegex(release, r"OrthodoxPrayers-v\d+\.\d+\.\d+")
        self.assertIn("origin/verified-data", release)
        self.assertIn("--require-current --strict-native-lanes", release)
        self.assertIn("Tag/version mismatch", release)
        self.assertIn("scripts/validate_release_readiness.py", release)

        for path in workflows.glob("*.yml"):
            for use in re.findall(r"uses:\s*([^\s#]+)", path.read_text(encoding="utf-8")):
                self.assertRegex(use, r"^[^@]+@[0-9a-f]{40}$", f"Action must be pinned by full SHA in {path.name}: {use}")

    def test_published_verifier_legacy_manifest_escape_hatch_is_debug_only(self):
        verifier = (ROOT / "scripts/verify.py").read_text(encoding="utf-8")
        build = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        update = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
        self.assertIn("--allow-missing-manifest", verifier)
        self.assertIn("not manifest.exists() and not manifest_signature.exists()", verifier)
        self.assertEqual(1, build.count("--allow-missing-manifest"))
        self.assertNotIn("--allow-missing-manifest", update)

    def test_application_requires_official_source_publication_and_vocalized_scripture(self):
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        strings = (ROOT / "app/src/main/res/values/strings.xml").read_text(encoding="utf-8")
        contract = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataContract.java").read_text(encoding="utf-8")
        network = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/NetworkEndpointSecurity.java").read_text(encoding="utf-8")
        self.assertIn("supportsSchema", repository)
        self.assertIn("MIN_SUPPORTED_SCHEMA_VERSION = 9", contract)
        self.assertIn("MAX_SUPPORTED_SCHEMA_VERSION = 9", contract)
        self.assertIn("raw.githubusercontent.com", network)
        self.assertIn("setInstanceFollowRedirects(false)", repository)
        self.assertIn("IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS", repository)
        self.assertIn("IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS", repository)
        self.assertIn("machine_translation_flag_invalid", repository)
        self.assertIn("automatic_diacritization_flag_invalid", repository)
        self.assertIn("A missing", repository)
        self.assertIn("DailyDataEndpointPolicy.jsonCandidates", repository)
        self.assertIn("verified-data/data/calendar/today.json", strings)
        self.assertIn("verified-data/data/update-manifest.json", strings)
        manifest_parser = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/UpdateManifest.java").read_text(encoding="utf-8")
        self.assertIn("manifest_revision_rollback", repository)
        self.assertIn("minimum_app_version_code", manifest_parser)
        self.assertIn("manifest_payload_hash_mismatch", repository)
        endpoint_policy = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DailyDataEndpointPolicy.java").read_text(encoding="utf-8")
        self.assertIn('date + ".json"', endpoint_policy)
        self.assertIn('candidate + ".sig"', endpoint_policy)


    def test_refresh_exceptions_future_dates_and_favorites_migration_are_hardened(self):
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        preferences = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/AppPreferences.java").read_text(encoding="utf-8")
        self.assertIn("unexpected_refresh_error", repository)
        self.assertIn("date_in_future", repository)
        self.assertIn("firstUnsafeTranslationError", repository)
        self.assertIn("segment_replacements", repository)
        self.assertIn("FAVORITES_SET", preferences)
        self.assertIn("getStringSet", preferences)
        self.assertIn("FAVORITES_LEGACY", preferences)

    def test_user_agent_uses_build_version_and_refresh_policy_uses_resume_signal(self):
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        policy = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/update/RefreshPolicy.java").read_text(encoding="utf-8")
        self.assertIn('"OrthodoxPrayers-Android/" + BuildConfig.VERSION_NAME', repository)
        self.assertIn("if (!resumed)", policy)

    def test_optional_guidance_is_collapsed_and_never_replaces_text(self):
        library = json.loads((ROOT / "app/src/main/assets/data/library.json").read_text(encoding="utf-8"))
        rendered = json.dumps(library, ensure_ascii=False)
        for banned in ("راجع الكنيسة", "راجع النص الكنسي", "تضاف هنا القطع", '"ar": "إرشاد"'):
            self.assertNotIn(banned, rendered)
        notes = [segment for service in library["services"] for segment in service.get("segments", []) if segment.get("type") == "note"]
        self.assertTrue(notes)
        self.assertTrue(all(note.get("collapsed_by_default") is True for note in notes))
        adapter = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/ReaderAdapter.java").read_text(encoding="utf-8")
        self.assertIn("bindNote", adapter)
        self.assertIn("expandedNotes", adapter)

    def test_quality_gate_verifies_detached_signature(self):
        quality_gate = (ROOT / "scripts/run_quality_gate.py").read_text(encoding="utf-8")
        self.assertIn("scripts/verify_data_signature.py", quality_gate)
        self.assertIn('quality.append("--allow-stale")', quality_gate)
        self.assertIn("scripts/validate_reader_services.py", quality_gate)
        self.assertIn("scripts/validate_scripture_translations.py", quality_gate)
        self.assertNotIn("--allow-signed-legacy", quality_gate)
        self.assertIn("--strict-native-lanes", quality_gate)
        self.assertIn("scripts/validate_native_source_contract.py", quality_gate)
        self.assertIn("scripts/validate_content_deduplication.py", quality_gate)
        self.assertIn("scripts/scan_repository_secrets.py", quality_gate)
        self.assertIn("scripts/verify_gradle_wrapper.py", quality_gate)
        self.assertIn("scripts/check_native_coverage.py", quality_gate)
        self.assertIn("--reject-invalid", quality_gate)
        scripture = (ROOT / "scripts/public_domain_scripture.py").read_text(encoding="utf-8")
        self.assertIn("MAX_TOTAL_UNCOMPRESSED_BYTES", scripture)
        self.assertIn("MAX_COMPRESSION_RATIO", scripture)
        self.assertIn("_safe_scripture_members", scripture)
        self.assertTrue((ROOT / "tests/test_clean_source_archive.py").is_file())
        self.assertTrue((ROOT / "tests/test_unsigned_generation.py").is_file())

    def test_code_and_content_rights_are_explicitly_separated(self):
        self.assertTrue((ROOT / "LICENSE").is_file())
        self.assertTrue((ROOT / "CONTENT_RIGHTS.md").is_file())
        self.assertFalse((ROOT / "LICENSE_PENDING_OWNER_DECISION.md").exists())
        rights = (ROOT / "CONTENT_RIGHTS.md").read_text(encoding="utf-8")
        self.assertIn("لا تغطي", rights)
        self.assertIn("النصوص", rights)

    def test_content_review_register_covers_all_services(self):
        register = json.loads((ROOT / "canonical/content_review_status.json").read_text(encoding="utf-8"))["services"]
        ids = set()
        for path in (ROOT / "app/src/main/assets/data/library.json", self.today_path):
            data = json.loads(path.read_text(encoding="utf-8"))
            ids.update(service["id"] for service in data["services"])
        self.assertEqual(ids, set(register))

    def test_no_legacy_unverified_calendar_snapshots_are_shipped(self):
        calendar_files = {path.name for path in (ROOT / "data/calendar").glob("*.json")}
        self.assertEqual({"today.json", self.today["date_iso"] + ".json"}, calendar_files)

    def test_source_tree_has_no_duplicate_daily_service_snapshots_or_handoff_files(self):
        service_files = {path.name for path in (ROOT / "data/services").glob("*.json")}
        self.assertEqual({"library.json"}, service_files)
        for obsolete in (
            "FILE_SHA256SUMS.txt",
            "VERIFICATION_AR.txt",
            "INSTALL_CLEAN_VERSION.ps1",
            "RECOVERY_NOTES_AR.md",
            "OWNER_SETUP_REQUIRED_AR.md",
            "خطوات_الاستبدال.txt",
        ):
            self.assertFalse((ROOT / obsolete).exists(), obsolete)
        self.assertFalse((ROOT / "reports").exists())

    def test_reader_recognizes_verified_daily_services_and_notes_toggle_both_ways(self):
        reader = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java").read_text(encoding="utf-8")
        adapter = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/ReaderAdapter.java").read_text(encoding="utf-8")
        self.assertIn("VERIFIED_DYNAMIC_PROPERS_NATIVE_SCRIPTURE_FAIL_CLOSED", reader)
        self.assertIn("collapsedNotes", adapter)
        self.assertIn("defaultCollapsed", adapter)

    def test_documentation_does_not_require_daily_human_text_correction(self):
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        owner = (ROOT / "SETUP_AR.md").read_text(encoding="utf-8")
        self.assertNotIn("لا تدمج Pull Request اليومي", contributing)
        self.assertIn("لا توجد خطوة تصحيح بشري يومية", owner)
        self.assertIn("verified-data", owner)

    def test_complete_core_prayers_are_official_jordan_pinned(self):
        registry = json.loads((ROOT / "canonical/static_prayer_sources.json").read_text(encoding="utf-8"))["services"]
        library = json.loads((ROOT / "app/src/main/assets/data/library.json").read_text(encoding="utf-8"))
        services = {item["id"]: item for item in library["services"]}
        self.assertEqual({"lord_prayer", "creed", "trisagion", "before_food", "after_food"}, set(registry))
        creed = " ".join(segment["text"]["ar"] for segment in services["creed"]["segments"])
        self.assertGreater(len(creed), 1000)
        for clause in ("نُورٍ مِنْ نُورٍ", "وَصُلِبَ عَنَّا", "وَبِكَنِيسَةٍ وَاحِدَةٍ", "وَأَتَرَجَّى قِيَامَةَ الْمَوْتَى"):
            self.assertIn(clause, creed)
        self.assertEqual(6, len(services["trisagion"]["segments"]))
        for service_id in registry:
            self.assertEqual("OFFICIAL_ARABIC_EXACT_PINNED", services[service_id]["source_provenance"]["status"])

    def test_incomplete_daily_offices_are_not_presented_as_complete(self):
        services = {item["id"]: item for item in self.today["services"]}
        self.assertEqual("قطع الغروب الموثقة لليوم", services["vespers"]["title"]["ar"])
        self.assertEqual("قطع السَحَر الموثقة لليوم", services["orthros"]["title"]["ar"])
        for service_id in ("vespers", "orthros", "morning_prayer", "evening_prayer", "small_compline"):
            self.assertIn("VERIFIED_DYNAMIC_PROPERS_NATIVE_SCRIPTURE_FAIL_CLOSED", services[service_id]["integrity"]["status"])
            self.assertNotIn("خدمة اليوم", services[service_id]["title"]["ar"])


if __name__ == "__main__":
    unittest.main()
