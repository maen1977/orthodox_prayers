## 5.2.0 — إصلاح التحديث اليومي عند فتح التطبيق

- قبول الحزمة الموقعة ذات التسعة أيام عندما يقع تاريخ اليوم داخل نافذتها، حتى لو بدأت الحزمة في اليوم السابق.
- إبقاء الحزم اليومية القديمة ذات اليوم الواحد مقيدة بالمطابقة التامة للتاريخ.
- التحقق من تطابق تغطية مسار اللغة مع تغطية البيان الموقّع ومنع أي تاريخ خارج النافذة.
- اختيار سجل يوم عمّان الحالي من `weekly_days` بعد التحقق بدل الرجوع إلى جذر الحزمة أو النسخة المضمنة القديمة.
- إضافة اختبارات رجعية لحزمة 2026-08-05 حتى 2026-08-13 عند فتح التطبيق في 2026-08-06.
- لم يتغير أي ملف من روزنامة 2026–2050.

## R44.1 — Android emulator jank gate stability hotfix

- Kept startup and memory budgets blocking on Android API 26, 29, and 33.
- Made cloud-emulator `gfxinfo` jank diagnostic on compatibility jobs to prevent false release failures caused by host rendering variance.
- Kept jank a strict blocking gate on API 35 with a minimum 90-frame sample.
- Warmed the reader before frame capture and used display-relative controlled gestures.
- Throttled reading-progress UI updates to one callback per frame and skipped unchanged percentages.

## R44 — Release artifact attestation and deterministic handoff

- Added fail-closed APK/AAB structural validation, package/version verification, signing verification, and secret-file exclusion.
- Added an in-toto-style release qualification attestation bound to the immutable 2026–2050 calendar lock.
- Added deterministic, secret-free qualified release handoff archives with complete SHA-256 manifests.
- Kept Android 8.0 (API 26) as the minimum and retained version 5.2.0 / code 50200.
- No calendar JSON file or calendar date was modified.

# R41 — بوابة التدقيق الديني الصارمة وحماية الروزنامة

- تثبيت التوافق عند Android 8.0 / API 26 مع الإبقاء على targetSdk وcompileSdk عند 36 دون حلول توافق قديمة تقلل الأمان.
- إضافة قفل SHA-256 غير قابل للتجاوز لملفات الروزنامة الداخلية من 2026-01-01 حتى 2050-12-31؛ أي تغيير في ملف أو حجمه أو قائمة السنوات يفشل بوابة الجودة.
- إضافة تدقيق آلي صارم للرسالة والإنجيل وإنجيل السحر عند وجوده: المرجع القانوني، مصدر كل لغة، بصمة النص، عدد الآيات، وبصمة كل سطر/آية، مع منع الترجمة الآلية والتشكيل الآلي والرجوع إلى لغة أخرى.
- توحيد سياسة عرض التذكار في الصفحة الرئيسية والتقويم والأيام القادمة والتنبيهات والـWidget: يظهر التذكار الموثق فقط، وتختفي العبارات العامة والحالات المعلقة أو غير المتوفرة بلا عنوان أو شرطة أو مساحة فارغة.
- تحميل سنة الروزنامة فقط عند فتح التقويم وتحرير فهرس البحث والذاكرة الاختيارية عند ضغط النظام، دون تفريغ بيانات اليوم الموقعة.
- رفع أهداف اللمس الأساسية للرجوع إلى 48dp وتحسين الوصول على الشاشات الصغيرة.
- دمج قفل الروزنامة والتدقيق الصارم في Build وUpdate قبل البناء والتوقيع والنشر، وإرفاق تقرير تدقيق واضح في GitHub Actions.

## 5.1.0 — Reader continuity and collection workflow

- Added a localized Continue Reading card backed by per-service progress persistence.
- Added direct favorite actions to Search and removal actions to Favorites.
- Preserved the signed-data compatibility floor at version code 50023.
- Modernized historical patch verifiers to accept safe newer application versions.

# R40.11 — إصلاح دليل الكنائس داخل مسارات اللغات

- تمرير `--language` إلى مدقق `source intelligence` بدل فحص ملف اليونانية أو الإنجليزية كأنه الملف الجامع.
- التحقق من بنية كل رابط كنيسة رسمي مع محاسبة كل مسار على الأسماء الأصلية المتاحة بلغته فقط.
- دمج الترجمات الخمس المراجعة الموجودة في `jordan_church_directory_seed.json` مع القائمة الحية ذات 41 رابطًا بواسطة مطابقة الرابط الرسمي الدقيق فقط.
- منع اختراع أو ترجمة أسماء الكنائس آليًا؛ الروابط الإضافية تبقى رسمية وبلا اسم مترجم إلى أن تتوفر ترجمة موثقة.
- الإبقاء على قبول bootstrap المضمّن القديم بوضع legacy معلن، مع فرض الترجمات المراجعة في كل نشر مؤرخ جديد.
- إضافة محاكاة كاملة لمسار يوناني يحتوي 10 موصلات و41 رابط كنيسة، واختبارات تمنع رجوع خطأ `church directory entry is incomplete`.
- اجتياز 442 اختبارًا و14 اختبارًا فرعيًا، إضافة إلى 46 مدقق إصدار غير تابع لـ pytest.

# R40.10 — إصلاح التحقق المستقل لمسارات اللغات

- تمرير `--language` من بوابة الأدلة الدينية إلى مدققي المحتوى وسياسة النصوص.
- جعل ملف اللغة المستقل يتحقق من لغته فقط، مع إبقاء الملف الجامع ملزمًا باكتمال العربية والإنجليزية واليونانية.
- تقييد فحص بدائل الرسالة والإنجيل باللغة المختارة بدل مطالبة ملف عربي بأدلة إنجليزية ويونانية غير موجودة عمدًا.
- إضافة اختبارات رجعية تحاكي فشل `missing native verification` في `ar.json`.

## R40.8 — Reader controls viewport and usable reading-area hotfix

- Fixed the real Android 15 layout defect revealed after emulator stabilization: expanding reader controls could consume nearly the entire screen and collapse the 630-row `RecyclerView` to 17 px.
- Wrapped the reader tools in a dedicated vertically scrollable viewport capped at 38% of the display height and at 340 dp, while respecting a smaller parent measurement constraint.
- Reserved a 180 dp minimum height for the prayer reader so controls cannot displace the text into an unusable strip on compact displays.
- Kept all reader tools reachable by scrolling inside the controls viewport and restored its scroll position to the top whenever the panel is opened.
- Strengthened Android instrumentation to require at least 120 dp of usable reader height, attached rows, and forward scrolling for long services before accepting the expanded or collapsed state.
- Passed 428 tests plus 14 subtests and all 44 non-pytest release validators. Local Android compilation remains unavailable only because the execution environment cannot resolve `services.gradle.org`; GitHub performs the final APK/instrumentation proof.

## R40.7 — Reader layout-readiness instrumentation stabilization

- Fixed the Android 15 runtime failure where `ReaderSmokeTest` inspected the `RecyclerView` after its adapter was populated but before Android attached the first visible child row.
- Replaced one-shot `waitForIdleSync()` assertions with a bounded 12-second readiness probe that requires the reader, adapter, minimum content count, measured height, visible child rows, and long-content scrolling to be simultaneously ready.
- Preserved strict failure behavior: the test still fails with a detailed snapshot when the reader does not become visible; no test is skipped, ignored, retried as success, or placed behind `continue-on-error`.
- Applied the same readiness check before and after expanding and collapsing reader controls, while preserving the reading-area height assertions.
- Passed 426 tests plus 14 subtests and every non-Gradle strict-native quality-gate validator. Android compilation and emulator execution remain delegated to GitHub because the local environment cannot resolve `services.gradle.org`.

## R40.6 — KVM-accelerated emulator boot and short-failure stabilization

