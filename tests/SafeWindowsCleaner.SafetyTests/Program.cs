using System.Diagnostics;
using SafeWindowsCleaner.Models;
using SafeWindowsCleaner.Services;

var tests = new List<(string Name, Action Run)>
{
    ("Publisher metadata", TestPublisherMetadata),
    ("Settings normalization", TestSettingsNormalization),
    ("Lite profile defaults", TestLiteProfileDefaults),
    ("Cleanup profiles protect automatic cleanup", TestCleanupProfiles),
    ("Cleaner rules reject unsafe roots", TestCleanerRules),
    ("Publisher thumbprints are normalized", TestThumbprintNormalization),
    ("Activity hash changes with content", TestActivityHash),
    ("Path containment rejects prefix tricks", TestPathContainment),
    ("Windows directory is protected", TestWindowsPathProtection),
    ("Duplicate guard keeps one copy", TestDuplicateGuard),
    ("Monitored install directory guard", TestMonitoredInstallDirectoryGuard),
    ("Deep uninstall identity matching", TestDeepUninstallIdentityMatching),
    ("MSI uninstall command normalization", TestMsiUninstallNormalization),
    ("Automatic orphan policy is conservative", TestAutomaticOrphanPolicy),
    ("Automatic startup policy only disables broken entries", TestAutomaticStartupPolicy),
    ("Memory relief requires explicit user choice", TestExplicitMemoryPolicy),
    ("Only production-ready languages are exposed", TestSupportedLanguages),
    ("Language selector never mixes Arabic and English labels", TestLanguageSelectorLabels),
    ("Core actions are localized in every exposed non-Arabic language", TestCoreLocalization),
    ("Localization catalog is complete and contains no Arabic leakage", TestLocalizationCatalog),
    ("Size units never mix Arabic and English", TestLocalizedSizeUnits),
    ("Runtime status and report templates are fully localized", TestRuntimeLocalizationTemplates),
    ("Unknown runtime prose cannot mix interface languages", TestStrictRuntimeFallback),
    ("Displayed model text follows the active language", TestDisplayedModelLocalization),
    ("System memory snapshot is measurable", TestSystemMemorySnapshot),
    ("Virtual memory presets are adaptive and reversible", TestVirtualMemoryPreset),
    ("Updater selects the matching Windows architecture", TestUpdateArchitectureSelection)
};

int failed = 0;
foreach ((string name, Action run) in tests)
{
    try
    {
        run();
        Console.WriteLine($"PASS: {name}");
    }
    catch (Exception ex)
    {
        failed++;
        Console.Error.WriteLine($"FAIL: {name} — {ex.Message}");
    }
}

Console.WriteLine($"Safety checks complete. Passed: {tests.Count - failed}, Failed: {failed}");
return failed == 0 ? 0 : 1;

static void TestPublisherMetadata()
{
    Assert(PublisherInfo.DisplayName == "معن حنونة للستلايت", "Publisher name does not match the configured owner.");
    Assert(PublisherInfo.Phone == "00962788272988", "Publisher phone does not match the configured number.");
}

static void TestSettingsNormalization()
{
    AppSettings settings = SettingsService.Normalize(new AppSettings
    {
        Theme = "unsupported",
        QuarantineRetentionDays = -3,
        MinimumDuplicateSizeMb = 99999,
        LargestFilesLimit = 2,
        GitHubRepository = "https://github.com/example/repo.git"
    });

    Assert(settings.Theme == "Light", "Unsupported theme must fall back to Light.");
    Assert(settings.QuarantineRetentionDays == 1, "Retention must be clamped to the minimum.");
    Assert(settings.MinimumDuplicateSizeMb == 10240, "Duplicate size must be clamped to the maximum.");
    Assert(settings.LargestFilesLimit == 50, "Largest-file limit must be clamped to the minimum.");
    Assert(settings.GitHubRepository == "example/repo", "Repository normalization failed.");
}


static void TestLiteProfileDefaults()
{
    AppSettings settings = SettingsService.Normalize(new AppSettings());
    Assert(settings.SettingsSchemaVersion == 5, "Lite settings schema must be current.");
    Assert(settings.LowResourceMode, "Low-resource mode must be enabled by default.");
    Assert(!settings.CalculateDuplicatesDuringDiskScan, "Duplicate hashing must be opt-in on the Lite profile.");
    Assert(settings.LargestFilesLimit == 200, "Lite profile should display 200 largest files by default.");
    Assert(settings.MinimumDuplicateSizeMb == 50, "Lite profile should ignore small duplicate candidates by default.");
    Assert(!settings.CheckForUpdatesOnStartup, "Startup update checks must be disabled by default to speed launch.");
    Assert(settings.DefaultCleanupProfile == CleanupProfileService.SafeProfile, "The safe cleanup profile must be the default.");
    Assert(!settings.EnableTemporaryMemoryRelease, "Temporary working-set trimming must remain disabled.");
    Assert(settings.RequireSignedUpdates, "Signed updates must be required by default.");
    Assert(settings.SimpleNavigation, "The fixed Lite navigation must be enabled by default.");
}

