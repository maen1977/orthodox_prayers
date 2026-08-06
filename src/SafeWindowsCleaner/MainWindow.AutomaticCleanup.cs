using System.Diagnostics;
using System.Windows;
using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Models;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner;

public partial class MainWindow
{
    private readonly AutomaticCleanupReportService _automaticCleanupReportService = new();
    private CancellationTokenSource? _automaticCleanupCancellation;
    private string _latestAutomaticReportPath = string.Empty;

    private async void RunAutomaticCleanup_Click(object sender, RoutedEventArgs e)
    {
        if (_automaticCleanupCancellation is not null)
        {
            ShowLocalizedMessage("التنظيف التلقائي يعمل حاليًا.", "التنظيف التلقائي", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        if (!_settings.PreviewOnlyMode && !ElevationService.IsAdministrator)
        {
            MessageBoxResult elevationChoice = ShowLocalizedMessage(
                "التنظيف التلقائي قد يحتاج تنظيف Windows Temp وإنشاء نقطة استعادة وإصلاح بدء التشغيل. ستُفتح نسخة بصلاحية مسؤول فقط بعد اختيارك بدء العملية. هل تريد المتابعة؟",
                "صلاحية مسؤول عند الطلب",
                MessageBoxButton.YesNo,
                MessageBoxImage.Information);
            if (elevationChoice == MessageBoxResult.Yes && ElevationService.TryRelaunchElevated(nameof(AutomaticCleanupTab)))
            {
                Close();
            }
            return;
        }

        MessageBoxResult confirmation = ShowLocalizedMessage(
            "سيبدأ البرنامج تنظيفًا آمنًا ومتتابعًا للملفات المؤقتة والكاش، ثم ينقل بقايا البرامج المؤكدة إلى الحجر ويعالج عناصر بدء التشغيل المكسورة. لن يُغلق أي برنامج ولن ينفذ أي عملية وهمية لتنظيف الرام. هل تريد البدء؟",
            "بدء التنظيف التلقائي",
            MessageBoxButton.YesNo,
            MessageBoxImage.Information);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        _automaticCleanupCancellation = new CancellationTokenSource();
        AutomaticCleanupStartButton.IsEnabled = false;
        AutomaticCleanupCancelButton.IsEnabled = true;
        AutomaticCleanupOpenReportButton.IsEnabled = false;
        AutomaticCleanupProgressBar.Value = 0;
        AutomaticCleanupSummaryText.Text = L("بدأ التنظيف التلقائي الخفيف. يعمل قسمًا بعد قسم لتقليل الضغط على الجهاز.");
        SetAutomaticCleanupUi(isRunning: true);

        var result = new AutomaticCleanupResult
        {
            StartedAt = DateTimeOffset.UtcNow,
            PreviewOnly = _settings.PreviewOnlyMode,
            LanguageCode = _settings.LanguageCode
        };

        RestorePointSession? restorePointSession = null;
        try
        {
            SetBusy(true, "فحص الكاش والملفات المؤقتة...", disableTabs: false);
            CancellationToken token = _automaticCleanupCancellation.Token;

            UpdateAutomaticProgress(8, "فحص الكاش والملفات المؤقتة...");
            List<CleanupTarget> cleanupTargets = await _cleanupService.ScanAsync(CreateProgress(), token);
            ReplaceCollection(CleanupTargets, cleanupTargets);
            long cleanupPotential = cleanupTargets.Sum(item => item.SizeBytes);
            int cleanupPotentialFiles = cleanupTargets.Sum(item => item.FileCount);

            if (result.PreviewOnly)
            {
                result.Actions.Add($"معاينة: يمكن حذف {cleanupPotentialFiles:N0} ملف مؤقت بحجم {SizeFormatter.Format(cleanupPotential, _settings.LanguageCode)}.");
            }
            else
            {
                UpdateAutomaticProgress(18, "تنظيف الكاش والملفات المؤقتة...");
                CleanupResult cleanupResult = await _cleanupService.CleanAsync(cleanupTargets, CreateProgress(), token);
                result.TemporaryDeletedFiles = cleanupResult.DeletedFiles;
                result.TemporaryFailedFiles = cleanupResult.FailedFiles;
                result.TemporaryFreedBytes = cleanupResult.FreedBytes;
                result.Actions.Add($"حذف {cleanupResult.DeletedFiles:N0} ملف مؤقت وتوفير {SizeFormatter.Format(cleanupResult.FreedBytes, _settings.LanguageCode)}.");
                if (cleanupResult.FailedFiles > 0)
                {
                    result.Warnings.Add($"تعذر حذف {cleanupResult.FailedFiles:N0} ملف مؤقت لأنه مستخدم أو محمي.");
                }
            }

            UpdateAutomaticProgress(30, "قراءة البرامج المثبتة...");
            List<InstalledApp> installedApps = await _installedAppsService.GetInstalledAppsAsync(token);
            ReplaceCollection(InstalledApps, installedApps);

            UpdateAutomaticProgress(38, "البحث عن بقايا البرامج المحذوفة...");
            List<LeftoverItem> orphanItems = await _leftoverService.SearchOrphanedProgramsAsync(
                installedApps,
                CreateProgress(),
                token);
            ReplaceCollection(Leftovers, orphanItems);
            result.OrphanCandidatesFound = orphanItems.Count;

            List<LeftoverItem> automaticOrphans = orphanItems
                .Where(item => AutomaticCleanupPolicy.ShouldQuarantineOrphan(item, DateTime.UtcNow))
                .ToList();
            foreach (LeftoverItem item in automaticOrphans)
            {
                item.IsSelected = true;
            }

            result.OrphansSkipped = Math.Max(0, orphanItems.Count - automaticOrphans.Count);
            foreach (LeftoverItem skipped in orphanItems.Where(item => !automaticOrphans.Contains(item)).Take(80))
            {
                result.SkippedItems.Add($"بقايا لم تُنقل للحماية: {skipped.Path} — الثقة {skipped.ConfidenceScore}%.");
            }

            if (result.PreviewOnly)
            {
                long orphanPotential = automaticOrphans.Sum(item => item.SizeBytes);
                result.Actions.Add($"معاينة: يمكن نقل {automaticOrphans.Count:N0} بقايا عالية الثقة إلى الحجر بحجم {SizeFormatter.Format(orphanPotential, _settings.LanguageCode)}.");
            }
            else if (automaticOrphans.Count > 0)
            {
                UpdateAutomaticProgress(50, "نقل بقايا البرامج المؤكدة إلى الحجر...");
                QuarantineOperationResult quarantine = await _quarantineService.QuarantineAsync(
                    automaticOrphans,
                    CreateProgress(),
                    token);
                result.OrphansQuarantined = quarantine.SucceededItems;
                result.OrphansFailed = quarantine.FailedItems;
                result.OrphansSkipped += quarantine.SkippedItems;
                result.OrphanBytesQuarantined = quarantine.BytesProcessed;
                result.Actions.Add($"نقل {quarantine.SucceededItems:N0} بقايا برنامج إلى الحجر القابل للاستعادة.");
                if (quarantine.FailedItems > 0)
                {
                    result.Warnings.Add($"تعذر نقل {quarantine.FailedItems:N0} بقايا إلى الحجر.");
                }

                await LoadQuarantineItemsAsync();
            }

            UpdateAutomaticProgress(60, "فحص الريجستري وعناصر بدء التشغيل المكسورة...");
            List<StartupItem> startupItems = await _startupManagerService.GetStartupItemsAsync(CreateProgress());
            token.ThrowIfCancellationRequested();
            ReplaceCollection(StartupItems, startupItems);
            List<StartupItem> brokenItems = startupItems
                .Where(AutomaticCleanupPolicy.ShouldDisableBrokenStartup)
                .ToList();
            result.BrokenRegistryEntriesFound = brokenItems.Count(item => item.Kind == StartupItemKind.Registry);
            result.BrokenStartupItemsFound = brokenItems.Count(item => item.Kind != StartupItemKind.Registry);

            if (result.PreviewOnly)
            {
                result.Actions.Add($"معاينة: يمكن تعطيل {brokenItems.Count:N0} عنصر بدء تشغيل مكسور مع حفظ بيانات الاستعادة.");
            }
            else if (brokenItems.Count > 0)
            {
                result.RestorePointAttempted = _settings.CreateRestorePointBeforeDeepChanges;
                bool canChangeStartup = true;
                if (_settings.CreateRestorePointBeforeDeepChanges)
                {
                    RestorePointSessionResult restoreResult = await _restorePointService.BeginAsync(
                        "Safe Windows Cleaner - Before Automatic Cleanup");
                    result.RestorePointCreated = restoreResult.Succeeded;
                    result.RestorePointMessage = restoreResult.Message;
                    restorePointSession = restoreResult.Session;
                    result.RestorePointSequence = restoreResult.Session?.SequenceNumber ?? 0;
                    if (!restoreResult.Succeeded)
                    {
                        canChangeStartup = false;
                        result.Warnings.Add("تعذر إنشاء نقطة استعادة؛ لذلك تم تجاوز تغييرات الريجستري وبدء التشغيل تلقائيًا.");
                    }
                }
                else
                {
                    result.RestorePointMessage = "إنشاء نقطة الاستعادة معطل من الإعدادات؛ تم تجاوز تغييرات الريجستري التلقائية للحماية.";
                    canChangeStartup = false;
                }

                if (canChangeStartup)
                {
                    UpdateAutomaticProgress(68, "تعطيل عناصر بدء التشغيل المكسورة بأمان...");
                    List<StartupItem> brokenRegistry = brokenItems
                        .Where(item => item.Kind == StartupItemKind.Registry)
                        .ToList();
                    List<StartupItem> brokenOtherStartup = brokenItems
                        .Where(item => item.Kind != StartupItemKind.Registry)
                        .ToList();

                    StartupOperationResult registryResult = brokenRegistry.Count == 0
                        ? new StartupOperationResult()
                        : await _startupManagerService.DisableAsync(brokenRegistry, CreateProgress());
                    StartupOperationResult otherResult = brokenOtherStartup.Count == 0
                        ? new StartupOperationResult()
                        : await _startupManagerService.DisableAsync(brokenOtherStartup, CreateProgress());

                    result.BrokenRegistryEntriesDisabled = registryResult.SucceededItems;
                    result.BrokenStartupItemsDisabled = otherResult.SucceededItems;
                    result.StartupItemsFailed = registryResult.FailedItems + otherResult.FailedItems;
                    int disabledTotal = registryResult.SucceededItems + otherResult.SucceededItems;
                    result.Actions.Add($"تعطيل {disabledTotal:N0} عنصر ريجستري أو بدء تشغيل مكسور مع حفظ إمكانية الاستعادة.");
                    if (result.StartupItemsFailed > 0)
                    {
                        result.Warnings.Add($"تعذر تعطيل {result.StartupItemsFailed:N0} عنصر بدء تشغيل.");
                    }
                }
                else
                {
                    foreach (StartupItem item in brokenItems.Take(80))
                    {
                        result.SkippedItems.Add($"عنصر ريجستري/بدء تشغيل تم تجاوزه: {item.Name} — {item.Location}.");
                    }
                }
            }

            if (restorePointSession is not null)
            {
                RestorePointCompletionResult completion = await _restorePointService.CompleteAsync(restorePointSession, cancelled: false);
                result.RestorePointMessage = completion.Message;
                restorePointSession = null;
            }

            UpdateAutomaticProgress(90, "إنشاء تقرير التنظيف...");
            result.CompletedAt = DateTimeOffset.UtcNow;
            AutomaticCleanupReportResult report = await _automaticCleanupReportService.CreateAsync(result, token);
            _latestAutomaticReportPath = report.HtmlPath;

            await RecordActivityAsync(
                "التنظيف التلقائي",
                result.PreviewOnly ? "معاينة فقط" : result.Warnings.Count > 0 ? "اكتمل بتحذيرات" : "نجاح",
                $"ملفات مؤقتة: {result.TemporaryDeletedFiles:N0}، بقايا للحجر: {result.OrphansQuarantined:N0}، بدء تشغيل مكسور: {result.BrokenRegistryEntriesDisabled + result.BrokenStartupItemsDisabled:N0}.",
                result.TotalChangedItems,
                result.TotalDiskBytesFreed,
                result.RestorePointSequence);
            await RefreshActivityAsync();

            UpdateAutomaticProgress(100, "اكتمل التنظيف التلقائي وتم إنشاء التقرير.");
            AutomaticCleanupSummaryText.Text = BuildAutomaticSummary(result);
            AutomaticCleanupOpenReportButton.IsEnabled = true;
            SetStatus("اكتمل التنظيف التلقائي.");

            if (File.Exists(_latestAutomaticReportPath))
            {
                OpenPathWithShell(_latestAutomaticReportPath, "تعذر فتح تقرير التنظيف التلقائي.");
            }
        }
        catch (OperationCanceledException)
        {
            result.Cancelled = true;
            result.CompletedAt = DateTimeOffset.UtcNow;
            result.Warnings.Add("أوقف المستخدم العملية قبل اكتمالها.");
            AutomaticCleanupReportResult report = await _automaticCleanupReportService.CreateAsync(result);
            _latestAutomaticReportPath = report.HtmlPath;
            AutomaticCleanupOpenReportButton.IsEnabled = true;
            AutomaticCleanupSummaryText.Text = L("تم إيقاف التنظيف. تم حفظ تقرير بما اكتمل قبل الإيقاف.");
            SetStatus("تم إيقاف التنظيف التلقائي.");
        }
        catch (Exception ex)
        {
            result.CompletedAt = DateTimeOffset.UtcNow;
            result.Warnings.Add(ex.Message);
            try
            {
                AutomaticCleanupReportResult report = await _automaticCleanupReportService.CreateAsync(result);
                _latestAutomaticReportPath = report.HtmlPath;
                AutomaticCleanupOpenReportButton.IsEnabled = true;
            }
            catch (Exception reportException)
            {
                AppLogger.Error("Could not create automatic cleanup failure report.", reportException);
            }

            HandleError("تعذر إكمال التنظيف التلقائي. تم الاحتفاظ بما نُفذ بأمان.", ex);
        }
        finally
        {
            if (restorePointSession is not null)
            {
                try
                {
                    RestorePointCompletionResult completion = await _restorePointService.CompleteAsync(
                        restorePointSession,
                        cancelled: true);
                    result.RestorePointMessage = completion.Message;
                }
                catch (Exception ex)
                {
                    AppLogger.Error("Could not complete automatic-cleanup restore point.", ex);
                }
            }

            _automaticCleanupCancellation?.Dispose();
            _automaticCleanupCancellation = null;
            AutomaticCleanupStartButton.IsEnabled = true;
            AutomaticCleanupCancelButton.IsEnabled = false;
            SetAutomaticCleanupUi(isRunning: false);
            SetBusy(false);
        }
    }

    private void CancelAutomaticCleanup_Click(object sender, RoutedEventArgs e)
    {
        _automaticCleanupCancellation?.Cancel();
        AutomaticCleanupSummaryText.Text = L("جارٍ إيقاف العملية بعد إنهاء العنصر الحالي...");
        SetStatus("جارٍ إيقاف التنظيف التلقائي...");
    }

    private void LoadLatestAutomaticReport()
    {
        try
        {
            if (!Directory.Exists(AutomaticCleanupReportService.ReportsDirectory))
            {
                AutomaticCleanupOpenReportButton.IsEnabled = false;
                return;
            }

            _latestAutomaticReportPath = Directory
                .EnumerateFiles(AutomaticCleanupReportService.ReportsDirectory, "automatic-cleanup-*.html", SearchOption.TopDirectoryOnly)
                .OrderByDescending(File.GetLastWriteTimeUtc)
                .FirstOrDefault() ?? string.Empty;
            AutomaticCleanupOpenReportButton.IsEnabled = File.Exists(_latestAutomaticReportPath);
        }
        catch (Exception ex)
        {
            AppLogger.Error("Could not locate latest automatic cleanup report.", ex);
            _latestAutomaticReportPath = string.Empty;
            AutomaticCleanupOpenReportButton.IsEnabled = false;
        }
    }

    private void OpenLatestAutomaticReport_Click(object sender, RoutedEventArgs e)
    {
        if (string.IsNullOrWhiteSpace(_latestAutomaticReportPath) || !File.Exists(_latestAutomaticReportPath))
        {
            ShowLocalizedMessage("لا يوجد تقرير تنظيف تلقائي حديث.", "التقرير", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        OpenPathWithShell(_latestAutomaticReportPath, "تعذر فتح تقرير التنظيف التلقائي.");
    }

    private void OpenAutomaticReportsFolder_Click(object sender, RoutedEventArgs e)
    {
        Directory.CreateDirectory(AutomaticCleanupReportService.ReportsDirectory);
        OpenPathWithShell(AutomaticCleanupReportService.ReportsDirectory, "تعذر فتح مجلد تقارير التنظيف التلقائي.");
    }

    private void SetAutomaticCleanupUi(bool isRunning)
    {
        foreach (object item in RootTabs.Items)
        {
            if (item is System.Windows.Controls.TabItem tab)
            {
                tab.IsEnabled = !isRunning || ReferenceEquals(tab, AutomaticCleanupTab);
            }
        }

        if (isRunning)
        {
            RootTabs.SelectedItem = AutomaticCleanupTab;
        }
    }

    private void UpdateAutomaticProgress(double value, string message)
    {
        AutomaticCleanupProgressBar.Value = Math.Clamp(value, 0, 100);
        string localized = L(message);
        AutomaticCleanupStageText.Text = localized;
        StatusText.Text = localized;
    }

    private string BuildAutomaticSummary(AutomaticCleanupResult result)
    {
        string code = LocalizationService.NormalizeLanguage(result.LanguageCode);
        IFormatProvider culture = LocalizationService.CultureFor(code);
        string nOrphans = result.OrphansQuarantined.ToString("N0", culture);
        string nRegistry = (result.BrokenRegistryEntriesDisabled + result.BrokenStartupItemsDisabled).ToString("N0", culture);
        string nWarnings = result.Warnings.Count.ToString("N0", culture);
        string mode = result.PreviewOnly
            ? LocalizationService.T("@PreviewCompleted", code)
            : LocalizationService.T("@Completed", code);

        return code == "ar"
            ? $"{mode}. المساحة المحررة {result.DiskFreedText}، البقايا المنقولة إلى الحجر {nOrphans}، عناصر بدء التشغيل المعالجة {nRegistry}، التحذيرات {nWarnings}. لم يُغلق البرنامج أي تطبيق ولم ينفذ تنظيف رام تلقائيًا."
            : $"{mode}. Disk space freed: {result.DiskFreedText}; leftovers moved to quarantine: {nOrphans}; startup items handled: {nRegistry}; warnings: {nWarnings}. No application was closed and no automatic RAM cleaning was performed.";
    }

    private static void ReplaceCollection<T>(
        System.Collections.ObjectModel.ObservableCollection<T> collection,
        IEnumerable<T> items)
    {
        collection.Clear();
        foreach (T item in items)
        {
            collection.Add(item);
        }
    }
}