- Fixed the 30-minute `Timeout waiting for emulator to boot` failure by enabling and verifying `/dev/kvm` before launching the Android emulator on the pinned Ubuntu 24.04 runner.
- Added a pre-launch host check that runs `emulator -accel-check`, records host/ADB diagnostics, and fails before boot when hardware acceleration is unavailable.
- Replaced the heavier Google APIs Pixel 5 AVD with a single lighter Android 15/API 35 AOSP Pixel 2 image using 2 GB RAM, a 256 MB heap, a 4 GB disk, and explicit `-accel on`.
- Reduced the emulator boot timeout from 900 to 480 seconds so an infrastructure failure stops promptly instead of consuming roughly half an hour.
- Moved `assembleDebug` and `assembleDebugAndroidTest` before emulator startup, keeping Gradle compilation outside the resource-sensitive emulator window.
- Restored the two required branded release assets omitted from R40.5 and added order-independent test imports through `tests/conftest.py`.
- Passed 426 tests plus 14 subtests, 65 focused workflow/release tests, and every non-pytest strict-native quality-gate validator.

## R40.5 — Single-emulator direct-instrumentation stabilization

- Removed the API 29/API 35 runtime matrix and retained one stable Android 15/API 35 emulator job for the single application build.
- Preserved Android 10 and older-device compatibility through the committed `minSdk=26` contract plus mandatory `lintDebug` and `lintRelease` checks instead of the unstable API 29 GitHub emulator.
- Replaced Gradle `connectedDebugAndroidTest` device discovery with deterministic APK assembly, direct ADB installation, and direct `am instrument` execution, avoiding the DDMLib `Unknown API Level` failure path.
- Added separate ADB timeouts for boot, installation, instrumentation, and screenshot transfer; successful Android instrumentation code `-1` is no longer misclassified as a failure.
- Added always-uploaded ADB, system-property, package, logcat, and final-screen diagnostics for any emulator failure.
- Kept offline reader coverage inside instrumentation, multilingual Play Store screenshot generation, fail-closed test-result parsing, and protected release dependency on the runtime test.
- Passed 425 tests plus 14 subtests and the complete strict-native quality gate, including the new Android SDK compatibility validator.

## R40.4 — Android emulator DDMLib readiness and in-test offline hotfix

- Confirmed the two supplied API 29 logs were byte-for-byte identical and failed because DDMLib could not read stable device properties, so Gradle classified the emulator as `Unknown API Level`.
- Strengthened emulator readiness to require three consecutive successful probes for boot completion, the requested SDK level, and Android package-manager availability.
- Removed Wi-Fi/mobile-data mutations from the host Bash script before Gradle device discovery.
- Moved offline enforcement into `ReaderSmokeTest` after instrumentation has started, with an assertion that no validated Internet connection remains and automatic network restoration afterward.
- Added longer emulator boot allowance, explicit RAM/heap sizing, and cold no-snapshot startup while retaining API 29 and API 35 coverage.
- Passed 425 tests plus 14 subtests and all constituent strict-native quality-gate validators available without Gradle distribution network access.

## R40.3 — Android emulator single-command Bash runner hotfix

- Replaced the multiline `android-emulator-runner` script block with one command that invokes `scripts/run_android_emulator_ci.sh`.
- Moved Android boot waiting, retry logic, offline network control, instrumentation, network restoration, and API 35 screenshot collection into the repository Bash script.
- Added regression tests that execute the runner through `/bin/sh -c`, matching the action behavior that previously split multiline loops.
- Preserved fail-closed offline tests and automatic restoration of Wi-Fi and mobile data.


## R40.2
- Fixed offline Android reader instrumentation by using the embedded package date for dynamic next-Sunday services.
- Added a current-package-only dynamic reader test.
- Wait for Android boot completion and retry network-disable commands before offline instrumentation.

# R40.1 Android Emulator Bash Hotfix

- Run the emulator action script inside explicit Bash because the action invokes `/bin/sh` by default.
- Add regression checks that reject direct `pipefail` use under the emulator `script` input.
- Restore the two branded release icon files omitted from the R40 source ZIP.
- Preserve the R40 nine-day, twice-daily, automated-source comparison and release pipeline.

## 5.0.23 — R40 automated source research and release pipeline

- Added a fail-closed nine-day source-comparison engine with Orthodox Jordan and Jerusalem calendar priority, dated cross-check connectors, evidence hashes, and automatic publication decisions without a daily human-review dependency.
- Added source-structure drift detection, retries, per-run URL caching, machine-readable comparison reports, and automatic failure/recovery issue context.
- Added Android emulator coverage on API 29 and API 35 with network disabled, real Arabic/English/Greek store screenshots, and mandatory instrumentation before protected release.
- Added final APK permission enforcement and deterministic Play Console packaging for the AAB, graphics, multilingual listings, screenshots, privacy, Data Safety, rights, and checksums.
- Added complete 2026–2050 year-boundary/leap-window validation and release metadata/privacy updates.
- Passed 420 tests plus 14 subtests and all constituent strict-native quality-gate validators available without Gradle network access.

## 5.0.23 — R39 internal 2026–2050 calendar horizon

- Added a compact offline Jerusalem/Jordan old-calendar baseline for every civil day from 2026-01-01 through 2050-12-31 (9,131 days).
- Split Android calendar assets by year so only the selected year is parsed on low-memory devices.
- Calculated Orthodox Pascha, the Triodion/Pentecostarion cycle, major fixed feasts, relative Saturdays/Sundays, fasting baseline, and appointed Liturgy selection locally.
- Kept the believer-facing signed window at exactly nine days and retained two daily update runs at 04:23 and 16:43 Asia/Amman for source verification and corrections.
- Preserved fail-closed religious content: daily saints and exact readings are included only when a pinned or signed source exists; no AI translation, invented names, or cross-language fallback is used.
- Added year-boundary, leap-year, 2050-horizon, lazy-loading, navigation-boundary, and source-policy regression coverage.
- Passed 407 tests plus 14 subtests and every constituent strict-native quality-gate check.

## 5.0.23 — R38.3 Matins Gospel schema hotfix

- Added `matins_gospel` to the supported daily reading schema instead of dropping the appointed Orthros reading.
- Applied the same native-language evidence, exact-text hash, localization, embedded-data, and Android sanitizer checks used for the Epistle and Gospel.
- Kept the Epistle and Gospel as the required daily core while treating the Matins Gospel as optional and fully validated when present.
- Added regression coverage that accepts `matins_gospel`, rejects unknown reading kinds, and prevents it from bypassing native-text sanitization.
- Passed 401 tests plus 14 subtests and all remaining strict-native quality-gate checks.

## 5.0.23 — R38.1 fixed nine-day quality-gate contract

- Unified every active rolling-window contract on exactly nine days: today plus eight future days.
- Rejected legacy 21-day publications instead of treating them as supported input.
- Updated protected-contract hashes after reviewing the intentional R38 schedule and horizon changes.
- Corrected Arabic, English, and Greek update text to say twice daily at 04:23 and 16:43 Jordan time.
- Passed 398 tests plus 14 subtests and all constituent strict-native quality-gate checks.

## 5.0.23 — R36 card-only Settings hub

- Rebuilt the main Settings screen as five action cards for language, font size, calendar/reminders, update/data, and churches/live services.
- Moved the first four setting groups into dedicated back-navigable detail pages without removing any existing option.
- Kept the About section plain, in the same final position, with its original text and selectable provider notice.
- Kept the Settings bottom-navigation state active throughout settings detail, sources, and church-directory screens.
- Added regression coverage for card routing, back navigation, and in-place refresh after changing a setting.

## 5.0.23 — R35 compact back navigation and smart Home shortcuts

- Replaced wide text back buttons with a mirrored arrow-only 44dp control in subpages and readers.
- Rebuilt Home quick access as four two-column cards for today’s prayer, readings, calendar/fasting, and churches/live services.
- Added one context-aware Home card for feasts, Sunday Communion preparation, morning prayer, pre-Liturgy preparation, Compline, or the upcoming-service window.
- Preserved scroll restoration, the four primary navigation sections, and complete Arabic/English/Greek localization.
- Added regression coverage for navigation accessibility, the four-card layout, smart routing, and localized card titles.

## 5.0.23 — R31 dependency-free icon safe-zone test hotfix

- Removed the accidental Pillow dependency from `tests/test_icon_safe_zone.py`.
- Kept the real PNG validation by decoding the committed 8-bit RGBA asset with the Python standard library.
- Continue enforcing a 108×108 adaptive-icon canvas and a maximum 66×66 non-transparent artwork box.
- Verified the test directly with `python -S`, proving it runs without site packages.

## 5.0.23 — Church Prayers branding hotfix