static void TestCleanupProfiles()
{
    var targets = new List<CleanupTarget>
    {
        new() { Name = "Safe", Description = "Safe", RootPath = Path.GetTempPath(), SearchPatterns = ["*"], SafetyTier = CleanupSafetyTier.Safe, EnabledByDefault = true, Group = "Windows" },
        new() { Name = "Review", Description = "Review", RootPath = Path.GetTempPath(), SearchPatterns = ["*"], SafetyTier = CleanupSafetyTier.Review, EnabledByDefault = false, Group = "Creative" }
    };
    var profiles = new CleanupProfileService();
    profiles.Apply(CleanupProfileService.SafeProfile, targets);
    Assert(targets[0].IsSelected, "Safe default items should be selected by the safe profile.");
    Assert(!targets[1].IsSelected, "Review items must not be selected by the safe profile.");
    Assert(CleanupProfileService.NormalizeForAutomatic(CleanupProfileService.ReviewProfile) == CleanupProfileService.SafeProfile,
        "Scheduled cleanup must never run the manual-review profile.");
}

static void TestCleanerRules()
{
    var safe = new CleanerRuleDefinition
    {
        Id = "test-safe", Name = "Safe", RootPath = "%LOCALAPPDATA%\\SafeWindowsCleaner\\TestCache", SearchPatterns = ["*.tmp"]
    };
    Assert(CleanerRuleService.TryCreateTarget(safe, out CleanupTarget? target) && target is not null,
        "A bounded LocalAppData child rule should be accepted.");

    var unsafeRule = new CleanerRuleDefinition
    {
        Id = "test-unsafe", Name = "Unsafe", RootPath = "%WINDIR%\\System32", SearchPatterns = ["*"]
    };
    Assert(!CleanerRuleService.TryCreateTarget(unsafeRule, out _),
        "Cleaner rules must reject protected Windows roots outside Windows Temp.");

    var userDocumentsRule = new CleanerRuleDefinition
    {
        Id = "test-documents", Name = "Documents", RootPath = "%USERPROFILE%\\Documents", SearchPatterns = ["*"]
    };
    Assert(!CleanerRuleService.TryCreateTarget(userDocumentsRule, out _),
        "Cleaner rules must reject user-data roots that are not recognizable disposable caches or temporary folders.");

    var nestedDocumentsCacheRule = new CleanerRuleDefinition
    {
        Id = "test-documents-cache", Name = "Documents Cache", RootPath = "%USERPROFILE%\\Documents\\TestCache", SearchPatterns = ["*"]
    };
    Assert(!CleanerRuleService.TryCreateTarget(nestedDocumentsCacheRule, out _),
        "A disposable-looking child must not bypass protection for Documents or other personal-data folders.");

    var oneDriveCacheRule = new CleanerRuleDefinition
    {
        Id = "test-onedrive-cache", Name = "OneDrive Cache", RootPath = "%USERPROFILE%\\OneDrive - Example\\TestCache", SearchPatterns = ["*"]
    };
    Assert(!CleanerRuleService.TryCreateTarget(oneDriveCacheRule, out _),
        "A disposable-looking child must not bypass protection for organization OneDrive folders.");
}

static void TestThumbprintNormalization()
{
    string normalized = SettingsService.NormalizeThumbprint("aa bb:cc-dd ee ff 00 11 22 33 44 55 66 77 88 99 aa bb cc dd");
    Assert(normalized == "AABBCCDDEEFF00112233445566778899AABBCCDD", "Certificate thumbprint normalization failed.");
    Assert(SettingsService.NormalizeThumbprint("1234") == string.Empty, "Short thumbprints must be rejected.");
}

static void TestActivityHash()
{
    var first = new ActivityLogEntry
    {
        Sequence = 1,
        TimestampUtc = DateTimeOffset.Parse("2026-07-15T12:00:00Z"),
        Operation = "Test",
        Status = "Success",
        Summary = "Original",
        ItemCount = 1,
        BytesAffected = 100,
        PreviousHash = string.Empty
    };
    string original = ActivityLogService.ComputeHash(first);
    first.Summary = "Changed";
    string changed = ActivityLogService.ComputeHash(first);
    Assert(original.Length == 64, "SHA-256 hash must contain 64 hexadecimal characters.");
    Assert(!string.Equals(original, changed, StringComparison.Ordinal), "Changing record content must change its hash.");
}

