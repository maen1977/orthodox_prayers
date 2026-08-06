using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Diagnostics;
using System.Windows;
using System.Windows.Threading;
using Microsoft.Win32;
using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Models;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner;

public partial class MainWindow : Window
{
    private readonly CleanupService _cleanupService = new();
    private readonly LeftoverService _leftoverService = new();
    private readonly InstalledAppsService _installedAppsService = new();
    private readonly ProcessService _processService = new();
    private readonly SystemMemoryService _systemMemoryService = new();
    private readonly QuarantineService _quarantineService = new();
    private readonly DeepUninstallService _deepUninstallService;
    private readonly StartupManagerService _startupManagerService = new();
    private readonly DiskAnalyzerService _diskAnalyzerService = new();
    private CancellationTokenSource? _diskScanCancellation;
    private bool _localizationRefreshPending;

    public ObservableCollection<CleanupTarget> CleanupTargets { get; } = [];
    public ObservableCollection<LeftoverItem> Leftovers { get; } = [];
    public ObservableCollection<InstalledApp> InstalledApps { get; } = [];
    public ObservableCollection<ProcessInfoItem> Processes { get; } = [];
    public ObservableCollection<QuarantineItem> QuarantineItems { get; } = [];
    public ObservableCollection<OperationSessionRecord> OperationSessions { get; } = [];
    public ObservableCollection<StartupItem> StartupItems { get; } = [];
    public ObservableCollection<DiskFileItem> DiskLargestFiles { get; } = [];
    public ObservableCollection<DiskFileItem> DiskDuplicateFiles { get; } = [];
    public ObservableCollection<DiskFolderSummary> DiskFolders { get; } = [];
    public ObservableCollection<DiskCategorySummary> DiskCategories { get; } = [];

    public MainWindow()
    {
        InitializeComponent();
        DataContext = this;
        _deepUninstallService = new DeepUninstallService(_quarantineService);
        _monitoredUninstallCleanupService = new MonitoredUninstallCleanupService(_installMonitorService, _quarantineService);
        LocalizationService.Apply(this, App.CurrentSettings.LanguageCode);
    }

    private async void Window_Loaded(object sender, RoutedEventArgs e)
    {
        LoadSettingsIntoControls();
        LocalizationService.Apply(this, _settings.LanguageCode);
        UpdateAboutPage();
        DiskPathBox.Text = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        UpdateV15Status();
        LoadLatestPreviewReport();
        LoadLatestAutomaticReport();
        await RefreshHomeDashboardAsync();
        _liteUiReady = true;
        ApplyStartupNavigation();
        SetStatus("جاهز — نسخة Lite لا تفحص الأقراص أو البرامج تلقائيًا عند التشغيل.");

        if (_settings.CheckForUpdatesOnStartup && !string.IsNullOrWhiteSpace(GetEffectiveRepository()))
        {
            await CheckForUpdatesAsync(showMessages: false);
        }
    }

    private void Window_Closing(object? sender, CancelEventArgs e)
    {
        HandleInstallMonitorWindowClosing(e);
        if (e.Cancel)
        {
            return;
        }

        _diskScanCancellation?.Cancel();
        _automaticCleanupCancellation?.Cancel();
        _updateCancellation?.Cancel();
    }

    private async void ScanCleanup_Click(object sender, RoutedEventArgs e)
        => await ScanCleanupAsync();