- Unified the installed launcher label as `Church Prayers` without changing the Android application ID.
- Replaced launcher and Play Store artwork with the supplied Jerusalem cross.
- Added a Jerusalem-cross monochrome notification/themed icon.
- Renamed downloadable debug/release APK and AAB artifacts to `Church-Prayers-*`.
- Added Windows ICO/PNG sidecar branding and documented the Windows APK icon limitation.

## 5.0.23 — R28 runtime signed-payload storage alignment

- Unified the signed remote payload ceiling at 12,000,000 bytes across manifest parsing, HTTP download, and atomic on-device storage.
- Raised `minimum_app_version_code` to 50023 so 5.0.22 and older fail early with an app-update requirement instead of downloading an unsavable moving-window package.
- Manual update failures now automatically preserve/open technical diagnostics and show the stable diagnostic code in the failure toast.
- Added regression coverage for the exact large-language-payload failure.

## 5.0.22 — R27 public endpoint payload-size hotfix

- Fixed public endpoint verification for signed language payloads larger than the obsolete 6,000,000-byte verifier limit.
- Derive the exact download bound from the already verified signed manifest while enforcing the same 12,000,000-byte ceiling used by Android.
- Keep paths, languages, declared sizes, hashes, and signatures fail-closed and add regression coverage above the former six-megabyte boundary.

## 5.0.22 — R26 moving-window schema hotfix

- Fixed `daily_data.schema.json` so schema 10 accepts the supported 9–42 day moving horizon instead of only the original nine-day package.
- Preserved schema 9 compatibility at exactly seven future days.
- Added behavioral regression coverage for 9, 21, and 42 days and both out-of-range boundaries.

## 5.0.22 — R25 source-ID hotfix

- Fixed the Arabic Transfiguration prokeimenon being removed by the strict native-language lane gate.
- Normalized historical proper-source IDs to the canonical IDs registered in the native-source contract.
- Added a regression test for 2026-08-19 across Arabic, English, and Greek.

## 5.0.22 — Rolling-window feast-title hotfix (2026-07-31)

- Fixed the 2026-08-19 rolling-window failure by validating Jerusalem fixed feasts against an explicit canonical Arabic alias allowlist instead of one short title only.
- Added approved aliases for the Transfiguration, Dormition, Nativity of the Theotokos, Exaltation of the Cross, and Entry of the Theotokos.
- Kept the check fail-closed: Unicode/spacing/diacritic normalization is allowed, but semantic names must be explicitly listed.
- Made `scripts/update.py` prepare the exact native Scripture horizon itself for manual runs; GitHub Actions passes `--skip-scripture-preparation` after its dedicated preparation step to avoid duplicate work.
- Added regression tests for canonical feast aliases, rejection of unrelated titles, and update/workflow Scripture-preparation ownership.

# 5.0.22 R24 — Nine-day appointed Liturgy engine

- Replace the old seven-day outlook with one rolling window of exactly nine consecutive days: today plus the next eight days.
- Select the appointed service independently for every date: St John Chrysostom, St Basil the Great, Presanctified Gifts, St James only by documented dated override, no Divine Liturgy, or unresolved Typikon.
- Store and display the service type, service form, localized reason, authority, source, confidence, and full-text availability.
- Keep liturgy type separate from service form, including morning Divine Liturgy, Vespers with Divine Liturgy, and Lenten Vespers with Presanctified Gifts.
- Open one complete appointed service from preparation and pre-Communion prayers through the fixed rite, Communion, thanksgiving, and dismissal.
- Forbid cross-rite fallback: an unavailable appointed rite is blocked instead of being silently replaced by St John Chrysostom.
- Publish the nine-day package atomically: any failed or incomplete future date restores the original current-day data and leaves no partial final package.
- Keep incomplete or unsafe native editions fail-closed until substantive Arabic, English, and Greek source texts pass the full-service contract.
- Add schema 10 while retaining read compatibility with already signed schema 9 packages.
- Add regression coverage for the nine-day contract, liturgical rules, full beginning-to-end composition, no-fallback behavior, and atomic publication rollback.

## 5.0.17 R20.1 — resilient automatic updates

- Try the signed GitHub raw endpoint first and a pinned jsDelivr mirror second.
- Distinguish offline, DNS, server, TLS, signature, and invalid-payload failures.
- Never show “no internet” for a server publication or signature problem.
- Verify the public manifest and all three signed language payloads after every GitHub publication.
- Schedule early publication at 00:07, retry at 00:37, and supplement at 06:37 Asia/Amman.

## Follow-along Liturgy scope and dual daily updates

- Restore the important Home shortcuts for readings, prayers, calendar and fasting,
  seven-day outlook, churches and live services, search, favorites, history,
  languages, and settings.
- Restore a compact seven-day fasting/no-fast table on Home, with each row opening
  its matching calendar day.
- Open every reader with its controls hidden and let the believer show or hide them
  only through the explicit control handle; ordinary scrolling never changes them.
- Preserve the exact reading position when controls are shown, hidden, or rebuilt
  after a reading-setting change.
- Check the signed update manifest automatically whenever the app enters a new
  foreground session, not only after a missed 01:00 or 06:00 window.
- Preserve an in-flight scheduled retry when the app opens after a publication
  window, and retry delayed publication every 15 minutes in foreground/background.
- Fix Android unit-test compilation by explicitly handling checked `JSONException`
  calls in `DailySnapshotRegressionGuardTest`.
- Make the believer-facing Home screen open one continuous full Liturgy directly.
- Compose available native Communion preparation with the fixed Liturgy without duplicating source text.
- Add an official-only Matins Gospel daily slot that stays hidden when its native source text is unavailable.
- Highlight source-marked silent prayers for the priest and faithful and add jumps for both Entrances, readings, Communion, and dismissal.
- Schedule signed refreshes at 01:00 and 06:00 Asia/Amman, with missed-window catch-up on app open.
- Prevent a later same-day revision from deleting already accepted readings or Liturgy propers, both in publication and on device.
- Keep Arabic, English, and Greek text lanes independent with no translation or cross-language fallback.
- Remove OCR separator artifacts from the imported English and Greek Communion text.

## 5.0.15 R19.2 — Compound Scripture reference hotfix

- Accept ordered semicolon-separated canonical spans from the same Bible book.
- Fill every appointed span from each exact same-language corpus without including omitted verses.
- Preserve fail-closed all-or-nothing publication and exact per-verse hashes for compound readings.
- Cover the exact 2026-07-23 DCS reference `1CO.10.28-33;1CO.11.1-8`.

## 5.0.15 R19.1 — Root patch deployment guard

- Fail at the start of the quality gate when R19 files were extracted only partially or into a nested directory.
- Ship a deterministic root-overlay patch containing `app/build.gradle.kts` at the exact repository-relative path.
- Allow a complete clean-source archive to use a wrapper-free root layout for direct repository overwrite.
- Add regression coverage proving that the patch has no wrapper directory and carries version 5.0.15 / code 50015.
- Keep application behavior and signed religious content unchanged.

## 5.0.15 R19 — Language accuracy and user-experience refinement

- Correct native-pack completeness so Arabic, English, and Greek are each measured from their own independent bundled library, regardless of the currently selected UI language.
- Add Arabic to the visible three-language coverage summary and preserve the existing no-cross-language-fallback policy.
- Format app-owned timestamps in the selected in-app language instead of inheriting an unrelated device locale.
- Correct the remaining Greek font-family labels and isolate technical identifiers so they do not reorder surrounding Arabic text.
- Replace repeated 30-minute tapping with a proper time picker for reminders and quiet hours.
- Keep everyday update status concise and move hashes, source IDs, and diagnostic codes behind an optional technical-details control.
- Add a confirmed reset for reading appearance and behavior while preserving favorites, notes, history, and reminder schedules.
- Make the public source registry deterministic and stop assigning an unverified date merely because a source record was rebuilt.
- Align the canonical publication contract with the real single 00:00 workflow, which verifies the published branch in the same run rather than claiming a removed 00:15 schedule.

## 5.0.14 R18.4 — DCS Matthew-reference parser hotfix