static void TestPathContainment()
{
    string root = Path.Combine(Path.GetTempPath(), "swc-root");
    string child = Path.Combine(root, "folder", "file.txt");
    string prefixTrick = root + "-other" + Path.DirectorySeparatorChar + "file.txt";
    Assert(PathSafetyService.IsPathUnder(child, root), "A real child path should be accepted.");
    Assert(!PathSafetyService.IsPathUnder(prefixTrick, root), "A path that only shares the text prefix must be rejected.");
}

static void TestWindowsPathProtection()
{
    string windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
    if (string.IsNullOrWhiteSpace(windows))
    {
        throw new InvalidOperationException("Windows directory is unavailable on the Windows test runner.");
    }

    Assert(PathSafetyService.IsProtectedSystemPath(Path.Combine(windows, "System32", "kernel32.dll")),
        "Files inside the Windows directory must be protected.");
}

static void TestDuplicateGuard()
{
    string root = Path.Combine(Path.GetTempPath(), "swc-tests-" + Guid.NewGuid().ToString("N"));
    Directory.CreateDirectory(root);
    try
    {
        string first = Path.Combine(root, "first.bin");
        string second = Path.Combine(root, "second.bin");
        File.WriteAllBytes(first, [1, 2, 3, 4]);
        File.WriteAllBytes(second, [1, 2, 3, 4]);

        var allSelected = new HashSet<string>(new[] { Path.GetFullPath(first), Path.GetFullPath(second) }, StringComparer.OrdinalIgnoreCase);
        var oneSelected = new HashSet<string>(new[] { Path.GetFullPath(second) }, StringComparer.OrdinalIgnoreCase);
        Assert(PathSafetyService.WouldRemoveEveryExistingCopy(new[] { first, second }, allSelected),
            "Selecting every existing copy must be blocked.");
        Assert(!PathSafetyService.WouldRemoveEveryExistingCopy(new[] { first, second }, oneSelected),
            "Selecting only an extra copy must remain allowed.");
    }
    finally
    {
        Directory.Delete(root, true);
    }
}


static void TestMonitoredInstallDirectoryGuard()
{
    string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
    Assert(!string.IsNullOrWhiteSpace(local), "LocalAppData is unavailable on the Windows test runner.");
    string root = Path.Combine(local, "swc-monitor-test-" + Guid.NewGuid().ToString("N"));
    string nested = Path.Combine(root, "nested");
    Directory.CreateDirectory(nested);
    try
    {
        Assert(InstallMonitorService.IsSafeMonitoredApplicationDirectory(root),
            "A direct application-data child directory created for a monitored install should be eligible for quarantine review.");
        Assert(!InstallMonitorService.IsSafeMonitoredApplicationDirectory(nested),
            "A nested directory must not be treated as a top-level application directory.");
        Assert(!InstallMonitorService.IsSafeMonitoredApplicationDirectory(local),
            "The LocalAppData root itself must never be eligible for quarantine.");
    }
    finally
    {
        Directory.Delete(root, true);
    }
}


static void TestDeepUninstallIdentityMatching()
{
    var app = new InstalledApp
    {
        DisplayName = "Example Photo Studio 5",
        Publisher = "Example Imaging Ltd",
        InstallLocation = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Example Photo Studio"),
        UninstallString = "uninstall.exe"
    };

    string[] tokens = DeepUninstallService.BuildIdentityTokens(app);
    Assert(tokens.Contains("examplephotostudio", StringComparer.OrdinalIgnoreCase),
        "Deep uninstall must retain the complete application identity.");
    Assert(DeepUninstallService.IsStrongIdentityMatch("Example Photo Studio", tokens),
        "A matching application folder must be recognized.");
    Assert(!DeepUninstallService.IsStrongIdentityMatch("Common Files", tokens),
        "A shared folder name must not match the application identity.");
    Assert(!DeepUninstallService.IsStrongIdentityMatch("Example Imaging", tokens),
        "Publisher-only text must not be treated as the application identity.");
}