    private async Task ScanCleanupAsync()
    {
        try
        {
            SetBusy(true, "بدء فحص الملفات المؤقتة...");
            List<CleanupTarget> targets = await _cleanupService.ScanAsync(CreateProgress());

            CleanupTargets.Clear();
            foreach (CleanupTarget target in targets)
            {
                CleanupTargets.Add(target);
            }
            _cleanupProfileService.Apply(CleanupProfileComboBox.SelectedValue?.ToString() ?? _settings.DefaultCleanupProfile, CleanupTargets);

            long totalBytes = targets.Sum(target => target.SizeBytes);
            int totalFiles = targets.Sum(target => target.FileCount);
            bool truncated = targets.Any(target => target.ScanTruncated);
            CleanupSummaryText.Text = L($"تم العثور على {totalFiles:N0} ملف بحجم {SizeFormatter.Format(totalBytes, _settings.LanguageCode)}."
                + (truncated ? " تم وضع حد لعدد الملفات المعروضة لحماية الرام؛ يمكن إعادة الفحص بعد التنظيف." : string.Empty));
            SetStatus("اكتمل فحص الملفات المؤقتة.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر فحص الملفات المؤقتة.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void CleanSelected_Click(object sender, RoutedEventArgs e)
    {
        List<CleanupTarget> selected = CleanupTargets.Where(target => target.IsSelected && target.FileCount > 0).ToList();
        if (selected.Count == 0)
        {
            ShowLocalizedMessage("لا توجد عناصر محددة تحتوي على ملفات قابلة للتنظيف.", "تنظيف", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        long total = selected.Sum(target => target.SizeBytes);
        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = "تنظيف الملفات المؤقتة",
                Description = "حذف الملفات المؤقتة المحددة نهائيًا.",
                ItemCount = selected.Sum(target => target.FileCount),
                EstimatedBytes = total,
                RequiresAdministrator = selected.Any(target => target.RequiresAdministrator),
                RiskLevel = "منخفض",
                Items = selected.Select(target => new OperationPreviewItem
                {
                    Name = target.Name,
                    Location = target.RootPath,
                    Action = $"حذف {target.FileCount:N0} ملف مؤقت",
                    Safety = target.Description,
                    SizeBytes = target.SizeBytes
                }).ToList()
            }))
        {
            return;
        }

        MessageBoxResult confirmation = !_settings.ConfirmDangerousOperations
            ? MessageBoxResult.Yes
            : ShowLocalizedMessage(
            $"سيتم حذف الملفات المؤقتة المحددة نهائيًا وتوفير نحو {SizeFormatter.Format(total, _settings.LanguageCode)}. هل تريد المتابعة؟",
            "تأكيد التنظيف",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);

        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        try
        {
            SetBusy(true, "تنظيف الملفات المحددة...");
            CleanupResult result = await _cleanupService.CleanAsync(selected, CreateProgress());
            AppLogger.Info($"Cleanup completed: {result.DeletedFiles} files, {result.FreedBytes} bytes, {result.FailedFiles} failures.");
            await RecordActivityAsync(
                "تنظيف الملفات المؤقتة",
                result.FailedFiles > 0 ? "اكتمل بتحذيرات" : "نجاح",
                $"تم حذف {result.DeletedFiles:N0} ملف، وتعذر حذف {result.FailedFiles:N0} ملف.",
                result.DeletedFiles,
                result.FreedBytes);
            await RefreshActivityAsync();

            ShowLocalizedMessage(
                $"تم حذف {result.DeletedFiles:N0} ملف وتوفير {SizeFormatter.Format(result.FreedBytes, _settings.LanguageCode)}.\n" +
                (result.FailedFiles > 0 ? $"تعذر حذف {result.FailedFiles:N0} ملف لأنها مستخدمة أو محمية." : "اكتمل التنظيف بدون أخطاء."),
                "نتيجة التنظيف",
                MessageBoxButton.OK,
                result.FailedFiles > 0 ? MessageBoxImage.Information : MessageBoxImage.None);

            SetBusy(false);
            await ScanCleanupAsync();
        }
        catch (Exception ex)
        {
            HandleError("تعذر إكمال التنظيف.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void SelectAllCleanup_Click(object sender, RoutedEventArgs e)
    {
        foreach (CleanupTarget target in CleanupTargets)
        {
            target.IsSelected = true;
        }
    }

    private void SelectNoneCleanup_Click(object sender, RoutedEventArgs e)
    {
        foreach (CleanupTarget target in CleanupTargets)
        {
            target.IsSelected = false;
        }
    }

    private void BrowseDiskPath_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var dialog = new OpenFolderDialog
            {
                Title = L("اختر المجلد أو القرص المراد تحليله"),
                Multiselect = false,
                InitialDirectory = Directory.Exists(DiskPathBox.Text)
                    ? DiskPathBox.Text
                    : Environment.GetFolderPath(Environment.SpecialFolder.UserProfile)
            };

            if (dialog.ShowDialog(this) == true)
            {
                DiskPathBox.Text = dialog.FolderName;
            }
        }
        catch (Exception ex)
        {
            HandleError("تعذر فتح نافذة اختيار المجلد.", ex);
        }
    }

    private async void ScanDisk_Click(object sender, RoutedEventArgs e)
    {
        if (_diskScanCancellation is not null)
        {
            ShowLocalizedMessage("يوجد تحليل جارٍ بالفعل. أوقفه أولًا أو انتظر اكتماله.", "محلل مساحة القرص", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        string path = Environment.ExpandEnvironmentVariables(DiskPathBox.Text.Trim());
        if (!Directory.Exists(path))
        {
            ShowLocalizedMessage("اختر مجلدًا أو قرصًا موجودًا قبل بدء التحليل.", "محلل مساحة القرص", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        _diskScanCancellation = new CancellationTokenSource();
        SetDiskScanUi(true);
        DiskLargestFiles.Clear();
        DiskDuplicateFiles.Clear();
        DiskFolders.Clear();
        DiskCategories.Clear();

        try
        {
            SetBusy(true, "بدء تحليل مساحة القرص...", disableTabs: false);
            var progress = new Progress<DiskScanProgress>(value =>
            {
                StatusText.Text = L(value.Message);
                DiskSummaryText.Text = L(value.Message);
            });

            bool lowResourceMode = _settings.LowResourceMode;
            bool calculateDuplicates = DiskDuplicateScanCheckBox.IsChecked == true;
            var options = new DiskAnalyzerOptions
            {
                LargestFileLimit = lowResourceMode
                    ? Math.Min(_settings.LargestFilesLimit, 500)
                    : _settings.LargestFilesLimit,
                MinimumDuplicateSizeBytes = checked((long)_settings.MinimumDuplicateSizeMb * 1024L * 1024L),
                CalculateDuplicates = calculateDuplicates,
                DuplicateCandidateLimit = lowResourceMode ? 20_000 : 100_000,
                DuplicateResultFileLimit = lowResourceMode ? 1_000 : 5_000,
                ProgressInterval = lowResourceMode ? 1_000 : 250,
                HashBufferSizeBytes = lowResourceMode ? 128 * 1024 : 1024 * 1024,
                ScanThrottleMilliseconds = lowResourceMode ? 1 : 0
            };

            DiskAnalysisResult result = await _diskAnalyzerService.AnalyzeAsync(
                path,
                options,
                progress,
                _diskScanCancellation.Token);

            foreach (DiskFileItem item in result.LargestFiles)
            {
                DiskLargestFiles.Add(item);
            }

            foreach (DiskFileItem item in result.DuplicateFiles)
            {
                DiskDuplicateFiles.Add(item);
            }

            foreach (DiskFolderSummary item in result.FolderSummaries)
            {
                DiskFolders.Add(item);
            }

            foreach (DiskCategorySummary item in result.CategorySummaries)
            {
                DiskCategories.Add(item);
            }

            int duplicateGroups = result.DuplicateFiles
                .Select(item => item.DuplicateGroup)
                .Where(group => !string.IsNullOrWhiteSpace(group))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .Count();
            string candidateWarning = result.DuplicateCandidateLimitReached
                ? L(" تم بلوغ حد مرشحي التكرار؛ قد لا تظهر كل التكرارات في الأقراص الضخمة.")
                : string.Empty;
            if (result.DuplicateResultLimitReached)
            {
                candidateWarning += L(" تم عرض أكبر مجموعات التكرار فقط لحماية أداء الواجهة.");
            }

            string duplicateSummary = result.DuplicateAnalysisPerformed
                ? L($"مجموعات التكرار: {duplicateGroups:N0}، والمساحة المكررة المقدّرة: {SizeFormatter.Format(result.DuplicateWasteBytes, _settings.LanguageCode)}.")
                : L("لم يتم حساب بصمات التكرار في هذا الفحص الخفيف. فعّل خيار «فحص التكرارات» عند الحاجة.");
            DiskSummaryText.Text =
                L($"تم فحص {result.FileCount:N0} ملف بحجم {SizeFormatter.Format(result.TotalBytes, _settings.LanguageCode)}.") + " " +
                duplicateSummary + " " +
                L($"تم تجاوز {result.SkippedEntries:N0} عنصر غير متاح أو رابط خاص.") +
                candidateWarning;
            DiskSelectionSummaryText.Text = L(result.DuplicateAnalysisPerformed
                ? "راجع المسار والحماية قبل التحديد. الملفات المكررة لم تُحدد تلقائيًا."
                : "الفحص الخفيف اكتمل دون قراءة محتوى الملفات الكبيرة؛ هذا هو الوضع الأفضل لجهازك.");
            SetStatus("اكتمل تحليل مساحة القرص.");
        }
        catch (OperationCanceledException)
        {
            DiskSummaryText.Text = L("تم إيقاف التحليل. النتائج الجزئية لم تُعتمد؛ أعد الفحص عند الحاجة.");
            SetStatus("تم إيقاف تحليل مساحة القرص.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر تحليل المجلد أو القرص المحدد.", ex);
        }
        finally
        {
            SetDiskScanUi(false);
            _diskScanCancellation?.Dispose();
            _diskScanCancellation = null;
            SetBusy(false, disableTabs: false);
        }
    }

    private void CancelDiskScan_Click(object sender, RoutedEventArgs e)
    {
        if (_diskScanCancellation is null)
        {
            return;
        }

        DiskCancelButton.IsEnabled = false;
        StatusText.Text = L("جارٍ إيقاف التحليل بأمان...");
        _diskScanCancellation.Cancel();
    }

    private void SelectDuplicateExtras_Click(object sender, RoutedEventArgs e)
    {
        foreach (DiskFileItem item in DiskLargestFiles)
        {
            item.IsSelected = false;
        }

        int selected = 0;
        long bytes = 0;
        foreach (DiskFileItem item in DiskDuplicateFiles)
        {
            bool shouldSelect = !item.IsPreferredCopy && item.IsSafeToQuarantine && File.Exists(item.Path);
            item.IsSelected = shouldSelect;
            if (shouldSelect)
            {
                selected++;
                bytes += item.SizeBytes;
            }
        }

        DiskSelectionSummaryText.Text = L(selected == 0
            ? "لا توجد نسخ إضافية آمنة قابلة للتحديد."
            : $"تم تحديد {selected:N0} نسخة إضافية بحجم {SizeFormatter.Format(bytes, _settings.LanguageCode)}. راجع كل مجموعة قبل النقل.");
    }

    private void OpenDiskFileLocation_Click(object sender, RoutedEventArgs e)
    {
        DiskFileItem? item = DiskDuplicateFilesGrid.SelectedItem as DiskFileItem
                             ?? DiskLargestFilesGrid.SelectedItem as DiskFileItem;
        if (item is null)
        {
            ShowLocalizedMessage("حدد ملفًا من قائمة أكبر الملفات أو الملفات المكررة أولًا.", "فتح موقع الملف", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        try
        {
            if (File.Exists(item.Path))
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = "explorer.exe",
                    Arguments = $"/select,\"{item.Path}\"",
                    UseShellExecute = true
                });
                return;
            }

            string? parent = Path.GetDirectoryName(item.Path);
            if (!string.IsNullOrWhiteSpace(parent) && Directory.Exists(parent))
            {
                Process.Start(new ProcessStartInfo(parent) { UseShellExecute = true });
                return;
            }

            ShowLocalizedMessage("الملف ومجلده لم يعودا موجودين.", "فتح موقع الملف", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            HandleError("تعذر فتح موقع الملف.", ex);
        }
    }

    private async void QuarantineDiskFiles_Click(object sender, RoutedEventArgs e)
    {
        List<DiskFileItem> selected = DiskLargestFiles
            .Concat(DiskDuplicateFiles)
            .Where(item => item.IsSelected && item.IsSafeToQuarantine)
            .GroupBy(item => Path.GetFullPath(item.Path), StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .Where(item => File.Exists(item.Path))
            .ToList();

        if (selected.Count == 0)
        {
            ShowLocalizedMessage("حدد ملفًا آمنًا واحدًا على الأقل بعد مراجعة مساره.", "محلل مساحة القرص", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        HashSet<string> selectedPaths = selected
            .Select(item => Path.GetFullPath(item.Path))
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        foreach (IGrouping<string, DiskFileItem> group in DiskDuplicateFiles
                     .Where(item => !string.IsNullOrWhiteSpace(item.DuplicateGroup))
                     .GroupBy(item => item.DuplicateGroup, StringComparer.OrdinalIgnoreCase))
        {
            if (group.Count(item => File.Exists(item.Path)) > 1
                && PathSafetyService.WouldRemoveEveryExistingCopy(group.Select(item => item.Path), selectedPaths))
            {
                ShowLocalizedMessage(
                    $"لا يمكن نقل كل نسخ {group.Key}. اترك نسخة واحدة على الأقل غير محددة.",
                    "حماية الملفات المكررة",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);
                return;
            }
        }

        long totalBytes = selected.Sum(item => item.SizeBytes);
        int referenceCopies = DiskDuplicateFiles.Count(item =>
            item.IsPreferredCopy && selectedPaths.Contains(Path.GetFullPath(item.Path)));
        string preview = string.Join("\n", selected.Take(6).Select(item => $"• {item.Path}"));
        if (selected.Count > 6)
        {
            preview += $"\n• و{selected.Count - 6:N0} ملفات أخرى";
        }

        string referenceWarning = referenceCopies > 0
            ? $"\n\nتنبيه: يتضمن الاختيار {referenceCopies:N0} ملفًا مصنفًا كنسخة مرجعية."
            : string.Empty;

        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = "نقل ملفات إلى الحجر",
                Description = "نقل الملفات المحددة إلى حجر البرنامج القابل للاستعادة.",
                ItemCount = selected.Count,
                EstimatedBytes = totalBytes,
                RiskLevel = referenceCopies > 0 ? "متوسط" : "منخفض",
                Items = selected.Select(item => new OperationPreviewItem
                {
                    Name = item.Name,
                    Location = item.Path,
                    Action = "نقل إلى الحجر",
                    Safety = item.IsPreferredCopy ? "نسخة مرجعية — تحتاج مراجعة" : item.ProtectionReason,
                    SizeBytes = item.SizeBytes
                }).ToList()
            }))
        {
            return;
        }

        MessageBoxResult confirmation = !_settings.ConfirmDangerousOperations
            ? MessageBoxResult.Yes
            : ShowLocalizedMessage(
            $"سيتم نقل {selected.Count:N0} ملف بحجم {SizeFormatter.Format(totalBytes, _settings.LanguageCode)} إلى الحجر القابل للاستعادة:\n\n{preview}{referenceWarning}\n\nهل تريد المتابعة؟",
            "تأكيد نقل الملفات إلى الحجر",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        try
        {
            SetBusy(true, "نقل الملفات المحددة إلى الحجر...");
            QuarantineOperationResult result = await _quarantineService.QuarantineDiskFilesAsync(selected, CreateProgress());
            await RecordActivityAsync(
                "نقل ملفات إلى الحجر",
                result.FailedItems > 0 ? "اكتمل بتحذيرات" : "نجاح",
                $"نجح: {result.SucceededItems:N0}، فشل: {result.FailedItems:N0}، تم تجاوز: {result.SkippedItems:N0}.",
                result.SucceededItems,
                result.BytesProcessed);
            await RefreshActivityAsync();
            HashSet<string> movedPaths = selected
                .Where(item => !File.Exists(item.Path))
                .Select(item => Path.GetFullPath(item.Path))
                .ToHashSet(StringComparer.OrdinalIgnoreCase);

            foreach (DiskFileItem item in DiskLargestFiles.Where(item => movedPaths.Contains(Path.GetFullPath(item.Path))).ToList())
            {
                DiskLargestFiles.Remove(item);
            }

            foreach (DiskFileItem item in DiskDuplicateFiles.Where(item => movedPaths.Contains(Path.GetFullPath(item.Path))).ToList())
            {
                DiskDuplicateFiles.Remove(item);
            }

            await LoadQuarantineItemsAsync();
            DiskSelectionSummaryText.Text =
                L($"تم نقل {result.SucceededItems:N0} ملف إلى الحجر. أعد التحليل لتحديث أحجام المجلدات والتكرارات.");
            ShowLocalizedMessage(
                BuildOperationMessage("تم نقل", result, "إلى الحجر"),
                "نتيجة نقل الملفات",
                MessageBoxButton.OK,
                result.FailedItems > 0 || result.SkippedItems > 0 ? MessageBoxImage.Information : MessageBoxImage.None);
        }
        catch (Exception ex)
        {
            HandleError("تعذر نقل بعض الملفات إلى الحجر.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void SearchLeftovers_Click(object sender, RoutedEventArgs e)
    {
        string query = LeftoverSearchBox.Text.Trim();
        if (query.Length < 3)
        {
            ShowLocalizedMessage("اكتب ثلاثة أحرف على الأقل من اسم البرنامج.", "فحص البقايا", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        await SearchLeftoversAsync(query, string.Empty, string.Empty);
    }

    private async Task SearchLeftoversAsync(string programName, string publisher, string installLocation)
    {
        try
        {
            SetBusy(true, $"البحث عن بقايا: {programName}");
            List<LeftoverItem> items = await _leftoverService.SearchAsync(
                programName,
                publisher,
                installLocation,
                CreateProgress());

            Leftovers.Clear();
            foreach (LeftoverItem item in items)
            {
                Leftovers.Add(item);
            }

            long totalBytes = items.Sum(item => item.SizeBytes);
            int highConfidence = items.Count(item => item.ConfidenceScore >= 80);
            int mediumConfidence = items.Count(item => item.ConfidenceScore is >= 55 and < 80);

            LeftoverSummaryText.Text = L(items.Count == 0
                ? "لم يتم العثور على مجلدات مطابقة."
                : $"{items.Count:N0} نتيجة بحجم {SizeFormatter.Format(totalBytes, _settings.LanguageCode)} — ثقة عالية: {highConfidence:N0}، متوسطة: {mediumConfidence:N0}. راجع المسارات قبل الاختيار.");
            SetStatus("اكتمل فحص بقايا البرامج.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر البحث عن بقايا البرنامج.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void DeleteLeftovers_Click(object sender, RoutedEventArgs e)
    {
        List<LeftoverItem> selected = Leftovers.Where(item => item.IsSelected && item.IsQuarantinable).ToList();
        if (selected.Count == 0)
        {
            ShowLocalizedMessage("حدد مجلدًا واحدًا على الأقل بعد مراجعة مساره وسبب التطابق.", "بقايا البرامج", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        string paths = string.Join("\n", selected.Take(5).Select(item => $"• [{item.ConfidenceText}] {item.Path}"));
        if (selected.Count > 5)
        {
            paths += $"\n• و{selected.Count - 5} عناصر أخرى";
        }

        int lowConfidence = selected.Count(item => item.ConfidenceScore < 55);
        string warning = lowConfidence > 0
            ? $"\n\nتنبيه: اخترت {lowConfidence:N0} عنصر بدرجة ثقة منخفضة. راجعه بعناية."
            : string.Empty;

        long selectedBytes = selected.Sum(item => item.SizeBytes);
        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = "نقل بقايا البرامج إلى الحجر",
                Description = "نقل مجلدات البقايا المحددة إلى حجر قابل للاستعادة.",
                ItemCount = selected.Count,
                EstimatedBytes = selectedBytes,
                RiskLevel = lowConfidence > 0 ? "مرتفع" : "متوسط",
                Items = selected.Select(item => new OperationPreviewItem
                {
                    Name = item.Name,
                    Location = item.Path,
                    Action = "نقل إلى الحجر",
                    Safety = $"{item.ConfidenceText} — {item.MatchReason}",
                    SizeBytes = item.SizeBytes
                }).ToList()
            }))
        {
            return;
        }

        MessageBoxResult confirmation = !_settings.ConfirmDangerousOperations
            ? MessageBoxResult.Yes
            : ShowLocalizedMessage(
            $"سيتم نقل المجلدات التالية إلى حجر البرنامج مع إمكانية استعادتها:\n\n{paths}{warning}\n\nهل تريد المتابعة؟",
            "تأكيد نقل البقايا إلى الحجر",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);

        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        try
        {
            SetBusy(true, "نقل البقايا إلى الحجر...");
            QuarantineOperationResult result = await _quarantineService.QuarantineAsync(selected, CreateProgress());
            await RecordActivityAsync(
                "نقل بقايا البرامج إلى الحجر",
                result.FailedItems > 0 ? "اكتمل بتحذيرات" : "نجاح",
                $"نجح: {result.SucceededItems:N0}، فشل: {result.FailedItems:N0}، تم تجاوز: {result.SkippedItems:N0}.",
                result.SucceededItems,
                result.BytesProcessed);
            await RefreshActivityAsync();
            foreach (LeftoverItem item in selected.Where(item => !Directory.Exists(item.Path)).ToList())
            {
                Leftovers.Remove(item);
            }

            await LoadQuarantineItemsAsync();
            LeftoverSummaryText.Text = L($"تم نقل {result.SucceededItems:N0} عنصر بحجم {SizeFormatter.Format(result.BytesProcessed, _settings.LanguageCode)} إلى الحجر.");
            ShowLocalizedMessage(
                BuildOperationMessage("تم نقل", result, "إلى الحجر"),
                "نتيجة الحجر",
                MessageBoxButton.OK,
                result.FailedItems > 0 || result.SkippedItems > 0 ? MessageBoxImage.Information : MessageBoxImage.None);
        }
        catch (Exception ex)
        {
            HandleError("تعذر نقل بعض البقايا إلى الحجر.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void RefreshInstalledApps_Click(object sender, RoutedEventArgs e)
        => await RefreshInstalledAppsAsync();

    private async Task RefreshInstalledAppsAsync()
    {
        try
        {
            SetBusy(true, "تحميل البرامج المثبتة...");
            List<InstalledApp> apps = await _installedAppsService.GetInstalledAppsAsync();
            InstalledApps.Clear();
            foreach (InstalledApp app in apps)
            {
                InstalledApps.Add(app);
            }

            InstalledAppsSummaryText.Text = L($"تم العثور على {apps.Count:N0} برنامج مثبت.");
            SetStatus("تم تحديث قائمة البرامج المثبتة.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر قراءة قائمة البرامج المثبتة.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void OpenAppsSettings_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            Process.Start(new ProcessStartInfo("ms-settings:appsfeatures") { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            HandleError("تعذر فتح إعدادات تطبيقات ويندوز.", ex);
        }
    }

    private async void ScanSelectedAppLeftovers_Click(object sender, RoutedEventArgs e)
    {
        if (InstalledAppsGrid.SelectedItem is not InstalledApp app)
        {
            ShowLocalizedMessage("حدد برنامجًا من القائمة أولًا.", "فحص البقايا", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        await ScanAppLeftoversAsync(app);
    }

    private async void UninstallSelected_Click(object sender, RoutedEventArgs e)
    {
        if (InstalledAppsGrid.SelectedItem is not InstalledApp app)
        {
            ShowLocalizedMessage(
                LocalizationService.T("@SelectInstalledApplication", _settings.LanguageCode),
                LocalizationService.T("@DeepUninstallTitle", _settings.LanguageCode),
                MessageBoxButton.OK,
                MessageBoxImage.Information);
            return;
        }

        if (string.IsNullOrWhiteSpace(app.UninstallString))
        {
            ShowLocalizedMessage(
                LocalizationService.T("@NoUninstallCommand", _settings.LanguageCode),
                LocalizationService.T("@DeepUninstallTitle", _settings.LanguageCode),
                MessageBoxButton.OK,
                MessageBoxImage.Information);
            OpenAppsSettings_Click(sender, e);
            return;
        }

        string location = string.IsNullOrWhiteSpace(app.InstallLocation) ? app.Publisher : app.InstallLocation;
        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = LocalizationService.T("@DeepUninstallTitle", _settings.LanguageCode),
                Description = LocalizationService.Format("@DeepUninstallPreview", _settings.LanguageCode, app.DisplayName),
                ItemCount = 1,
                EstimatedBytes = app.EstimatedSizeBytes,
                RequiresAdministrator = true,
                RiskLevel = LocalizationService.T("@MediumRisk", _settings.LanguageCode),
                Items =
                [
                    new OperationPreviewItem
                    {
                        Name = app.DisplayName,
                        Location = location,
                        Action = LocalizationService.T("@DeepUninstallAction", _settings.LanguageCode),
                        Safety = LocalizationService.T("@DeepUninstallSafety", _settings.LanguageCode),
                        SizeBytes = app.EstimatedSizeBytes
                    }
                ]
            }))
        {
            return;
        }

        MessageBoxResult confirmation = !_settings.ConfirmDangerousOperations
            ? MessageBoxResult.Yes
            : ShowLocalizedMessage(
                LocalizationService.Format("@DeepUninstallConfirm", _settings.LanguageCode, app.DisplayName),
                LocalizationService.T("@DeepUninstallTitle", _settings.LanguageCode),
                MessageBoxButton.YesNo,
                MessageBoxImage.Warning);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        InstallMonitorSessionSummary? monitoredSession = await FindMatchingCompletedMonitorSessionAsync(app);

        RestorePointDecision restoreDecision = await PrepareRestorePointAsync(
            $"Safe Windows Cleaner — Before deep uninstall {app.DisplayName}",
            uninstallOperation: true);
        if (!restoreDecision.ContinueOperation)
        {
            SetStatus(LocalizationService.T("@RestorePointCancelledOperation", _settings.LanguageCode));
            return;
        }

        bool cancelRestoreSession = true;
        try
        {
            SetBusy(true, LocalizationService.T("@RunOfficialUninstaller", _settings.LanguageCode));
            Process? uninstallProcess = Process.Start(CreateUninstallStartInfo(app.UninstallString));
            if (uninstallProcess is null)
            {
                throw new InvalidOperationException(LocalizationService.T("@OfficialUninstallerDidNotStart", _settings.LanguageCode));
            }

            await uninstallProcess.WaitForExitAsync();
            int exitCode = uninstallProcess.ExitCode;
            if (exitCode is not 0 and not 1641 and not 3010)
            {
                throw new InvalidOperationException(
                    LocalizationService.Format("@UninstallerFailedExitCode", _settings.LanguageCode, exitCode));
            }

            SetBusy(true, LocalizationService.T("@VerifyApplicationRemoved", _settings.LanguageCode));
            bool removed = await WaitForInstalledApplicationRemovalAsync(app);
            if (!removed)
            {
                throw new InvalidOperationException(LocalizationService.T("@ApplicationStillInstalled", _settings.LanguageCode));
            }

            cancelRestoreSession = false;
            MonitoredUninstallCleanupResult? monitoredCleanup = null;
            if (monitoredSession is not null)
            {
                SetBusy(true, LocalizationService.T("@CleanMonitoredRecords", _settings.LanguageCode));
                monitoredCleanup = await _monitoredUninstallCleanupService.CleanupAsync(
                    monitoredSession.SessionId,
                    progress: null);
            }

            SetBusy(true, LocalizationService.T("@DeepCleanupProgress", _settings.LanguageCode));
            DeepUninstallResult cleanup = await _deepUninstallService.CleanupAsync(
                app,
                _settings.LanguageCode,
                CreateProgress(),
                monitoredCleanup);

            await RecordActivityAsync(
                LocalizationService.T("@DeepUninstallTitle", _settings.LanguageCode),
                cleanup.FailedItems > 0
                    ? LocalizationService.T("@CompletedWithWarnings", _settings.LanguageCode)
                    : LocalizationService.T("@Success", _settings.LanguageCode),
                LocalizationService.Format(
                    "@DeepUninstallSummary",
                    _settings.LanguageCode,
                    cleanup.TotalRemovedItems,
                    cleanup.FailedItems,
                    cleanup.SkippedItems),
                cleanup.TotalRemovedItems,
                cleanup.BytesQuarantined,
                restorePointSequence: restoreDecision.Session?.SequenceNumber ?? 0);

            await RefreshActivityAsync();
            await RefreshInstalledAppsAsync();
            await RefreshQuarantineAsync();

            if (File.Exists(cleanup.HtmlReportPath))
            {
                OpenPathWithShell(cleanup.HtmlReportPath, LocalizationService.T("@CouldNotOpenDeepReport", _settings.LanguageCode));
            }

            string restartNotice = cleanup.RestartRequired
                ? "\n\n" + LocalizationService.T("@RestartRequiredForLockedFiles", _settings.LanguageCode)
                : string.Empty;
            ShowLocalizedMessage(
                LocalizationService.Format(
                    "@DeepUninstallCompletedMessage",
                    _settings.LanguageCode,
                    app.DisplayName,
                    cleanup.TotalRemovedItems,
                    cleanup.DirectoriesQuarantined,
                    cleanup.FilesQuarantined,
                    cleanup.RegistryKeysRemoved + cleanup.RegistryValuesRemoved,
                    cleanup.ServicesRemoved,
                    cleanup.ScheduledTasksRemoved,
                    cleanup.FailedItems) + restartNotice,
                LocalizationService.T("@DeepUninstallCompleted", _settings.LanguageCode),
                MessageBoxButton.OK,
                cleanup.FailedItems > 0 ? MessageBoxImage.Warning : MessageBoxImage.Information);
            SetStatus(LocalizationService.T("@DeepUninstallCompleted", _settings.LanguageCode));
        }
        catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)
        {
            await RecordActivityAsync(
                LocalizationService.T("@DeepUninstallTitle", _settings.LanguageCode),
                LocalizationService.T("@Cancelled", _settings.LanguageCode),
                LocalizationService.T("@ElevationCancelled", _settings.LanguageCode));
            SetStatus(LocalizationService.T("@Cancelled", _settings.LanguageCode));
        }
        catch (Exception ex)
        {
            await RecordActivityAsync(
                LocalizationService.T("@DeepUninstallTitle", _settings.LanguageCode),
                LocalizationService.T("@Failed", _settings.LanguageCode),
                ex.Message);
            HandleError(LocalizationService.T("@DeepUninstallFailed", _settings.LanguageCode), ex);
        }
        finally
        {
            await FinishRestorePointAsync(restoreDecision.Session, cancelRestoreSession);
            SetBusy(false);
        }
    }

    private async Task<InstallMonitorSessionSummary?> FindMatchingCompletedMonitorSessionAsync(
        InstalledApp app,
        CancellationToken cancellationToken = default)
    {
        List<InstallMonitorSessionSummary> sessions = await _installMonitorService.GetSessionsAsync(cancellationToken);
        foreach (InstallMonitorSessionSummary session in sessions
                     .Where(candidate => candidate.Status == InstallMonitorStatus.Completed
                                         && string.Equals(candidate.DetectedApplicationName.Trim(), app.DisplayName.Trim(), StringComparison.OrdinalIgnoreCase))
                     .Take(20))
        {
            cancellationToken.ThrowIfCancellationRequested();
            InstallMonitorManifest manifest = await _installMonitorService.GetManifestAsync(session.SessionId, cancellationToken);
            bool publisherMatches = string.IsNullOrWhiteSpace(app.Publisher)
                                    || string.IsNullOrWhiteSpace(manifest.DetectedPublisher)
                                    || string.Equals(app.Publisher.Trim(), manifest.DetectedPublisher.Trim(), StringComparison.OrdinalIgnoreCase);
            bool versionMatches = string.IsNullOrWhiteSpace(app.Version)
                                  || string.IsNullOrWhiteSpace(manifest.DetectedVersion)
                                  || string.Equals(app.Version.Trim(), manifest.DetectedVersion.Trim(), StringComparison.OrdinalIgnoreCase);
            if (publisherMatches && versionMatches)
            {
                return session;
            }
        }

        return null;
    }

    private async Task<bool> WaitForInstalledApplicationRemovalAsync(
        InstalledApp original,
        CancellationToken cancellationToken = default)
    {
        for (int attempt = 0; attempt < 60; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            List<InstalledApp> installed = await _installedAppsService.GetInstalledAppsAsync(cancellationToken);
            bool stillInstalled = !string.IsNullOrWhiteSpace(original.RegistryKeyPath)
                ? installed.Any(candidate =>
                    string.Equals(candidate.RegistryHiveName, original.RegistryHiveName, StringComparison.OrdinalIgnoreCase)
                    && string.Equals(candidate.RegistryViewName, original.RegistryViewName, StringComparison.OrdinalIgnoreCase)
                    && string.Equals(candidate.RegistryKeyPath, original.RegistryKeyPath, StringComparison.OrdinalIgnoreCase))
                : installed.Any(candidate =>
                    string.Equals(candidate.DisplayName.Trim(), original.DisplayName.Trim(), StringComparison.OrdinalIgnoreCase)
                    && (string.IsNullOrWhiteSpace(original.Publisher)
                        || string.IsNullOrWhiteSpace(candidate.Publisher)
                        || string.Equals(candidate.Publisher.Trim(), original.Publisher.Trim(), StringComparison.OrdinalIgnoreCase)));
            if (!stillInstalled)
            {
                return true;
            }

            await Task.Delay(2000, cancellationToken);
        }

        return false;
    }

    private async Task ScanAppLeftoversAsync(InstalledApp app)
    {
        LeftoverSearchBox.Text = app.DisplayName;
        RootTabs.SelectedItem = LeftoversTab;
        await SearchLeftoversAsync(app.DisplayName, app.Publisher, app.InstallLocation);
    }

    private async void RefreshStartupItems_Click(object sender, RoutedEventArgs e)
        => await RefreshStartupItemsAsync();

    private async Task RefreshStartupItemsAsync()
    {
        try
        {
            SetBusy(true, "قراءة عناصر بدء التشغيل...");
            List<StartupItem> items = await _startupManagerService.GetStartupItemsAsync(CreateProgress());
            StartupItems.Clear();
            foreach (StartupItem item in items)
            {
                StartupItems.Add(item);
            }

            int enabled = items.Count(item => item.IsEnabled);
            int disabled = items.Count - enabled;
            int protectedItems = items.Count(item => !item.CanToggle);
            StartupSummaryText.Text = L($"{items.Count:N0} عنصر — مفعّل: {enabled:N0}، معطّل: {disabled:N0}، محمي: {protectedItems:N0}.");
            SetStatus("تم تحديث عناصر بدء التشغيل.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر قراءة بعض عناصر بدء التشغيل.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void OpenStartupSettings_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            Process.Start(new ProcessStartInfo("ms-settings:startupapps") { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            HandleError("تعذر فتح إعدادات بدء التشغيل في ويندوز.", ex);
        }
    }

    private void OpenStartupItemLocation_Click(object sender, RoutedEventArgs e)
    {
        StartupItem? item = StartupItemsGrid.SelectedItem as StartupItem
                            ?? StartupItems.FirstOrDefault(candidate => candidate.IsSelected);
        if (item is null)
        {
            ShowLocalizedMessage("حدد عنصرًا من القائمة أولًا.", "بدء التشغيل", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        string path = File.Exists(item.ExecutablePath)
            ? item.ExecutablePath
            : File.Exists(item.SourceA) ? item.SourceA : string.Empty;
        if (string.IsNullOrWhiteSpace(path))
        {
            ShowLocalizedMessage("لا يوجد ملف تنفيذي محلي يمكن فتح موقعه لهذا العنصر.", "بدء التشغيل", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = "explorer.exe",
                Arguments = $"/select,\"{path}\"",
                UseShellExecute = true
            });
        }
        catch (Exception ex)
        {
            HandleError("تعذر فتح موقع الملف.", ex);
        }
    }

    private async void DisableStartupItems_Click(object sender, RoutedEventArgs e)
    {
        List<StartupItem> selected = StartupItems
            .Where(item => item.IsSelected && item.CanToggle && item.IsEnabled)
            .ToList();
        if (selected.Count == 0)
        {
            ShowLocalizedMessage("حدد عنصرًا مفعّلًا واحدًا على الأقل. العناصر المحمية لا يمكن تحديدها.", "تعطيل بدء التشغيل", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = "تعطيل عناصر بدء التشغيل",
                Description = "تعطيل العناصر المحددة عند بدء تشغيل ويندوز دون حذفها.",
                ItemCount = selected.Count,
                RequiresAdministrator = selected.Any(item => item.Kind is StartupItemKind.Service or StartupItemKind.ScheduledTask),
                RiskLevel = selected.Any(item => item.Kind == StartupItemKind.Service) ? "متوسط" : "منخفض",
                Items = selected.Select(item => new OperationPreviewItem
                {
                    Name = item.Name,
                    Location = item.Location,
                    Action = "تعطيل عند بدء التشغيل",
                    Safety = item.DetailsText,
                    SizeBytes = 0
                }).ToList()
            }))
        {
            return;
        }

        string preview = string.Join("\n", selected.Take(6).Select(item => $"• {item.Name} — {item.Category}"));
        if (selected.Count > 6)
        {
            preview += $"\n• و{selected.Count - 6:N0} عناصر أخرى";
        }

        MessageBoxResult confirmation = !_settings.ConfirmDangerousOperations
            ? MessageBoxResult.Yes
            : ShowLocalizedMessage(
            $"سيتم تعطيل العناصر التالية عند بدء التشغيل:\n\n{preview}\n\nلن يتم إيقاف الخدمات التي تعمل الآن. قد يطلب ويندوز صلاحية المسؤول للعناصر العامة والخدمات والمهام. هل تريد المتابعة؟",
            "تأكيد تعطيل بدء التشغيل",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);

        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        RestorePointDecision restoreDecision = await PrepareRestorePointAsync("Safe Windows Cleaner — Before disabling startup items");
        if (!restoreDecision.ContinueOperation)
        {
            SetStatus("تم إلغاء تعطيل عناصر بدء التشغيل.");
            return;
        }

        bool cancelRestoreSession = true;
        try
        {
            SetBusy(true, "تعطيل عناصر بدء التشغيل المحددة...");
            StartupOperationResult result = await _startupManagerService.DisableAsync(selected, CreateProgress());
            cancelRestoreSession = false;
            await RecordActivityAsync(
                "تعطيل عناصر بدء التشغيل",
                result.FailedItems > 0 ? "اكتمل بتحذيرات" : "نجاح",
                $"نجح: {result.SucceededItems:N0}، فشل: {result.FailedItems:N0}، تم تجاوز: {result.SkippedItems:N0}.",
                result.SucceededItems,
                restorePointSequence: restoreDecision.Session?.SequenceNumber ?? 0);
            SetBusy(false);
            await RefreshStartupItemsAsync();
            await RefreshActivityAsync();
            ShowLocalizedMessage(
                BuildStartupOperationMessage("تم تعطيل", result),
                "نتيجة تعطيل بدء التشغيل",
                MessageBoxButton.OK,
                result.FailedItems > 0 || result.SkippedItems > 0 ? MessageBoxImage.Information : MessageBoxImage.None);
        }
        catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)
        {
            await RecordActivityAsync("تعطيل عناصر بدء التشغيل", "ألغيت", "تم إلغاء طلب صلاحية المسؤول.");
            SetStatus("تم إلغاء طلب صلاحية المسؤول.");
        }
        catch (Exception ex)
        {
            await RecordActivityAsync("تعطيل عناصر بدء التشغيل", "فشل", ex.Message);
            HandleError("تعذر تعطيل بعض عناصر بدء التشغيل.", ex);
        }
        finally
        {
            await FinishRestorePointAsync(restoreDecision.Session, cancelRestoreSession);
            SetBusy(false);
        }
    }

    private async void EnableStartupItems_Click(object sender, RoutedEventArgs e)
    {
        List<StartupItem> selected = StartupItems
            .Where(item => item.IsSelected && item.CanToggle && !item.IsEnabled)
            .ToList();
        if (selected.Count == 0)
        {
            ShowLocalizedMessage("حدد عنصرًا معطّلًا واحدًا على الأقل لإعادة تفعيله.", "إعادة التفعيل", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = "إعادة تفعيل عناصر بدء التشغيل",
                Description = "إعادة العناصر المحددة إلى حالة التشغيل التلقائي السابقة.",
                ItemCount = selected.Count,
                RequiresAdministrator = selected.Any(item => item.Kind is StartupItemKind.Service or StartupItemKind.ScheduledTask),
                RiskLevel = "منخفض",
                Items = selected.Select(item => new OperationPreviewItem
                {
                    Name = item.Name,
                    Location = item.Location,
                    Action = "إعادة التفعيل",
                    Safety = item.DetailsText,
                    SizeBytes = 0
                }).ToList()
            }))
        {
            return;
        }

        MessageBoxResult confirmation = !_settings.ConfirmDangerousOperations
            ? MessageBoxResult.Yes
            : ShowLocalizedMessage(
            $"سيتم إعادة تفعيل {selected.Count:N0} عنصر عند بدء التشغيل. هل تريد المتابعة؟",
            "تأكيد إعادة التفعيل",
            MessageBoxButton.YesNo,
            MessageBoxImage.Question);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        RestorePointDecision restoreDecision = await PrepareRestorePointAsync("Safe Windows Cleaner — Before enabling startup items");
        if (!restoreDecision.ContinueOperation)
        {
            SetStatus("تم إلغاء إعادة تفعيل عناصر بدء التشغيل.");
            return;
        }

        bool cancelRestoreSession = true;
        try
        {
            SetBusy(true, "إعادة تفعيل عناصر بدء التشغيل...");
            StartupOperationResult result = await _startupManagerService.EnableAsync(selected, CreateProgress());
            cancelRestoreSession = false;
            await RecordActivityAsync(
                "إعادة تفعيل عناصر بدء التشغيل",
                result.FailedItems > 0 ? "اكتمل بتحذيرات" : "نجاح",
                $"نجح: {result.SucceededItems:N0}، فشل: {result.FailedItems:N0}، تم تجاوز: {result.SkippedItems:N0}.",
                result.SucceededItems,
                restorePointSequence: restoreDecision.Session?.SequenceNumber ?? 0);
            SetBusy(false);
            await RefreshStartupItemsAsync();
            await RefreshActivityAsync();
            ShowLocalizedMessage(
                BuildStartupOperationMessage("تمت إعادة تفعيل", result),
                "نتيجة إعادة التفعيل",
                MessageBoxButton.OK,
                result.FailedItems > 0 || result.SkippedItems > 0 ? MessageBoxImage.Information : MessageBoxImage.None);
        }
        catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)
        {
            await RecordActivityAsync("إعادة تفعيل عناصر بدء التشغيل", "ألغيت", "تم إلغاء طلب صلاحية المسؤول.");
            SetStatus("تم إلغاء طلب صلاحية المسؤول.");
        }
        catch (Exception ex)
        {
            await RecordActivityAsync("إعادة تفعيل عناصر بدء التشغيل", "فشل", ex.Message);
            HandleError("تعذر إعادة تفعيل بعض عناصر بدء التشغيل.", ex);
        }
        finally
        {
            await FinishRestorePointAsync(restoreDecision.Session, cancelRestoreSession);
            SetBusy(false);
        }
    }

    private async void RefreshQuarantine_Click(object sender, RoutedEventArgs e)
        => await RefreshQuarantineAsync();

    private async Task RefreshQuarantineAsync()
    {
        try
        {
            SetBusy(true, "تحميل عناصر الحجر...");
            await LoadQuarantineItemsAsync();
            await LoadOperationSessionsAsync();
            SetStatus("تم تحديث مركز الإنقاذ وسجل الخطط.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر قراءة عناصر الحجر.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async Task LoadQuarantineItemsAsync()
    {
        List<QuarantineItem> items = await _quarantineService.GetItemsAsync();
        QuarantineItems.Clear();
        foreach (QuarantineItem item in items)
        {
            item.RetentionWarningDays = _settings.QuarantineRetentionDays;
            QuarantineItems.Add(item);
        }

        long totalBytes = items.Sum(item => item.SizeBytes);
        int oldItems = items.Count(item => item.AgeDays >= _settings.QuarantineRetentionDays);
        QuarantineSummaryText.Text = items.Count == 0
            ? L("الحجر فارغ.")
            : oldItems > 0
                ? L($"يوجد {items.Count:N0} عنصر بحجم {SizeFormatter.Format(totalBytes, _settings.LanguageCode)}، منها {oldItems:N0} أقدم من {_settings.QuarantineRetentionDays:N0} يومًا. يمكن استعادتها إلى مواقعها الأصلية.")
                : L($"يوجد {items.Count:N0} عنصر بحجم {SizeFormatter.Format(totalBytes, _settings.LanguageCode)}. يمكن استعادتها إلى مواقعها الأصلية.");
    }


    private async Task LoadOperationSessionsAsync()
    {
        List<OperationSessionRecord> sessions = await _operationSessionService.GetRecentAsync(100);
        OperationSessions.Clear();
        foreach (OperationSessionRecord session in sessions)
        {
            OperationSessions.Add(session);
        }
    }

    private async void RestoreQuarantine_Click(object sender, RoutedEventArgs e)
    {
        List<QuarantineItem> selected = QuarantineItems.Where(item => item.IsSelected).ToList();
        if (selected.Count == 0)
        {
            ShowLocalizedMessage("حدد عنصرًا واحدًا على الأقل لاستعادته.", "الاستعادة", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = "استعادة عناصر الحجر",
                Description = "استعادة العناصر المحددة إلى مواقعها الأصلية.",
                ItemCount = selected.Count,
                EstimatedBytes = selected.Sum(item => item.SizeBytes),
                RiskLevel = "منخفض",
                Items = selected.Select(item => new OperationPreviewItem
                {
                    Name = item.Name,
                    Location = item.OriginalPath,
                    Action = "استعادة من الحجر",
                    Safety = "سيتم تجاوز العنصر إذا كان المسار الأصلي مستخدمًا.",
                    SizeBytes = item.SizeBytes
                }).ToList()
            }))
        {
            return;
        }

        MessageBoxResult confirmation = !_settings.ConfirmDangerousOperations
            ? MessageBoxResult.Yes
            : ShowLocalizedMessage(
            $"سيتم استعادة {selected.Count:N0} عنصر إلى مكانه الأصلي. إذا كان المكان مستخدمًا حاليًا فسيتم تجاوز العنصر. هل تريد المتابعة؟",
            "تأكيد الاستعادة",
            MessageBoxButton.YesNo,
            MessageBoxImage.Question);

        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        try
        {
            SetBusy(true, "استعادة العناصر من الحجر...");
            QuarantineOperationResult result = await _quarantineService.RestoreAsync(selected, CreateProgress());
            await RecordActivityAsync(
                "استعادة عناصر الحجر",
                result.FailedItems > 0 ? "اكتمل بتحذيرات" : "نجاح",
                $"نجح: {result.SucceededItems:N0}، فشل: {result.FailedItems:N0}، تم تجاوز: {result.SkippedItems:N0}.",
                result.SucceededItems,
                result.BytesProcessed);
            await LoadQuarantineItemsAsync();
            await RefreshActivityAsync();
            ShowLocalizedMessage(
                BuildOperationMessage("تمت استعادة", result, ""),
                "نتيجة الاستعادة",
                MessageBoxButton.OK,
                result.FailedItems > 0 || result.SkippedItems > 0 ? MessageBoxImage.Information : MessageBoxImage.None);
        }
        catch (Exception ex)
        {
            HandleError("تعذر استعادة بعض العناصر.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void DeleteQuarantinePermanently_Click(object sender, RoutedEventArgs e)
    {
        List<QuarantineItem> selected = QuarantineItems.Where(item => item.IsSelected).ToList();
        if (selected.Count == 0)
        {
            ShowLocalizedMessage("حدد عنصرًا واحدًا على الأقل لحذفه.", "الحذف النهائي", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        long totalBytes = selected.Sum(item => item.SizeBytes);
        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = "حذف نهائي من الحجر",
                Description = "حذف العناصر المحددة نهائيًا من حجر البرنامج دون إمكانية الاستعادة.",
                ItemCount = selected.Count,
                EstimatedBytes = totalBytes,
                RiskLevel = "مرتفع",
                Items = selected.Select(item => new OperationPreviewItem
                {
                    Name = item.Name,
                    Location = item.OriginalPath,
                    Action = "حذف نهائي",
                    Safety = "لا يمكن التراجع بعد التنفيذ.",
                    SizeBytes = item.SizeBytes
                }).ToList()
            }))
        {
            return;
        }

        MessageBoxResult confirmation = !_settings.ConfirmDangerousOperations
            ? MessageBoxResult.Yes
            : ShowLocalizedMessage(
            $"سيتم حذف {selected.Count:N0} عنصر بحجم {SizeFormatter.Format(totalBytes, _settings.LanguageCode)} نهائيًا. لا يمكن التراجع عن هذه العملية. هل أنت متأكد؟",
            "تأكيد الحذف النهائي",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);

        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        try
        {
            SetBusy(true, "حذف العناصر نهائيًا من الحجر...");
            QuarantineOperationResult result = await _quarantineService.DeletePermanentlyAsync(selected, CreateProgress());
            await RecordActivityAsync(
                "حذف نهائي من الحجر",
                result.FailedItems > 0 ? "اكتمل بتحذيرات" : "نجاح",
                $"نجح: {result.SucceededItems:N0}، فشل: {result.FailedItems:N0}، تم تجاوز: {result.SkippedItems:N0}.",
                result.SucceededItems,
                result.BytesProcessed);
            await LoadQuarantineItemsAsync();
            await RefreshActivityAsync();
            ShowLocalizedMessage(
                BuildOperationMessage("تم حذف", result, "نهائيًا"),
                "نتيجة الحذف النهائي",
                MessageBoxButton.OK,
                result.FailedItems > 0 || result.SkippedItems > 0 ? MessageBoxImage.Information : MessageBoxImage.None);
        }
        catch (Exception ex)
        {
            HandleError("تعذر حذف بعض عناصر الحجر.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void OpenQuarantineFolder_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            Directory.CreateDirectory(QuarantineService.QuarantineRoot);
            Process.Start(new ProcessStartInfo(QuarantineService.QuarantineRoot) { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            HandleError("تعذر فتح مجلد الحجر.", ex);
        }
    }

    private async void RefreshProcesses_Click(object sender, RoutedEventArgs e)
        => await RefreshProcessesAsync();

    private async Task RefreshProcessesAsync()
    {
        try
        {
            SetBusy(true, "قراءة البرامج وقياس استخدام الذاكرة...");
            SystemMemorySnapshot memory = _systemMemoryService.Capture();
            List<ProcessInfoItem> allProcesses = await _processService.GetProcessesAsync();
            List<ProcessInfoItem> processes = allProcesses
                .Where(process => process.CanClose
                                  && process.WorkingSetBytes >= 20L * 1024L * 1024L
                                  && (!string.IsNullOrWhiteSpace(process.WindowTitle) || process.IsRecommended))
                .OrderByDescending(process => process.WorkingSetBytes)
                .Take(_settings.LowResourceMode ? 30 : 60)
                .ToList();

            Processes.Clear();
            foreach (ProcessInfoItem process in processes)
            {
                Processes.Add(process);
            }

            long totalWorkingSet = processes.Sum(process => process.WorkingSetBytes);
            int userPrograms = processes.Count;
            ProcessesSummaryText.Text = LocalizationService.Format(
                "@MemoryProcessSummary",
                _settings.LanguageCode,
                userPrograms,
                SizeFormatter.Format(totalWorkingSet, _settings.LanguageCode));
            UpdateMemoryDashboard(memory);
            await RefreshVirtualMemoryPanelAsync();
            SetStatus("تم تحديث قائمة البرامج وقياسات الذاكرة.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر قراءة البرامج أو قياسات الذاكرة.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void UpdateMemoryDashboard(SystemMemorySnapshot snapshot)
    {
        string code = _settings.LanguageCode;
        MemoryTotalText.Text = SizeFormatter.Format(snapshot.TotalPhysicalBytes, code);
        MemoryUsedText.Text = SizeFormatter.Format(snapshot.UsedPhysicalBytes, code);
        MemoryAvailableText.Text = SizeFormatter.Format(snapshot.AvailablePhysicalBytes, code);
        MemoryLoadText.Text = snapshot.MemoryLoadPercent.ToString("N0", LocalizationService.CultureFor(code)) + "%";
    }

    private void OptimizeMemory_Click(object sender, RoutedEventArgs e)
    {
        ShowLocalizedMessage(
            "لتبقى النسخة Lite واضحة وآمنة، أُلغي التحرير المؤقت للرام. اختر برنامجًا من القائمة ثم أغلقه لتحرير ذاكرته فعليًا.",
            "تخفيف الذاكرة",
            MessageBoxButton.OK,
            MessageBoxImage.Information);
    }

    private async void EndProcess_Click(object sender, RoutedEventArgs e)
    {
        if (ProcessesGrid.SelectedItem is not ProcessInfoItem item)
        {
            ShowLocalizedMessage("حدد عملية من القائمة أولًا.", "إغلاق عملية", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        if (item.ProcessId == Environment.ProcessId)
        {
            ShowLocalizedMessage("لا يمكن إغلاق برنامج التنظيف من هذه القائمة.", "إغلاق عملية", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        if (!item.CanClose)
        {
            ShowLocalizedMessage("هذه عملية تابعة لويندوز أو عملية محمية، ولن يسمح البرنامج بإغلاقها.", "إغلاق عملية", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = "إغلاق عملية",
                Description = "إنهاء العملية المحددة. قد يؤدي ذلك إلى فقدان بيانات غير محفوظة.",
                ItemCount = 1,
                EstimatedBytes = item.WorkingSetBytes,
                RiskLevel = "مرتفع",
                Items =
                [
                    new OperationPreviewItem
                    {
                        Name = item.Name,
                        Location = $"PID {item.ProcessId}",
                        Action = "إنهاء العملية",
                        Safety = "قد تفقد بيانات لم تُحفظ داخل البرنامج.",
                        SizeBytes = item.WorkingSetBytes
                    }
                ]
            }))
        {
            return;
        }

        MessageBoxResult confirmation = !_settings.ConfirmDangerousOperations
            ? MessageBoxResult.Yes
            : ShowLocalizedMessage(
            $"إغلاق العملية {item.Name} قد يؤدي إلى فقدان بيانات غير محفوظة. هل تريد المتابعة؟",
            "تأكيد إغلاق العملية",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);

        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        try
        {
            SetBusy(true, $"إغلاق العملية: {item.Name}");
            await _processService.EndProcessAsync(item.ProcessId);
            await RecordActivityAsync(
                "إغلاق عملية",
                "نجاح",
                $"تم إغلاق العملية {item.Name} (PID {item.ProcessId}).",
                1,
                item.WorkingSetBytes);
            await RefreshActivityAsync();
            SetStatus($"تم إغلاق العملية {item.Name}.");
            SetBusy(false);
            await RefreshProcessesAsync();
        }
        catch (Exception ex)
        {
            HandleError("تعذر إغلاق العملية. قد تكون محمية أو تحتاج إلى صلاحية مسؤول.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private static ProcessStartInfo CreateUninstallStartInfo(string commandLine)
    {
        string command = Environment.ExpandEnvironmentVariables(commandLine.Trim());
        if (string.IsNullOrWhiteSpace(command))
        {
            throw new InvalidOperationException("The uninstall command is empty.");
        }

        string fileName;
        string arguments;

        if (command.StartsWith('"'))
        {
            int closingQuote = command.IndexOf('"', 1);
            if (closingQuote <= 1)
            {
                throw new InvalidOperationException("The uninstall command contains invalid quotes.");
            }

            fileName = command[1..closingQuote];
            arguments = command[(closingQuote + 1)..].TrimStart();
        }
        else
        {
            int executableEnd = command.IndexOf(".exe", StringComparison.OrdinalIgnoreCase);
            if (executableEnd >= 0)
            {
                executableEnd += 4;
                fileName = command[..executableEnd].Trim();
                arguments = command[executableEnd..].TrimStart();
            }
            else
            {
                int firstSpace = command.IndexOf(' ');
                fileName = firstSpace < 0 ? command : command[..firstSpace];
                arguments = firstSpace < 0 ? string.Empty : command[(firstSpace + 1)..].TrimStart();
            }
        }

        string executableName = Path.GetFileNameWithoutExtension(fileName);
        if (string.Equals(executableName, "msiexec", StringComparison.OrdinalIgnoreCase)
            && arguments.TrimStart().StartsWith("/I", StringComparison.OrdinalIgnoreCase))
        {
            int leadingWhitespace = arguments.Length - arguments.TrimStart().Length;
            arguments = arguments[..leadingWhitespace] + "/X" + arguments[(leadingWhitespace + 2)..];
        }

        return new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            UseShellExecute = true,
            Verb = "runas"
        };
    }

    private void OpenLogs_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            Directory.CreateDirectory(AppLogger.LogDirectory);
            Process.Start(new ProcessStartInfo(AppLogger.LogDirectory) { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            HandleError("تعذر فتح مجلد السجل.", ex);
        }
    }

    private string BuildStartupOperationMessage(string action, StartupOperationResult result)
    {
        string message = $"{L(action)} {result.SucceededItems:N0} {L("عنصر")}.";
        if (result.SkippedItems > 0)
        {
            message += L($"\nتم تجاوز {result.SkippedItems:N0} عنصر لأنه محمي أو لأن حالته لم تتغير.");
        }

        if (result.FailedItems > 0)
        {
            message += L($"\nفشلت معالجة {result.FailedItems:N0} عنصر. راجع السجل، وشغّل البرنامج كمسؤول عند تعديل الخدمات أو عناصر كل المستخدمين.");
        }

        return message;
    }

    private string BuildOperationMessage(string action, QuarantineOperationResult result, string suffix)
    {
        string suffixText = string.IsNullOrWhiteSpace(suffix) ? string.Empty : " " + L(suffix);
        string message = $"{L(action)} {result.SucceededItems:N0} {L("عنصر")}{suffixText}.";
        if (result.BytesProcessed > 0)
        {
            message += L($"\nالحجم: {SizeFormatter.Format(result.BytesProcessed, _settings.LanguageCode)}.");
        }

        if (result.SkippedItems > 0)
        {
            message += L($"\nتم تجاوز {result.SkippedItems:N0} عنصر لأنه غير موجود أو لأن مساره الأصلي مستخدم.");
        }

        if (result.FailedItems > 0)
        {
            message += L($"\nفشلت معالجة {result.FailedItems:N0} عنصر. راجع السجل للتفاصيل.");
        }

        return message;
    }

    private void SetDiskScanUi(bool isScanning)
    {
        DiskCancelButton.IsEnabled = isScanning;
        DiskDuplicateScanCheckBox.IsEnabled = !isScanning;
        DiskPathBox.IsEnabled = !isScanning;
        foreach (object item in RootTabs.Items)
        {
            if (item is System.Windows.Controls.TabItem tab)
            {
                tab.IsEnabled = !isScanning || ReferenceEquals(tab, DiskAnalyzerTab);
            }
        }

        if (isScanning)
        {
            RootTabs.SelectedItem = DiskAnalyzerTab;
        }
    }

    private Progress<string> CreateProgress()
        => new(message => SetStatus(message));

    private string L(string? message)
        => LocalizationService.Translate(message, _settings.LanguageCode);

    private MessageBoxResult ShowLocalizedMessage(
        string message,
        string caption,
        MessageBoxButton buttons = MessageBoxButton.OK,
        MessageBoxImage image = MessageBoxImage.None)
        => MessageBox.Show(L(message), L(caption), buttons, image);

    private void SetBusy(bool isBusy, string? message = null, bool disableTabs = true)
    {
        BusyProgress.IsIndeterminate = isBusy;
        if (disableTabs)
        {
            RootTabs.IsEnabled = !isBusy;
        }
        if (!string.IsNullOrWhiteSpace(message))
        {
            StatusText.Text = L(message);
        }

        ScheduleLocalizationRefresh();
    }

    private void SetStatus(string message)
    {
        StatusText.Text = L(message);
        AppLogger.Info(message);
        ScheduleLocalizationRefresh();
    }

    private void ScheduleLocalizationRefresh()
    {
        if (_localizationRefreshPending || !IsLoaded)
        {
            return;
        }

        _localizationRefreshPending = true;
        Dispatcher.BeginInvoke(DispatcherPriority.ContextIdle, new Action(() =>
        {
            try
            {
                LocalizationService.Apply(this, _settings.LanguageCode);
            }
            finally
            {
                _localizationRefreshPending = false;
            }
        }));
    }

    private void HandleError(string userMessage, Exception exception)
    {
        AppLogger.Error(userMessage, exception);
        string? diagnosticPath = CrashReportService.CreateReport(exception, userMessage);
        StatusText.Text = L(userMessage);
        ShowLocalizedMessage(
            diagnosticPath is null
                ? userMessage
                : $"{userMessage}\n\nتم حفظ تقرير تشخيص محلي دون إرساله تلقائيًا:\n{diagnosticPath}",
            "خطأ",
            MessageBoxButton.OK,
            MessageBoxImage.Error);
    }
}