- Accept the official Digital Chant Stand `Mt.` abbreviation in addition to `Matt.` so the Gospel reference remains publishable.
- Extract the regular-cycle Epistle and Gospel pair into the source-health snapshot from the verified `/h91/` service page.
- Reuse that same-day hashed health observation in the Jordan contract gate, avoiding a fragile second fetch while rejecting stale or unhashed observations.
- Preserve cross-chapter DCS references such as `1 Cor. 10:28-33; 11:1-8`.
- Keep the Jordan fail-closed authority gate unchanged and add regression coverage for the exact 2026-07-21 failure.

## 5.0.14 R18.3 — SettingsScreen Java compile hotfix

- Rename the Liturgy service-coverage badge local variable to avoid colliding with the earlier language-coverage `TextView` in `SettingsScreen.createView()`.
- Add a regression contract for the exact duplicate-local-variable compilation failure reported by GitHub Actions.
- Keep application behavior and signed daily data unchanged; this is a source-only Java compile correction.

## 5.0.14 R18.2 — legacy verified-data import migration

- Clean obsolete top-level calendar aliases inside detached `verified-data` worktrees before Debug and Release imports.
- Keep strict publication verification unchanged while allowing Debug CI to import a legacy branch that has neither update manifest nor manifest signature.
- Reject partial, unsigned, or invalid manifests even when the Debug compatibility flag is enabled.
- Clean the assembled Update publication tree again before signing as defense in depth.
- Add workflow and verifier regression contracts for the exact GitHub Actions failure.

## 5.0.14 R18.1 — publication alias hotfix

- Run `clean_legacy_calendar_snapshots.py` after successful daily validation and before unsigned/signed publication.
- Prevent stale top-level dated aliases such as `data/calendar/2026-07-17.json` from breaking the strict verified-data consistency gate.
- Preserve historical language-lane payloads under `data/daily/YYYY-MM-DD/`; only the top-level current-day alias directory is pruned.
- Add a regression test reproducing the GitHub Actions failure and proving cleanup restores a valid signed publication tree.

# 5.0.14 R18 — Orthodox source intelligence and smart discovery

- Added nine audited official-source connectors with Jordan/Jerusalem authority tiers.
- Added daily source-health snapshots, reading-reference consensus, poison detection, strict HTTPS allowlists, bounded downloads, and fail-closed local-authority conflict checks.
- Added an official Jordan church directory, live links, and discovered dated service links.
- Added unified smart search across prayers, readings, sources, churches, live resources, and official service links, including Arabic normalization and one-edit typo tolerance.
- Added truthful Divine Liturgy variable coverage and a packaged fallback coverage report.
- Added R18 workflow validation before signing, in the publication worktree, in the committed archive, and after origin publication.
- Preserved the signed R17 embedded daily payload; R18 metadata becomes part of the next protected signed daily publication.

# 5.0.13 R17 — Reliable signed daily updates

- Replaced exact-alarm permission with a network-aware WorkManager refresh at 00:05 Amman time.
- Throttled same-day correction checks to once every 30 minutes instead of every app resume.
- Added a signed update manifest with date, monotonic revision, minimum app version, size, and SHA-256 per language lane.
- Added rollback protection so an older same-day manifest revision cannot replace a newer accepted revision.
- Added publication-consistency gates that require the today alias, dated fallback, embedded asset, and every published lane to agree byte-for-byte and by date.
- Added manifest generation, signing, origin verification, Android parsing tests, and R17 regression contracts.

# 5.0.12 R16 — Liturgy, Communion prayers, and source transparency

- Added a user-visible registry of the active Orthodox, Scripture, and liturgical sources.
- Added source links to Settings, prayer readers, and Scripture detail screens.
- Separated personal Communion preparation from date-dependent Orthros and Liturgy propers.
- Added dedicated pre- and post-Communion service entries with truthful completeness states.
- Removed unregistered quiet-prayer prose from the Divine Liturgy template.
- Removed the unproven “Full Divine Liturgy” claim and added a machine-checked completeness gate.
- Added R16 source/Communion validators and regression tests.

# 5.0.11 R15 — HomeScreen Java compile fix

- Added the missing `ThemePalette` import used by the next-Sunday card.
- Added a regression contract and root-level patch verifier.
- No liturgical, lectionary, fasting, or user-interface behavior was changed.

# 5.0.10 R14

- Rename the visible application title from Church Agenda to Church Prayers in Arabic, English, and Greek.
- Simplify Home by removing the duplicate commemoration line, the blue three-column status card, and the large today-fasting details card while preserving their data and internal components.
- Hide Search, Favorites, Calendar, and Language Packs from Home quick access without deleting their screens or navigation routes.
- Keep Readings, Prayers, History, Upcoming Days, Settings, the full Divine Liturgy, seven-day details, and Next Sunday on Home.
- Add explicit symbol-first food rules on fasting-day cards: ✓ permitted and ✕ forbidden for meat/poultry, dairy, eggs, fish, wine, and oil.
- Remove the call and privacy-policy actions from Settings while keeping the free-app provider notice and the privacy file in the project.
- Add R14 root-patch verification, UI regression tests, and a documented review of the Orthodox Jordan daily-prayer index.

# 5.0.9 R13

- Add novice-friendly fasting guidance for today and the next seven days.
- Show permitted and restricted food categories, reason, duration status, spiritual note, and health note in Arabic, English, and Greek.
- Add a documented total-abstinence model that rejects invented clock times.
- Add a fail-closed fasting guidance validator and Android UI rendering on Home, Upcoming, and Calendar Day screens.
- Preserve compatibility with the immutable previously signed schema-9 daily payload while requiring the extension on newly generated data.

# 5.0.8 R12

- Preserve the exact localized prokeimenon during native Scripture corpus preparation.
- Limit native-corpus reset to Epistle and Gospel only.
- Run daily UI localization validation inside the update pipeline before success is reported.
- Add R12 patch verification and regression coverage for 2026-07-20.

## 5.0.7 — R11 robust two-phase patch deployment

- جعل مزامنة الأحد القادم تكتشف المرحلة المبكرة تلقائيًا عند وجود `source`، حتى لو بقي مستدعٍ أقدم لا يمرر `require_complete=False`.
- إبقاء الاستدعاء النهائي بعد الـCorpus صارمًا تلقائيًا عند غياب `source`.
- إضافة فحص `PIPELINE_PATCH_OK level=R11` في بداية `scripts/update.py` لمنع تشغيل ملفات مختلطة أو Patch مفكوك داخل مجلد فرعي.
- تجهيز حزمة تعديلات بلا مجلد غلاف حتى تستبدل الملفات مباشرة عند فكها في جذر المستودع.

# 5.0.6 R10

- Fixed the two-phase next-Sunday pipeline: canonical references may remain pending before native corpus resolution, while the final post-corpus synchronization remains strict and fail-closed.
- Prevented the early integrity pass from aborting before the Jordan publication lock and official evidence are written.
- Added a regression test for the exact 2026-07-20 update ordering failure.
- Version code 50006.

# 5.0.5 R9

- Re-synchronized `next_sunday` and its seven-day upcoming card after exact native Scripture filling.
- Prevented complete next-Sunday readings from retaining empty preview references.
- Added fail-closed checks for missing Epistle/Gospel references after corpus resolution.
- Added a regression test for 2026-07-20 → 2026-07-26 schedule synchronization.
- Version code 50005.

# 5.0.4 R8

- Fixed JSON Schema integrity-envelope overlap: valid release candidates may satisfy both verified-source and native-text envelopes.
- Added regression coverage for legacy-only, native-only, combined, and empty integrity objects.
- Version code 50004.

# 5.0.1 R5 — إصلاح استيراد Activity بعد ترقية Predictive Back

- إعادة `import android.app.Activity;` إلى `MainActivity.java` لأن عقد `ScreenHost.activity()` ما زال يعيد النوع `Activity`.
- الإبقاء على `ComponentActivity` و`OnBackPressedDispatcher` دون الرجوع إلى `onBackPressed()` القديم.
- توسيع اختبار عقد Predictive Back ليتحقق من وجود استيراد `Activity` المطلوب.
- نجاح 95 اختبارًا آليًا، وفحوص المحتوى والتوقيعات واللغات وجدولة منتصف الليل.

# 5.0.1 R4 — إصلاح Predictive Back وAndroid Lint