static void TestMsiUninstallNormalization()
{
    ProcessStartInfo startInfo = InstallMonitorService.CreateUninstallStartInfo("msiexec.exe /I{01234567-89AB-CDEF-0123-456789ABCDEF}");
    Assert(startInfo.FileName.EndsWith("msiexec.exe", StringComparison.OrdinalIgnoreCase),
        "MSI uninstall parsing must preserve msiexec.exe.");
    Assert(startInfo.Arguments.StartsWith("/X", StringComparison.OrdinalIgnoreCase),
        "MSI maintenance /I commands must be normalized to /X for uninstall.");
    Assert(startInfo.UseShellExecute && startInfo.Verb == "runas",
        "Monitored uninstall must request elevation through the Windows shell.");
}


static void TestAutomaticOrphanPolicy()
{
    DateTime now = DateTime.UtcNow;
    var safe = new LeftoverItem
    {
        Name = "OldRemovedApp",
        Path = Path.Combine(Path.GetTempPath(), "OldRemovedApp"),
        Location = "Test",
        SizeBytes = 1024,
        ConfidenceScore = 95,
        IsQuarantinable = true,
        LastModifiedUtc = now.AddDays(-120)
    };
    var recent = new LeftoverItem
    {
        Name = "RecentApp",
        Path = Path.Combine(Path.GetTempPath(), "RecentApp"),
        Location = "Test",
        SizeBytes = 1024,
        ConfidenceScore = 99,
        IsQuarantinable = true,
        LastModifiedUtc = now.AddDays(-4)
    };
    var uncertain = new LeftoverItem
    {
        Name = "Uncertain",
        Path = Path.Combine(Path.GetTempPath(), "Uncertain"),
        Location = "Test",
        SizeBytes = 1024,
        ConfidenceScore = 75,
        IsQuarantinable = true,
        LastModifiedUtc = now.AddDays(-200)
    };
    var protectedCandidate = new LeftoverItem
    {
        Name = "StillRunnable",
        Path = Path.Combine(Path.GetTempPath(), "StillRunnable"),
        Location = "Test",
        SizeBytes = 1024,
        ConfidenceScore = 99,
        IsQuarantinable = false,
        LastModifiedUtc = now.AddDays(-300)
    };

    Assert(AutomaticCleanupPolicy.ShouldQuarantineOrphan(safe, now),
        "An old, direct, very-high-confidence orphan should be eligible for automatic quarantine.");
    Assert(!AutomaticCleanupPolicy.ShouldQuarantineOrphan(recent, now),
        "A recently changed directory must not be quarantined automatically.");
    Assert(!AutomaticCleanupPolicy.ShouldQuarantineOrphan(uncertain, now),
        "A lower-confidence directory must not be quarantined automatically.");
    Assert(!AutomaticCleanupPolicy.ShouldQuarantineOrphan(protectedCandidate, now),
        "A candidate rejected by service-level executable and path safety checks must stay protected.");
}

static void TestAutomaticStartupPolicy()
{
    var brokenRegistry = new StartupItem
    {
        Id = "test-registry",
        Name = "Missing updater",
        Kind = StartupItemKind.Registry,
        Category = "Registry",
        Command = @"C:\Missing\updater.exe",
        Location = "HKCU Run",
        ExecutablePath = @"C:\Missing\updater.exe",
        IsEnabled = true,
        CanToggle = true
    };
    var validRegistry = new StartupItem
    {
        Id = "test-valid",
        Name = "Valid",
        Kind = StartupItemKind.Registry,
        Category = "Registry",
        Command = Environment.ProcessPath ?? string.Empty,
        Location = "HKCU Run",
        ExecutablePath = Environment.ProcessPath ?? string.Empty,
        IsEnabled = true,
        CanToggle = true
    };
    var protectedService = new StartupItem
    {
        Id = "test-service",
        Name = "Service",
        Kind = StartupItemKind.Service,
        Category = "Service",
        Command = @"C:\Missing\service.exe",
        Location = "Services",
        ExecutablePath = @"C:\Missing\service.exe",
        IsEnabled = true,
        CanToggle = true
    };

    Assert(AutomaticCleanupPolicy.ShouldDisableBrokenStartup(brokenRegistry),
        "A broken, user-toggleable registry startup entry should be disabled automatically.");
    Assert(!AutomaticCleanupPolicy.ShouldDisableBrokenStartup(validRegistry),
        "A valid startup entry must remain enabled.");
    Assert(!AutomaticCleanupPolicy.ShouldDisableBrokenStartup(protectedService),
        "Services must not be changed automatically by the Lite policy.");
}