- استبدال `Activity.onBackPressed()` بـ AndroidX `OnBackPressedDispatcher`.
- تحويل `MainActivity` إلى `ComponentActivity` وربط `OnBackPressedCallback` مع مكدس التنقل الداخلي.
- إزالة التسجيل اليدوي المكرر عبر `OnBackInvokedDispatcher`.
- إضافة اعتماد `androidx.activity:activity:1.10.1`.
- إضافة اختبار عقد إصدار يمنع رجوع `onBackPressed()` القديم.
- نجاح 95 اختبارًا آليًا وفحوص Workflow وGradle Wrapper والأسرار والتوقيعات واللغات.

# 5.0.1 R3 — إصلاح تجميع Java للقارئ

- إصلاح محارف السطر الجديد في مشاركة المقطع وتذييل المصدر داخل `ReaderAdapter.java` و`ReaderScreen.java`.
- إضافة فحص آلي يمنع وجود String أو Char غير مغلق في أي سطر Java.
- نجاح 94 اختبارًا وبوابة الجودة الكاملة.

# 5.0.1 — تحديث يومي ثابت عند منتصف الليل

- تثبيت تشغيل التحديث اليومي عند الساعة 00:00 بتوقيت `Asia/Amman` فقط.
- إزالة تشغيل التأكيد عند 00:15 وإزالة الفحص الدوري كل 12 ساعة.
- إضافة AlarmManager دقيق عند سماح Android، مع WorkManager احتياطي آمن عند غياب الإذن.
- إعادة تثبيت الموعد بعد تشغيل الهاتف، تحديث التطبيق، تغيير الساعة أو تغيير المنطقة الزمنية.
- إضافة زر داخل الإعدادات لفتح إذن المنبه الدقيق، مع إعادة المحاولة تلقائيًا عند تأخر نشر البيانات أو انقطاع الإنترنت.
- رفع الإصدار إلى 5.0.1 ورقم البناء إلى 50001، مع نجاح 93 اختبارًا.

# 5.0.0 — التخزين متعدد اللغات والقارئ الاحترافي والإصدار المحمي

- فصل كاش البيانات الموقعة لكل لغة والاحتفاظ بآخر 30 يومًا.
- توحيد حالة الإصدار والتحقق داخل الهاتف من الخدمات والتوقيع والمصادر.
- رفع SDK وGradle، وإضافة القارئ الورقي/الليلي والسطوع والتقدم والملاحظات.
- إضافة سجل البحث وساعات الهدوء وWidget يومي.
- إضافة SBOM وأرشيف مصدر نظيف وبصمات لجميع مخرجات الإصدار.
- لم تتم إضافة الصوت بناءً على طلب صاحب المشروع.

## إصلاح مسار قراءات الأحد القادم — 4.3.0 hotfix

- إصلاح تعطل التحديث عندما تكون قراءات اليوم موجودة في المقطع الكتابي المحلي بينما قراءات الأحد القادم تحتاج إلى الـCorpus الكامل.
- إضافة تحميل كسول وآمن للـCorpus العام المسجل لكل لغة، مع Cache وفشل مغلق عند تعذر المصدر.
- إضافة اختبارين يمنعان رجوع المشكلة، ورفع مجموع الاختبارات إلى 91 اختبارًا ناجحًا.

# 4.3.0 — اكتمال الإنجليزية واليونانية والقراءات الأصلية

- إكمال حزم الخدمات: العربية 601/601، الإنجليزية 758/758، واليونانية 750/750.
- استيراد القداس الإلهي الإنجليزي واليوناني من نسخة ثنائية اللغة مسجلة، مع إبقاء مسارات اللغات مستقلة.
- إضافة لقطات Scripture عامة الملكية لقراءات 16 يوليو 2026 من فان دايك وWorld English Bible والنص البطريركي اليوناني 1904.
- إضافة استيراد صريح لـ `--corpus-kind public-domain` وحفظ الترخيص وحالة التوزيع في Manifest.
- إضافة مولد مرشح يومي آمن لا يلمس البيانات الموقعة: `build_release_candidate.py`.
- إضافة fixtures للقراءات من 16 إلى 23 يوليو لضمان توليد غير متصل قابل لإعادة الاختبار.
- رفع الإصدار إلى 4.3.0 ورقم البناء إلى 43000، وتوسيع الاختبارات إلى 90 اختبارًا ناجحًا.
- إبقاء ترقية المرشح إلى بيانات التطبيق خطوة محمية بالمفتاح الخاص الأصلي؛ لا يُنشأ توقيع بديل.

# 4.2.0 — التقويم والتذكيرات وتجربة القراءة واستيراد اللغات

- إضافة تقويم كنسي شهري مع صفحات تفاصيل للأيام الموجودة في الحزمة الموقّعة، وخيار عرض غريغوري أو يولياني قديم.
- إضافة تذكيرات اختيارية لصلاة الصباح والمساء والقراءات والأعياد والصيام وتذكير شخصي، مع طلب إذن الإشعارات على Android 13 فما بعد.
- إضافة سجل آخر 20 نصًا، وتثبيت النصوص في الصفحة الرئيسية، ومجموعات للمفضلة وإعادة ترتيبها.
- إضافة نوع الخط وتباعد الأسطر والتمرير التلقائي وإدارة اللغات النشطة ضمن إعدادات القراءة.
- تحديث WorkManager إلى 2.11.2، وتغيير الفحص الدوري الاحتياطي إلى 12 ساعة مع بقاء جدولي 00:00 و00:15 بتوقيت عمّان.
- إضافة `merge_authorized_native_services.py` لدمج نصوص أصلية مصرّح بها فقط، و`export_missing_native_fields.py` لإصدار تقارير النقص الإنجليزية واليونانية.
- منع إشعار العيد أو الصيام عندما يكون النص الأصلي للغة المختارة غير متوفر.
- رفع الإصدار إلى 4.2.0 ورقم البناء إلى 42000، وتوسيع اختبارات Python إلى 86 اختبارًا ناجحًا.
- يبقى إصدار Production محجوبًا حتى استيراد النص الكامل المصرّح به للقداس ومكتبات الكتاب المقدس الأصلية في اللغات الثلاث.

# 4.1.5-r3 — إصلاح صلاحية gradlew على GitHub وWindows

- إصلاح فشل بوابة الجودة عندما ترفع الملفات من Windows أو واجهة GitHub ويُسجل `gradlew` بوضع `100644`.
- إضافة `scripts/ensure_gradlew_executable.py` لتطبيع صلاحية التنفيذ قبل اختبارات Python وقبل بوابتي Debug وRelease.
- جعل `run_quality_gate.py` يصلح الصلاحية ذاتيًا قبل اختبار عقد الإصدار، بدل الاعتماد على خطوة لاحقة في Workflow.
- جعل مولّد المصدر يضع `gradlew` دائمًا بوضع `0755` داخل ZIP حتى لو كانت نسخة العمل غير تنفيذية.
- إضافة محاكاة رجعية لحالة `0644` داخل اختبار الحزمة النظيفة، مع بقاء المجموعة **84/84** ناجحة.

# 4.1.5-r2 — تحصين خط التحديث وحزمة المصدر

- فصل تنزيل وتحليل المصادر عن مفتاح توقيع البيانات؛ يعمل التوليد أولًا بوضع `--unsigned` وتُرفض التوقيعات القديمة بجوار JSON جديد.
- استعادة المفتاح الخاص بعد اكتمال التحقق فقط، وحذفه قبل Commit أو Push إلى `verified-data`.
- إضافة حماية Zip Bomb لمكتبات USFM: حد عدد الملفات والحجم غير المضغوط والحجم الفردي ونسبة الضغط والمسارات المشبوهة.
- إصلاح صلاحية تنفيذ `gradlew` داخل Git وحزمة ZIP النظيفة.
- جعل Debug APK يستورد أحدث بيانات منشورة موقعة ويتحقق منها بعد نجاح بوابة المصدر.
- توسيع الاختبارات إلى 84 اختبار Python ناجحًا، بما فيها اختبارات الحزمة النظيفة والتوليد غير الموقّع وحماية ZIP.

# 4.1.5-r1 — نسخة مصدر منقحة

- تنظيف نسخة التسليم من `.git` والكاش وملفات bytecode ورسائل Commit وسكربتات التحقق القديمة.
- نقل تقارير الإصلاح وملاحظات الإصدارات التاريخية إلى `docs/history`.
- جعل `--strict-native-lanes` ينفذ فحصًا حقيقيًا يمنع نسخ العربية والأبجدية الخاطئة دون الادعاء باكتمال اللغات.
- إضافة تحقق مستقل من Gradle Wrapper وتثبيت JAR الرسمي المتوافق مع Gradle 8.9.
- حماية سر توقيع بيانات اليوم عبر Environment باسم `production-data-signing`.
- تحسين مولّد ZIP ليكون حتميًا، ويفحص المسارات، ويستبعد الأسرار والكاش وملفات البناء.
- تحديث وثائق الجاهزية والحالة الحالية إلى 84 اختبار Python ناجحًا.

# 4.1.5

- إضافة سجل قطع يومية موثقة بحسب التاريخ اليولياني، ويشمل تذكار وضع ثوب والدة الإله في 2 تموز القديم بالعربية والإنجليزية واليونانية.
- إضافة بروكيمينن العيد، ودورة بروكيمينن أيام الأسبوع، ودورة بروكيمينن الآحاد بحسب اللحن في اللغات الثلاث.
- إدخال الطروبارية والقنداق في صلاة الصباح والمساء والسحر والغروب والقداس عندما تتوفر قطع اليوم.
- منع إدخال عبارات «النص غير متاح» داخل الصلاة أو القداس؛ يبقى المرجع فقط مؤقتًا إلى أن تملأه مرحلة النص الأصلي.
- تنظيف المقاطع القديمة غير المحلولة أو الفارغة أو التي تحمل رسائل عدم التوفر عند تركيب الخدمة داخل أندرويد.
- تسجيل نطاقات مصادر قطع اليوم في عقد المصادر، وإضافة اختبارات للتاريخ الحالي ولصلاحية نطاق المصدر.
- رفع الإصدار إلى 4.1.5 وتوسيع مجموعة الاختبارات إلى 73 اختبارًا.

# 4.1.4

- إصلاح فقدان المرجع القياسي ونشر نص الرسالة والإنجيل في مسارات العربية والإنجليزية واليونانية.
- إضافة مصادر كتاب مقدس أصلية مستقلة وملكية عامة مع التحقق من اكتمال كل آية.
- إعادة تركيب خدمات اليوم بعد تعبئة القراءات، ومنع النشر إذا بقيت قراءة أو موضعها داخل القداس ناقصًا.
- إظهار رسالة واضحة بدل بطاقات القراءات الفارغة، خصوصًا البروكيمنن غير المتوفر.

# سجل التغييرات

## 4.1.2
- Fixed Android rejecting valid signed daily payloads when language-indexed metadata objects used `ar`, `en`, and `el` keys.
- Localized-text validation now requires string-valued language slots.
- Added regression coverage for `language_sources` and `native_source_verification`.

## 3.5.1-r4 — إصلاح مسار التحديث اليومي للمصادر الأصلية

- إصلاح `IsADirectoryError` الذي كان يحوّل مسار cache الفارغ إلى مجلد المستودع ويحاول قراءته كملف.
- جعل `orthodox_integrity.py` يفهم سياسة مكتبة رسمية أصلية مستقلة لكل لغة بدل منطق مكتبة عربية قديم.
- الاحتفاظ بالمرجع القانوني داخليًا دون نسخه إلى لغة أخرى، وترك النص غير المتوفر فارغًا حتى يستورده corpus رسمي باللغة نفسها.
- منع فقرات القداس الفارغة بعرض حالة واجهة محلية «النص الأصلي غير متاح» دون ترجمة نص ديني.
- نقل تقارير الفحص المؤقتة إلى `.cache` حتى لا تفشل بوابة جودة شجرة المصدر.
- إضافة اختبارين رجعيين للمسار الفارغ ولمنع فقرات القارئ الفارغة؛ أصبحت المجموعة 63 اختبارًا.

## 3.5.1 — إصلاح GitHub Actions وتشخيص بناء Android

- إصلاح تجميع Android في `DataRepository`: حساب SHA-256 للنص باستخدام UTF-8 bytes.
- إيقاف Dependabot version updates بحذف `.github/dependabot.yml`.
- إبقاء Workflowين فقط: Build وUpdate.
- منع Update من العمل عند Push والإبقاء على 00:00 و00:15 بتوقيت عمّان والتشغيل اليدوي.
- فصل Unit Tests وLint Debug وبناء Debug APK إلى خطوات مستقلة.
- تعطيل CodeQL والمحاكي مؤقتًا إلى أن يستقر بناء Debug.
- تحديث رقم التطبيق واسم مشروع Gradle الظاهر وتعليمات GitHub Desktop.

## 3.5.0 — مصادر أصلية مستقلة وبوابة نشر مغلقة

- فصل العربية والإنجليزية واليونانية إلى ثلاث قنوات دينية مستقلة، ومنع الترجمة والـfallback بين اللغات.
- إضافة عقد مصادر رسمي يفرض أخذ كل نص من مصدر كنسي باللغة نفسها ويحافظ على Unicode حرفيًا.
- إضافة مستورد لمكتبات الكتاب المقدس الرسمية مع بصمة لكل آية ومنع النشر الجزئي للمقاطع.
- إضافة فهرس بحث مستقل يسمح بالبحث المرن دون تغيير النص المعروض.
- إزالة عرض العربية بدل الإنجليزية أو اليونانية عند غياب النص.
- تثبيت Workflowين فقط: تحديث 00:00 وتحقق 00:15 بتوقيت عمّان، وبناء مستقل للتطبيق.
- إضافة بوابة `validate_release_readiness.py` التي تمنع الإصدار الإنتاجي حتى اكتمال الحزم والمكتبات الأصلية للغات الثلاث.
- تدوير مفتاح توقيع البيانات، وإضافة فحص أسرار يمنع مفاتيح PEM وJKS وكلمات المرور من دخول المستودع.
- رفع مخطط بيانات اليوم إلى الإصدار 9 وإضافة اختبارات الخلط بين اللغات، البصمات، البحث، وعدم النشر الجزئي.
- تحديث التطبيق والوثائق إلى 3.5.0 مع إبقاء المحتوى غير المتوفر ظاهرًا بصدق بدل اختراعه أو ترجمته.
## 3.3.0 — بيانات آمنة متعددة اللغات وبنية يومية بلا تكرار

- تصحيح قراءات 14 يوليو 2026 إلى 1 كورنثوس 6:20–7:12 ومتى 14:1–13 بنص عربي مثبت ومشكول.
- حذف النصوص الإنجليزية واليونانية المنسوخة أو المكتوبة بالأبجدية الخطأ بدل عرضها بوصفها ترجمة رسمية.
- إضافة سياسة لغات صريحة: النص الأصلي المرخص أولًا، والترجمة البشرية المراجعة فقط عند الضرورة، وإظهار «غير متوفر» عند غياب مصدر موثق.
- تحويل خدمات اليوم إلى ملحقات صغيرة فوق مكتبة ثابتة واحدة، مع استبدالات محددة للرسالة والإنجيل والقطع المتغيرة.
- رفع مخطط البيانات إلى الإصدار 8 وإضافة تحقق للتراكبات والتكرار وحجم ملف اليوم.
- رفض بيانات المستقبل، ومعالجة أعطال التحديث غير المتوقعة، وتحديث الشاشة المفتوحة مع حفظ موضع القراءة.
- ترحيل المفضلة من CSV إلى `StringSet` آمن مع توافق رجعي.
- إضافة الكنيسة الأرثوذكسية في أمريكا كمرجع أرثوذكسي احتياطي بعد المصادر العربية واليونانية الرسمية.
- تدوير مفتاح توقيع بيانات اليوم وإنشاء مفتاح Android خارج المستودع، مع ملف أسرار منفصل لا يجوز رفعه إلى GitHub.
- جعل فحوص الإصدار صارمة وقابلة للتكرار، وتوسيع المجموعة إلى 54 اختبارًا آليًا.
- إضافة صفحة خصوصية ثابتة قابلة للنشر عبر GitHub Pages، ووثائق Google Play وGitHub Desktop للإصدار 3.3.0.

## 3.2.6 — سلامة الترجمات وتحصين النشر