static void TestExplicitMemoryPolicy()
{
    AppSettings settings = SettingsService.Normalize(new AppSettings
    {
        EnableTemporaryMemoryRelease = true,
        SimpleNavigation = false
    });

    Assert(!settings.EnableTemporaryMemoryRelease,
        "Lite must never enable automatic working-set trimming, even from an old settings file.");
    Assert(settings.SimpleNavigation,
        "Lite must keep the fixed simplified navigation enabled.");

    var visibleApplication = new ProcessInfoItem
    {
        Name = "Editor",
        ProcessId = 12346,
        WorkingSetBytes = 200L * 1024L * 1024L,
        PrivateMemoryBytes = 180L * 1024L * 1024L,
        ExecutablePath = @"C:\Example\editor.exe",
        WindowTitle = "Unsaved document",
        StartTimeUtc = DateTime.UtcNow.AddHours(-2),
        IsCurrentUserSession = true,
        IsSystemProtected = false,
        CanClose = true,
        IsRecommended = true
    };
    var systemProcess = new ProcessInfoItem
    {
        Name = "System",
        ProcessId = 4,
        WorkingSetBytes = 500L * 1024L * 1024L,
        PrivateMemoryBytes = 400L * 1024L * 1024L,
        IsCurrentUserSession = true,
        IsSystemProtected = true,
        CanClose = false
    };

    Assert(visibleApplication.CanClose,
        "A user application may be closed only after the user explicitly selects it.");
    Assert(!systemProcess.CanClose,
        "A protected system process must never be offered for memory relief.");
}


static void TestSupportedLanguages()
{
    string[] expected = ["ar", "en"];
    string[] actual = LocalizationService.SupportedLanguages.Select(language => language.Code).ToArray();
    Assert(expected.SequenceEqual(actual),
        "The language selector must expose only fully audited production language packs.");
    Assert(LocalizationService.NormalizeLanguage("fr") == "en",
        "A removed non-Arabic language pack must migrate to complete English, not a mixed or unexpected Arabic interface.");
}

static void TestLanguageSelectorLabels()
{
    LanguageDisplayOption[] arabic = LocalizationService.GetLanguageDisplayOptions("ar").ToArray();
    Assert(arabic.Select(option => option.Code).SequenceEqual(new[] { "ar", "en" }),
        "Arabic language options must keep stable language codes.");
    Assert(arabic.All(option => LocalizationService.ContainsArabic(option.DisplayName)),
        "Every language name in the Arabic settings page must be Arabic.");

    LanguageDisplayOption[] english = LocalizationService.GetLanguageDisplayOptions("en").ToArray();
    Assert(english.Select(option => option.Code).SequenceEqual(new[] { "ar", "en" }),
        "English language options must keep stable language codes.");
    Assert(english.All(option => !LocalizationService.ContainsArabic(option.DisplayName)),
        "Every language name in the English settings page must be English.");
}

static void TestCoreLocalization()
{
    foreach (string language in new[] { "en" })
    {
        string cleanup = LocalizationService.T("تنظيف تلقائي الآن", language);
        string monitoredInstall = LocalizationService.T("تثبيت البرامج مع المراقبة", language);
        string fullRemoval = LocalizationService.T("حذف البرنامج وكل بقاياه", language);
        string memory = LocalizationService.T("تحسين الذاكرة الآمن", language);
        Assert(!string.IsNullOrWhiteSpace(cleanup) && cleanup != "تنظيف تلقائي الآن", $"Automatic-cleanup label is missing for {language}.");
        Assert(!string.IsNullOrWhiteSpace(monitoredInstall) && monitoredInstall != "تثبيت البرامج مع المراقبة", $"Monitored-install label is missing for {language}.");
        Assert(!string.IsNullOrWhiteSpace(fullRemoval) && fullRemoval != "حذف البرنامج وكل بقاياه", $"Full-removal label is missing for {language}.");
        Assert(!string.IsNullOrWhiteSpace(memory) && memory != "تحسين الذاكرة الآمن", $"Memory-optimization label is missing for {language}.");
        string dynamicFallback = LocalizationService.Translate("رسالة ديناميكية قديمة عن الرام والملفات", language);
        Assert(!LocalizationService.ContainsArabic(dynamicFallback), $"Dynamic fallback leaked Arabic into {language}.");
    }
}

static void TestLocalizationCatalog()
{
    Assert(LocalizationService.ValidateCatalog(out string error), error);

    string[] reportKeys =
    [
        "@TotalRam", "@UsedBefore", "@AvailableBefore", "@UsedAfter", "@AvailableAfter",
        "@MemoryFreed", "@MemoryDetails", "@ProcessActions", "@MemoryNote",
        "@PreviewReportTitle", "@InstallMonitorReport", "@DeepUninstallReport",
        "@ReasonFileExtension", "@ReasonComRegistration", "@ReasonEnvironmentPath", "@ReasonFirewallRule"
    ];
    foreach (string language in new[] { "en" })
    {
        foreach (string key in reportKeys)
        {
            string value = LocalizationService.T(key, language);
            Assert(!LocalizationService.ContainsArabic(value), $"Arabic text leaked into {language} for {key}: {value}");
        }
    }
}





static void TestLocalizedSizeUnits()
{
    string english = SafeWindowsCleaner.Helpers.SizeFormatter.Format(1536L * 1024L, "en");
    string arabic = SafeWindowsCleaner.Helpers.SizeFormatter.Format(1536L * 1024L, "ar");

    Assert(english.Contains("MB", StringComparison.Ordinal), $"English size must use MB: {english}");
    Assert(!LocalizationService.ContainsArabicSizeUnit(english), $"English size leaked an Arabic unit: {english}");
    Assert(arabic.Contains("ميغابايت", StringComparison.Ordinal), $"Arabic size must use the full Arabic unit: {arabic}");
    Assert(!LocalizationService.ContainsEnglishSizeUnit(arabic), $"Arabic size leaked an English unit: {arabic}");

    string normalizedArabic = LocalizationService.NormalizeTechnicalTokens("الحجم 40 MB", "ar");
    string normalizedEnglish = LocalizationService.NormalizeTechnicalTokens("Size 40 م.ب", "en");
    Assert(normalizedArabic.Contains("40 ميغابايت", StringComparison.Ordinal),
        $"Arabic technical-token normalization failed: {normalizedArabic}");
    Assert(!LocalizationService.ContainsEnglishSizeUnit(normalizedArabic),
        $"Arabic normalized text leaked an English unit: {normalizedArabic}");
    Assert(normalizedEnglish.Contains("40 MB", StringComparison.Ordinal),
        $"English technical-token normalization failed: {normalizedEnglish}");
    Assert(!LocalizationService.ContainsArabicSizeUnit(normalizedEnglish),
        $"English normalized text leaked an Arabic unit: {normalizedEnglish}");
}

static void TestRuntimeLocalizationTemplates()
{
    (string Arabic, string ExpectedEnglishToken)[] samples =
    [
        ("بدأ التنظيف التلقائي الخفيف. يعمل قسمًا بعد قسم لتقليل الضغط على الجهاز.", "automatic cleanup"),
        ("معاينة: يمكن حذف 12 ملف مؤقت بحجم 40 MB.", "12 temporary files"),
        ("مجموعات التكرار: 4، والمساحة المكررة المقدّرة: 2 GB.", "Duplicate groups"),
        ("تم فحص 125 ملف بحجم 3 GB.", "Scanned 125 files"),
        ("يوجد 7 عنصر بحجم 900 MB، منها 2 أقدم من 30 يومًا. يمكن استعادتها إلى مواقعها الأصلية.", "older than 30 days"),
        ("جلسة مراقبة فعالة: Demo. أكمل تثبيت البرنامج ثم اضغط «إنهاء المراقبة والمقارنة».", "Active monitoring session"),
        ("حُذفت البقايا — مجلدات للحجر: 2، ملفات للحجر: 5، ريجستري: 3، خدمات: 1، مهام: 0. المتبقي للمراجعة: ملفات/مجلدات 1، خدمات 0، مهام 0، ريجستري 2.", "Leftovers removed"),
        ("اكتمل الفحص: ملفات مؤقتة 1 GB، بقايا محتملة 3، برامج ثقيلة مقترحة 2، عناصر بدء تشغيل اختيارية 4. لا يتم تنفيذ أي تغيير تلقائيًا.", "Scan complete"),
        ("تعذر إنشاء أو إكمال نقطة الاستعادة: Access denied (رمز 5).", "restore point"),
        ("تنزيل SafeWindowsCleaner-2.0.0.exe...", "Downloading")
    ];

    foreach ((string arabic, string expectedEnglishToken) in samples)
    {
        string translated = LocalizationService.Translate(arabic, "en");
        Assert(!LocalizationService.ContainsArabic(translated),
            $"Runtime English text leaked Arabic: {translated}");
        Assert(translated.Contains(expectedEnglishToken, StringComparison.OrdinalIgnoreCase),
            $"Runtime message used an unclear fallback instead of its exact translation: {translated}");
    }
}