- منع عرض أي ترجمة إنجليزية أو يونانية للكتاب المقدس ما لم تحمل مصدرًا مستقلًا وبصمة ومطابقة للمرجع.
- إضافة منقّي دفاعي يعمل بعد التحقق من التوقيع وقبل العرض لإخفاء حقول الترجمة القديمة غير الموثقة.
- تعديل مولّد البيانات كي يترك الترجمة غير المتوفرة فارغة بدل نسخ العربية أو الإنجليزية إلى لغة أخرى.
- إضافة بوابة صارمة تمنع إصدار بيانات قديمة أو ترجمة كتابية غير موثقة.
- جعل إصدار Android يستورد أحدث بيانات موقعة من فرع `verified-data` ويرفض البناء إذا لم تكن لتاريخ عمّان الحالي.
- التحقق من الفرع المنشور بعد الدفع وفتح تنبيه GitHub تلقائيًا عند فشل تحديث بيانات اليوم.
- إصلاح معاملة التخزين الذرية بحيث لا يشير `current.ref` إلى جيل محذوف عند فشل كتابة النسخة الاحتياطية.
- تركيب ملحقات الغروب والسحرية وصلوات المنزل فوق نص المكتبة الثابت بدل تكرار الخدمة كاملة يوميًا.
- استخدام `BuildConfig.VERSION_NAME` في User-Agent وتفعيل إشارة العودة إلى التطبيق في سياسة إعادة المحاولة.
- إضافة اختبارات أعطال التخزين، وتنقية الترجمات، وتركيب الخدمات، ورفع الإصدار إلى 3.2.6.

## 3.2.5 — إصلاح التحديث اليومي التلقائي

- تنظيف حزمة المصدر من ملفات التسليم والتقارير والكاش وسكربتات الترحيل القديمة.
- دمج البناء وCodeQL في Workflow واحد باسم `CI`، والإبقاء على ثلاثة Workflows فقط.
- إزالة Dependency Review الإجباري الذي كان يفشل عند تعطيل Dependency Graph، مع إبقاء Dependabot وCodeQL.
- جعل أسماء ملفات الإصدار تُشتق من رقم النسخة بدل تكرار الرقم داخل Workflows.
- توحيد وثائق الإعداد في `SETUP_AR.md` وتحديث الوثائق القديمة إلى 3.2.5.
- نشر البيانات الموقعة تلقائيًا إلى فرع `verified-data` عند 00:05 بتوقيت عمّان، مع إعادة محاولة تلقائية عند 00:35.
- تشغيل النشر فور وصول تعديل خط الأنابيب إلى `main`.
- توقيع ملف اليوم المختصر وملف التاريخ الصريح معًا.
- جعل التطبيق يجرب ملف التاريخ الصريح قبل `today.json` لتجاوز أي تأخير في تحديث الاسم المختصر.
- جدولة فحص صامت بعد منتصف الليل بتوقيت عمّان، مع WorkManager احتياطي كل 24 ساعة.
- عدم تنزيل أي شيء إذا كانت بيانات اليوم الموقعة موجودة وسليمة.

## 3.2.4 — إصلاح الصفحة البيضاء وفحص قارئ الصلوات والقداس

- إزالة طبقة الأدوات العائمة التي كانت تغطي `RecyclerView` وتحجز ارتفاعها كاملًا كحشوة علوية حتى بعد تحريكها.
- بناء القارئ بتخطيط رأسي ثابت: أدوات مدمجة، مقبض دائم، ومنطقة قراءة مستقلة تأخذ المساحة المتبقية.
- منع فتح صفحة بيضاء: أي خدمة بلا عنوان أو فقرات قابلة للعرض تُرفض وتظهر رسالة خطأ واضحة مع الرجوع إلى النسخة الموثوقة.
- التحقق من وجود الخدمات اليومية السبع ومنع خدمة ناقصة أو مكررة من استبدال البيانات المحلية السليمة.
- تصفير مواضع القراءة القديمة غير المتوافقة مرة واحدة، ثم حفظ رقم الفقرة والإزاحة الجديدة.
- طي الأدوات وإعادتها بحركة مستخدم مقصودة مع مسافة أمان، دون تحريك طبقة فوق النص أو حجز مساحة فارغة.
- إضافة اختبار Android فعلي على محاكي يفتح القداس الحالي وقداس الأحد القادم وصلاة الصباح، ويتأكد من وجود فقرات مرئية ومساحة قابلة للتمرير.
- إضافة فحص ثابت لـ598 فقرة في الخدمات اليومية، وبوابة تمنع أي نص فارغ من الوصول للقارئ.
- إضافة قسم «عن البرنامج» والاتصال بالرقم 00962788272988 ورابط سياسة الخصوصية.
- إضافة ملفات تجهيز Google Play وData safety ووصف المتجر وأصول أولية للأيقونة والصورة التعريفية.
- تحديث الإصدار إلى 3.2.4.

## 3.2.2 — مساحة قراءة أكبر وتفعيل آمن للغات الثلاث

- جعل عنوان القارئ وشريط الأدوات ومعلومات المصدر والتنقل بين أقسام القداس قابلة للطي تلقائيًا عند التمرير إلى أسفل.
- إعادة أدوات القراءة عند التمرير إلى أعلى أو الضغط على شريط الإظهار الصغير، مع إبقاء شريط التنقل السفلي ثابتًا.
- حفظ رقم الفقرة والإزاحة الدقيقة داخلها حتى لا يضيع موضع القراءة عند تغيير حجم الخط أو المفضلة أو إظهار المصدر.
- تفعيل العربية والإنجليزية واليونانية في الإعدادات دون تعطيل أي زر.
- ترجمة واجهة التطبيق والتنقل والإعدادات وحالات التحديث إلى اللغات الثلاث مع RTL للعربية وLTR للإنجليزية واليونانية.
- منع عرض العربية على أنها ترجمة إنجليزية أو يونانية؛ النص غير الموثق باللغة المختارة يظهر كغير متوفر مع خيار إظهار نص المصدر الرسمي.
- تحسين اختيار النص الأصلي بحيث لا يقبل حقولًا يونانية أو إنجليزية تحتوي نسخة عربية منسوخة.
- إضافة أسماء تطبيق مترجمة على مستوى موارد Android، واختبارات تمنع عودة تعطيل اللغات أو خلط النصوص.
- تحديث الإصدار إلى 3.2.2.

## 3.2.1 — إصلاح التحديث اليومي واستقرار موضع القراءة

- منع أي تحديث شبكي تلقائي ما دامت بيانات تاريخ اليوم الموقعة صالحة.
- تنفيذ التحديث التلقائي عند تغيّر يوم عمّان أو عند وجود بيانات قديمة/ناقصة فقط.
- تغيير WorkManager إلى فحص يومي كل 24 ساعة، مع تخطي الشبكة عندما تكون البيانات الحالية سليمة.
- إزالة فحص الدقيقة ومراقبة تغيّر الشبكة اللذين كانا يكرران التنزيل والرسائل.
- إضافة مراقب خفيف لموعد منتصف الليل بتوقيت عمّان بدل المؤقت المتكرر.
- المحافظة على موضع التمرير عند تحديث شاشة الأجندة أو الإعدادات.
- جعل حالة «جارٍ التحديث» محايدة اللون، وحصر اللون الأحمر في الخطأ الحقيقي.
- عدم إظهار شارة نجاح دائمة في الأجندة بعد اكتمال التحديث.
- تضمين إصلاح توافق أنماط أندرويد API 26/27/28 وصلاحية تنفيذ Gradle Wrapper.

## 3.2.0 — مصادر رسمية ونصوص كاملة موثقة حيث تتوفر