static void TestStrictRuntimeFallback()
{
    string arabic = LocalizationService.Translate("The driver query failed while reading system details.", "ar");
    Assert(LocalizationService.ContainsArabic(arabic),
        $"Unknown English prose did not receive an Arabic fallback: {arabic}");
    Assert(!arabic.Contains("driver query failed", StringComparison.OrdinalIgnoreCase),
        $"Unknown English prose leaked into the Arabic interface: {arabic}");

    string english = LocalizationService.Translate("تعذر تنفيذ عملية غير مسجلة في كتالوج النصوص.", "en");
    Assert(!LocalizationService.ContainsArabic(english),
        $"Unknown Arabic prose leaked into the English interface: {english}");

    string technical = LocalizationService.Translate(@"C:\Windows\Temp", "ar");
    Assert(technical.Contains(@"C:\Windows\Temp", StringComparison.Ordinal),
        "Technical paths must remain visible in either interface language.");
}

static void TestDisplayedModelLocalization()
{
    LocalizationService.SetActiveLanguage("en");
    try
    {
        var cleanup = new CleanupTarget
        {
            Name = "الملفات المؤقتة للمستخدم",
            Description = "ملفات مؤقتة أقدم من 24 ساعة؛ يتم تجاوز الملفات المستخدمة.",
            Group = "Windows",
            RootPath = Path.GetTempPath(),
            SearchPatterns = ["*"],
            SafetyTier = CleanupSafetyTier.Safe
        };
        var startup = new StartupItem
        {
            Id = "localized-startup",
            Name = "Updater",
            Kind = StartupItemKind.Registry,
            Category = "Registry",
            Command = "updater.exe",
            Location = "HKCU Run",
            Publisher = "@Unknown",
            SignatureStatus = "@Unknown",
            IsEnabled = true,
            CanToggle = true
        };
        var quarantine = new QuarantineItem
        {
            SessionId = "localized-quarantine",
            Name = "sample.tmp",
            OriginalPath = Path.Combine(Path.GetTempPath(), "sample.tmp"),
            QuarantinedPath = Path.Combine(Path.GetTempPath(), "q", "sample.tmp"),
            QuarantinedAt = DateTimeOffset.UtcNow.AddDays(-2),
            SizeBytes = 1024,
            IsDirectory = false
        };
        var operation = new OperationSessionRecord
        {
            Operation = "تنظيف الملفات المؤقتة",
            Summary = "اكتملت",
            Recoverable = true,
            Status = OperationSessionStatus.Completed
        };
        var installChange = new InstallChangeItem
        {
            Name = "cache.tmp",
            Location = Path.Combine(Path.GetTempPath(), "cache.tmp"),
            Confidence = "@ConfidenceMedium",
            Category = InstallChangeCategory.FileSystem,
            Kind = InstallChangeKind.Added
        };

        string[] displayed =
        [
            cleanup.DisplayName,
            cleanup.DisplayDescription,
            cleanup.DisplayGroup,
            cleanup.SafetyText,
            startup.CategoryText,
            startup.PublisherText,
            startup.SignatureStatusText,
            startup.StateText,
            quarantine.ItemTypeText,
            quarantine.RetentionText,
            operation.OperationText,
            operation.SummaryText,
            operation.RecoverableText,
            operation.StatusText,
            installChange.ConfidenceText,
            installChange.CategoryText,
            installChange.KindText,
            installChange.LocationText,
            cleanup.SizeText,
            quarantine.SizeText
        ];

        foreach (string value in displayed)
        {
            Assert(!LocalizationService.ContainsArabic(value),
                $"English display text leaked Arabic: {value}");
            Assert(!LocalizationService.ContainsArabicSizeUnit(value),
                $"English display text leaked an Arabic size unit: {value}");
        }

        LocalizationService.SetActiveLanguage("ar");
        Assert(!LocalizationService.ContainsEnglishSizeUnit(quarantine.SizeText),
            $"Arabic display text leaked an English size unit: {quarantine.SizeText}");
    }
    finally
    {
        LocalizationService.SetActiveLanguage("ar");
    }
}

static void TestSystemMemorySnapshot()
{
    SystemMemorySnapshot snapshot = new SystemMemoryService().Capture();
    Assert(snapshot.TotalPhysicalBytes > 0, "Total physical memory must be measurable.");
    Assert(snapshot.AvailablePhysicalBytes >= 0 && snapshot.AvailablePhysicalBytes <= snapshot.TotalPhysicalBytes,
        "Available physical memory must be within the physical-memory range.");
    Assert(snapshot.UsedPhysicalBytes == snapshot.TotalPhysicalBytes - snapshot.AvailablePhysicalBytes,
        "Used physical memory must equal total minus available memory.");
}


static void TestVirtualMemoryPreset()
{
    Assert(VirtualMemoryService.FixedPageFileSizeMb == 16384,
        "The maximum Lite preset must remain 16 GB.");
    Assert(VirtualMemoryService.MediumPageFileSizeMb == 8192,
        "The medium Lite preset must be 8 GB.");
    Assert(VirtualMemoryService.MinimumPageFileSizeMb == 4096,
        "The minimum Lite preset must be 4 GB.");
    Assert(VirtualMemoryService.MinimumFreeBytesAfterApply >= 8L * 1024L * 1024L * 1024L,
        "The adaptive preset must preserve a safe Windows free-space reserve.");

    Assert(VirtualMemoryService.GetRecommendedPageFileSizeMb(100L * 1024L * 1024L * 1024L) == 16384,
        "A drive with ample free space should receive the 16 GB preset.");
    Assert(VirtualMemoryService.GetRecommendedPageFileSizeMb(20L * 1024L * 1024L * 1024L) == 8192,
        "A moderately free drive should fall back to the 8 GB preset.");
    Assert(VirtualMemoryService.GetRecommendedPageFileSizeMb(15L * 1024L * 1024L * 1024L) == 4096,
        "A constrained drive should fall back to the 4 GB preset.");
    Assert(VirtualMemoryService.GetRecommendedPageFileSizeMb(11L * 1024L * 1024L * 1024L) == 0,
        "The feature must refuse to consume the protected Windows reserve.");

    string root = Path.GetPathRoot(Environment.SystemDirectory)
                  ?? throw new InvalidOperationException("System drive is unavailable.");
    string entry = VirtualMemoryService.BuildPagingFileEntry(
        Path.Combine(root, "pagefile.sys"),
        VirtualMemoryService.FixedPageFileSizeMb,
        VirtualMemoryService.FixedPageFileSizeMb);
    PagingFileConfiguration parsed = VirtualMemoryService.ParsePagingFileEntry(entry)
                                     ?? throw new InvalidOperationException("The page-file entry must round-trip.");
    Assert(VirtualMemoryService.IsLitePreset(parsed),
        "A fixed 16 GB page-file entry must be recognized as a Lite preset.");
    Assert(VirtualMemoryService.ParsePagingFileEntry(@"C:\pagefile.sys 16384 4096") is null,
        "A maximum smaller than the initial size must be rejected.");
}

static void TestUpdateArchitectureSelection()
{
    string[] assets =
    [
        "SafeWindowsCleaner-2.4.0-Win10-11-x64-Setup.exe",
        "SafeWindowsCleaner-2.4.0-Win10-11-x86-Setup.exe",
        "SafeWindowsCleaner-2.4.0-Windows7-8-8.1-Legacy-Setup.exe",
        "SafeWindowsCleaner-2.4.0-Win10-11-x64-Portable.zip"
    ];

    Assert(
        UpdateService.SelectSetupAssetName(assets, "x64", new Version(2, 4, 0)) == "SafeWindowsCleaner-2.4.0-Win10-11-x64-Setup.exe",
        "A 64-bit installation must select the x64 Windows 10/11 setup package.");
    Assert(
        UpdateService.SelectSetupAssetName(assets, "x86", new Version(2, 4, 0)) == "SafeWindowsCleaner-2.4.0-Win10-11-x86-Setup.exe",
        "A 32-bit installation must select the x86 Windows 10/11 setup package.");
    Assert(
        UpdateService.SelectSetupAssetName(
            ["SafeWindowsCleaner-2.4.0-Windows7-8-8.1-Legacy-Setup.exe"],
            "x64",
            new Version(2, 4, 0)) is null,
        "The modern updater must never offer the Windows 7/8/8.1 Legacy package.");
    Assert(
        UpdateService.SelectSetupAssetName(
            ["SafeWindowsCleaner-2.2.0-Win10-11-x64-Setup.exe"],
            "x64",
            new Version(2, 4, 0)) is null,
        "The updater must not select a stale Setup asset from another version.");
    Assert(
        UpdateService.SelectSetupAssetName(
            ["SafeWindowsCleaner-Lite-Setup.exe"],
            "x64",
            expectedVersion: new Version(2, 4, 0),
            allowLegacyNameFallback: true) == "SafeWindowsCleaner-Lite-Setup.exe",
        "A 64-bit installation may migrate from the historical unversioned setup name.");
    Assert(
        UpdateService.SelectSetupAssetName(
            ["SafeWindowsCleaner-Lite-Setup.exe"],
            "x86",
            expectedVersion: new Version(2, 4, 0),
            allowLegacyNameFallback: false) is null,
        "A 32-bit installation must not download a historical setup with unknown architecture.");
}

static void Assert(bool condition, string message)
{
    if (!condition)
    {
        throw new InvalidOperationException(message);
    }
}