- فرض ترتيب المصادر: مطرانية الأردن، بطريركية القدس، بطريركية أنطاكية، ثم المصدر اليوناني الأرثوذكسي الرسمي.
- إضافة بوابة آلية مغلقة تمنع النشر عند قدم المصدر أو نقصه أو وجود نص تجريبي أو تعارض تقويمي.
- فصل مرجع القراءة الليتورجي عن نص الآيات؛ النصوص الكتابية مأخوذة حرفيًا من طبعة عربية مثبتة ومشكولة.
- التحقق من السفر والإصحاح وتسلسل أرقام الآيات وبصمات النص ونسبة الحركات ومطابقة الكلمات بعد إزالة التشكيل.
- منع الذكاء الاصطناعي من ترجمة أو إعادة صياغة أو تشكيل الكتاب المقدس والقطع الليتورجية للنشر.
- إضافة توافق صريح مع تقويم القدس القديم، ومنع مصدر التقويم الجديد من تجاوز عيد ثابت مقدسي.
- عرض البروكيمنن والقراءات والقطع المتاحة كاملة بدل عبارات «راجع الكنيسة» أو «راجع النص الكنسي».
- تثبيت الصلاة الربانية وقانون الإيمان والثلاثة تقديسات وصلوات المائدة كاملةً من سجلات مصدر مطرانية الأردن مع بصمات مستقلة.
- إعادة تسمية الأقسام الجزئية للغروب والسحرية حتى لا تُعرض خطأً كخدمات ليتورجية كاملة.
- تحويل الإرشادات الضرورية إلى ملاحظات اختيارية مغلقة افتراضيًا، ومنع استخدامها بدل نص مفقود.
- نشر البيانات اليومية الموقعة إلى فرع `verified-data` فقط بعد نجاح جميع الفحوص، مع إبقاء آخر نسخة سليمة عند الفشل.
- تحديث التطبيق لرفض أي بيانات لا تحمل حالة المصادر الرسمية والتشكيل الدقيق، وعرض المصدر المختار لليوم.
- تحديث الإصدار إلى 3.2.0.

## 3.1.0 — سلسلة ثقة وإصدار محمية

- إضافة توقيع RSA-3072 منفصل لبيانات اليوم والتحقق منه قبل قراءة JSON.
- حفظ البيانات الموقعة بأجيال ذرية مع آخر نسخة موثوقة بدل SharedPreferences.
- إنشاء Repository واحد ومنسق تحديث واحد وسياسة TTL قابلة للاختبار.
- منع التحديثات المتزامنة وطلبات WorkManager المكررة.
- تحويل التحديث اليومي من دفع مباشر إلى `main` إلى Pull Request للمراجعة البشرية.
- إضافة Release workflow موقع، R8، resource shrinking، APK/AAB، تحقق apksigner، وSHA-256.
- تثبيت GitHub Actions على commit SHA وإضافة CodeQL وDependency Review وDependabot.
- إضافة اختبارات JVM للتوقيع وسياسة التحديث واختبارات Python لرفض العبث وعقود الإصدار.
- عرض مصدر النسخة وبصمة المحتوى ومعرف المصدر الكتابي داخل الإعدادات.
- فصل ترخيص الكود عن حقوق النصوص والمحتوى، وإضافة سياسة خصوصية ودليل إعداد للمالك.
- تحديث الإصدار إلى 3.1.0.

## 3.0.4 — تحديث تلقائي عند عودة الإنترنت

- مراقبة اتصال أندرويد أثناء فتح التطبيق وتشغيل التحديث فور حصول الشبكة على اتصال إنترنت صالح.
- إضافة مهمة WorkManager فورية تنتظر الإنترنت إذا فُتح التطبيق دون اتصال، ثم تنزّل بيانات اليوم تلقائيًا عند عودته.
- إبقاء فحص دوري في الواجهة لإعادة المحاولة كل خمس دقائق عندما تكون بيانات اليوم قديمة، دون إغراق الخادم بالطلبات.
- إبقاء المهمة الدورية الاحتياطية، مع إضافة مهمة فورية مستقلة لا تنتظر موعدها عند غياب الإنترنت.
- جعل عامل الخلفية يتجاوز كاش GitHub ويعيد المحاولة عند أخطاء الشبكة أو عندما لم تُنشر بيانات اليوم بعد.
- تحديث الإصدار إلى 3.0.4.

## 3.0.3 — نسخة استعادة مستقرة

- اختصار GitHub Actions إلى Workflow للبناء وآخر لتحديث البيانات.
- إزالة اعتماد التحديث على مفاتيح Gemini والتوقيع الرقمي.
- منع فشل البناء بسبب كون بيانات Offline أقدم من تاريخ التشغيل.
- إبقاء التحقق الصارم من تاريخ اليوم داخل Workflow التحديث اليومي فقط.
- دعم مساحة شريط تنقل أندرويد قبل Android 11 وبعده.
- إصلاح التحديث التلقائي عند فتح التطبيق والعودة إليه.
- استخدام Android Gradle Plugin 8.7.3 وGradle 8.9 وJDK 17 وSDK 35.
- تحديث الإصدار إلى 3.0.3.

## 3.4.0 — 2026-07-14

- فصل المكتبات العربية واليونانية والإنجليزية إلى حزم أصلية مستقلة.
- تسجيل مصادر كل خدمة والموافقات والبصمات وحالة الاكتمال.
- تعطيل الترجمة الآلية ومنع تسرب الأبجديات بين اللغات.
- إضافة `install_authorized_native_pack.py` و`validate_native_language_packs.py` و`validate_daily_native_content.py`.
- تحديث عند تشغيل التطبيق، وجدول 00:00 و00:15 بتوقيت عمّان، ومحاولة احتياطية كل ست ساعات.
- جعل بوابة Release تتطلب `--require-native-complete`.
## 5.0.16 R20 — Religious integrity and true language isolation

- Strip ordinary and extended USFM word metadata without changing source words.
- Insert verified daily Prokeimenon, Epistle, and Gospel through stable semantic slots in Arabic, English, and Greek.
- Publish each signed daily lane with only its own localized text and source evidence.
- Remove cross-language metadata fallback from the church directory.
- Replace field-population percentages with a 15-service ecclesiastical completeness manifest.
- Block production releases until every required service is imported from an authorized complete native edition.
- Correct the Greek Cherubic Hymn character typo and remove misleading “complete” labels.

## R21 Phase 8 — controlled finalization

- Added paragraph-by-paragraph ecclesiastical review packets for native Basil and Presanctified candidates.
- Added exact Greek-English DCS source splitting without translation.
- Added hash-verified local Gradle Android build tooling and APK evidence generation.
- Added a truthful final completion gate covering native rites, annual propers, patristic commentary, official signing, and Android build proof.
- Protected 29 liturgical texts, contracts, and source-evidence files with static SHA-256 hashes.

## R21 Phase 9 — Daily annual audit and patristic commentary gate

- Added a deterministic offline audit for all 365 civil dates of 2026, with per-day blockers instead of an inferred annual-completeness percentage.
- Added a fail-closed patristic Gospel commentary registry, source registry, native-language candidate importer, and three-language review requirement.
- Added an optional `gospel_commentary` semantic slot after the Gospel response in Arabic, English, and Greek native Liturgy packs; it remains hidden unless all three reviewed native lanes are approved.
- Preserved the priest's homily as a separate liturgical action; the optional reading aid never replaces it.
- Registered Saint John Chrysostom, Homily 49 on Matthew, as source evidence for Matthew 14:14-22 without shipping an unreviewed quotation or AI-generated paraphrase.
- Added phase-nine validators to the main quality gate and protected the new contracts, registries, audit, and native packs with static hashes.

## R21 Phase 10 — Interpretation removal and dated coverage expansion

- Removed the patristic interpretation/commentary subsystem, its active contracts, importers, validators, native-reader slots, and stale phase-nine candidate artifacts.
- Preserved the post-Gospel liturgical response and the priest's homily position without adding an in-app explanation.
- Added a fail-closed dated proper for July 19, 2026 in the Jerusalem old-calendar lane: Tone 6, Eothinon 7, Matins John 20:1-10, Romans 15:1-7, and Matthew 9:27-35.
- Separated Paschal-cycle authority from fixed-date calendar context so a New Calendar commemoration is not copied into the Jerusalem Old Calendar lane.
- Removed USFM/Strong word attributes from display text while retaining the source words, with a regression test blocking technical markup in the reader.
- Rebuilt the 2026 offline annual audit: 365 dates audited, 3 currently complete, and 362 explicitly blocked rather than inferred complete.
- Kept the signed embedded July 26, 2026 release data unchanged; phase-ten candidates remain unsigned and marked do-not-publish.

### R30 branding Git tracking hotfix
- Keep generated `release/` outputs ignored while explicitly tracking canonical `release/branding/` assets.
- Mark `.ico` files as binary and add a regression test for Git ignore rules.
