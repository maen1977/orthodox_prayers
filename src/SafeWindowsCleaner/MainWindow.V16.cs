using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Diagnostics;
using System.Windows;
using Microsoft.Win32;
using SafeWindowsCleaner.Models;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner;

public partial class MainWindow
{
    private readonly InstallMonitorService _installMonitorService = new();
    private MonitoredUninstallCleanupService _monitoredUninstallCleanupService = null!;
    private RestorePointSession? _installMonitorRestoreSession;
    private string _selectedInstallMonitorSessionId = string.Empty;
    private bool _isRefreshingInstallMonitorSelection;

    public ObservableCollection<InstallMonitorSessionSummary> InstallMonitorSessions { get; } = [];
    public ObservableCollection<InstallChangeItem> InstallMonitorChanges { get; } = [];

    private async Task RefreshInstallMonitorSessionsAsync(string? selectSessionId = null)
    {
        List<InstallMonitorSessionSummary> sessions = await _installMonitorService.GetSessionsAsync();
        InstallMonitorSessions.Clear();
        foreach (InstallMonitorSessionSummary session in sessions)
        {
            InstallMonitorSessions.Add(session);
        }

        InstallMonitorSessionSummary? selected = sessions.FirstOrDefault(session =>
            string.Equals(session.SessionId, selectSessionId, StringComparison.OrdinalIgnoreCase))
            ?? sessions.FirstOrDefault(session =>
                string.Equals(session.SessionId, _selectedInstallMonitorSessionId, StringComparison.OrdinalIgnoreCase))
            ?? sessions.FirstOrDefault();

        _isRefreshingInstallMonitorSelection = true;
        try
        {
            InstallSessionsGrid.SelectedItem = selected;
        }
        finally
        {
            _isRefreshingInstallMonitorSelection = false;
        }
        _selectedInstallMonitorSessionId = selected?.SessionId ?? string.Empty;
        await LoadInstallMonitorChangesAsync(selected);
        UpdateInstallMonitorUi();
    }

    private async Task LoadInstallMonitorChangesAsync(InstallMonitorSessionSummary? session)
    {
        InstallMonitorChanges.Clear();
        if (session is null || session.Status != InstallMonitorStatus.Completed)
        {
            InstallChangesSummaryText.Text = L(session is null
                ? "اختر جلسة مكتملة لعرض التغييرات."
                : "هذه الجلسة ليست مكتملة ولا تحتوي على مقارنة نهائية.");
            return;
        }

        List<InstallChangeItem> changes = await _installMonitorService.GetChangesAsync(session.SessionId);
        foreach (InstallChangeItem change in changes)
        {
            InstallMonitorChanges.Add(change);
        }

        int safe = changes.Count(change => change.IsSafeToQuarantine && change.ExistsNow);
        InstallChangesSummaryText.Text = L($"{changes.Count:N0} تغيير — مجلدات يمكن نقلها للحجر بعد المراجعة: {safe:N0}.");
    }

    private void UpdateInstallMonitorUi()
    {
        bool active = _installMonitorService.HasActiveSession;
        FinishInstallMonitoringButton.IsEnabled = active;
        CancelInstallMonitoringButton.IsEnabled = active;
        StartMonitoredInstallButton.IsEnabled = !active;
        InstallMonitorActiveStatusText.Text = L(active
            ? $"جلسة مراقبة فعالة: {_installMonitorService.ActiveSessionId}. أكمل تثبيت البرنامج ثم اضغط «إنهاء المراقبة والمقارنة»."
            : "لا توجد جلسة مراقبة فعالة.");

        InstallMonitorSessionSummary? selected = InstallSessionsGrid.SelectedItem as InstallMonitorSessionSummary;
        OpenInstallReportButton.IsEnabled = selected is not null && File.Exists(selected.ReportPath);
        AnalyzeInstallResidualsButton.IsEnabled = selected?.Status == InstallMonitorStatus.Completed;
        UninstallMonitoredAppButton.IsEnabled = selected?.Status == InstallMonitorStatus.Completed
                                                && !string.IsNullOrWhiteSpace(selected.UninstallString);
        DeleteInstallSessionButton.IsEnabled = selected is not null
                                               && !string.Equals(selected.SessionId, _installMonitorService.ActiveSessionId, StringComparison.OrdinalIgnoreCase);
    }

    private async void StartMonitoredInstall_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = L("اختر ملف تثبيت لمراقبته"),
            Filter = L("ملفات التثبيت (*.exe;*.msi)|*.exe;*.msi|ملفات EXE (*.exe)|*.exe|حزم MSI (*.msi)|*.msi"),
            CheckFileExists = true,
            Multiselect = false
        };
        if (dialog.ShowDialog(this) != true)
        {
            return;
        }

        string installerPath = dialog.FileName;
        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = "تثبيت برنامج مع المراقبة",
                Description = "التقاط لقطة للنظام، مراقبة تغييرات الملفات، ثم تشغيل ملف التثبيت المحدد.",
                ItemCount = 1,
                RequiresAdministrator = true,
                RiskLevel = "متوسط",
                Items =
                [
                    new OperationPreviewItem
                    {
                        Name = Path.GetFileName(installerPath),
                        Location = installerPath,
                        Action = "تشغيل المثبت مع مراقبة التغييرات",
                        Safety = "لن يحذف المراقب أي عنصر تلقائيًا. التغييرات ستظهر في تقرير للمراجعة.",
                        SizeBytes = new FileInfo(installerPath).Length
                    }
                ]
            }))
        {
            return;
        }

        MessageBoxResult confirmation = !_settings.ConfirmDangerousOperations
            ? MessageBoxResult.Yes
            : ShowLocalizedMessage(
                L("سيأخذ البرنامج لقطة انتقائية للنظام ويبدأ مراقبة المجلدات المعتمدة، ثم يشغّل ملف التثبيت بصلاحية المسؤول.\n\n") +
                L("أغلق التطبيقات غير الضرورية لتقليل التغييرات غير المرتبطة، وبعد انتهاء المثبت اضغط «إنهاء المراقبة والمقارنة». هل تريد المتابعة؟"),
                "تثبيت مع المراقبة",
                MessageBoxButton.YesNo,
                MessageBoxImage.Warning);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        RestorePointDecision restoreDecision = await PrepareRestorePointAsync(
            $"Safe Windows Cleaner — Before monitored install {Path.GetFileName(installerPath)}");
        if (!restoreDecision.ContinueOperation)
        {
            SetStatus("تم إلغاء التثبيت المراقب.");
            return;
        }

        _installMonitorRestoreSession = restoreDecision.Session;
        try
        {
            SetBusy(true, "تجهيز جلسة مراقبة التثبيت...");
            InstallMonitorStartResult result = await _installMonitorService.BeginAndLaunchAsync(installerPath, CreateProgress());
            await RecordActivityAsync(
                "تثبيت مع المراقبة",
                "بدأت",
                $"بدأت جلسة {result.Session.SessionId} لملف {result.Session.InstallerName}. PID: {result.InstallerProcessId}.",
                1,
                restorePointSequence: _installMonitorRestoreSession?.SequenceNumber ?? 0);
            await RefreshActivityAsync();
            await RefreshInstallMonitorSessionsAsync(result.Session.SessionId);
            RootTabs.SelectedItem = InstallMonitorTab;
            SetStatus("بدأت مراقبة التثبيت. أكمل خطوات المثبت ثم أنهِ المراقبة.");

            if (result.Warnings.Count > 0)
            {
                ShowLocalizedMessage(
                    L("بدأت المراقبة، لكن توجد تنبيهات:\n\n") +
                    string.Join("\n", result.Warnings.Distinct().Take(8).Select(L)),
                    "تنبيهات مراقبة التثبيت",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
            }
        }
        catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)
        {
            await FinishInstallMonitorRestorePointAsync(cancelled: true);
            await RecordActivityAsync("تثبيت مع المراقبة", "ألغيت", "ألغى المستخدم تشغيل ملف التثبيت بصلاحية المسؤول.");
            SetStatus("تم إلغاء تشغيل المثبت.");
        }
        catch (Exception ex)
        {
            await FinishInstallMonitorRestorePointAsync(cancelled: true);
            await RecordActivityAsync("تثبيت مع المراقبة", "فشل", ex.Message);
            HandleError("تعذر بدء جلسة مراقبة التثبيت.", ex);
        }
        finally
        {
            SetBusy(false);
            UpdateInstallMonitorUi();
        }
    }

    private async void FinishInstallMonitoring_Click(object sender, RoutedEventArgs e)
    {
        if (!_installMonitorService.HasActiveSession)
        {
            ShowLocalizedMessage("لا توجد جلسة مراقبة فعالة.", "مراقبة التثبيت", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        MessageBoxResult confirmation = ShowLocalizedMessage(
            "تأكد من انتهاء برنامج التثبيت وأي نوافذ فرعية تابعة له. سيوقف البرنامج المراقبة الآن ويقارن النظام باللقطة السابقة.",
            "إنهاء المراقبة",
            MessageBoxButton.OKCancel,
            MessageBoxImage.Question);
        if (confirmation != MessageBoxResult.OK)
        {
            return;
        }

        try
        {
            SetBusy(true, "إنهاء المراقبة ومقارنة التغييرات...");
            InstallMonitorCompletionResult result = await _installMonitorService.CompleteActiveSessionAsync(CreateProgress());
            await FinishInstallMonitorRestorePointAsync(cancelled: false);
            await RecordActivityAsync(
                "تثبيت مع المراقبة",
                "اكتملت",
                $"اكتملت جلسة {result.Session.SessionId} وتم رصد {result.Changes.Count:N0} تغيير.",
                result.Changes.Count,
                result.Changes.Sum(change => change.SizeBytes));
            await RefreshActivityAsync();
            await RefreshInstalledAppsAsync();
            await RefreshInstallMonitorSessionsAsync(result.Session.SessionId);
            RootTabs.SelectedItem = InstallMonitorTab;
            SetStatus($"اكتملت المراقبة وتم رصد {result.Changes.Count:N0} تغيير.");

            string application = string.IsNullOrWhiteSpace(result.Session.DetectedApplicationName)
                ? "لم يُحدد البرنامج الجديد تلقائيًا."
                : $"البرنامج المكتشف: {result.Session.DetectedApplicationName}.";
            ShowLocalizedMessage(
                $"اكتملت المقارنة.\n{application}\nعدد التغييرات: {result.Changes.Count:N0}.\n\nراجع النتائج قبل تحديد أي مجلد للحجر.",
                "نتيجة مراقبة التثبيت",
                MessageBoxButton.OK,
                result.Warnings.Count > 0 ? MessageBoxImage.Information : MessageBoxImage.None);
        }
        catch (OperationCanceledException)
        {
            SetStatus("تم إلغاء المقارنة قبل اكتمالها.");
        }
        catch (Exception ex)
        {
            await FinishInstallMonitorRestorePointAsync(cancelled: true);
            await RecordActivityAsync("تثبيت مع المراقبة", "فشل", ex.Message);
            HandleError("تعذر إكمال مقارنة جلسة التثبيت.", ex);
        }
        finally
        {
            SetBusy(false);
            UpdateInstallMonitorUi();
        }
    }

    private async void CancelInstallMonitoring_Click(object sender, RoutedEventArgs e)
    {
        if (!_installMonitorService.HasActiveSession)
        {
            return;
        }

        MessageBoxResult confirmation = ShowLocalizedMessage(
            "سيتم إيقاف المراقبة وإلغاء الجلسة، لكن البرنامج لن يغلق ملف التثبيت الذي يعمل حاليًا. هل تريد المتابعة؟",
            "إلغاء المراقبة",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        try
        {
            string sessionId = _installMonitorService.ActiveSessionId;
            await _installMonitorService.CancelActiveSessionAsync();
            await FinishInstallMonitorRestorePointAsync(cancelled: true);
            await RecordActivityAsync("تثبيت مع المراقبة", "ألغيت", $"ألغيت جلسة المراقبة {sessionId}.");
            await RefreshActivityAsync();
            await RefreshInstallMonitorSessionsAsync(sessionId);
            SetStatus("تم إيقاف جلسة مراقبة التثبيت.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر إلغاء جلسة المراقبة.", ex);
        }
        finally
        {
            UpdateInstallMonitorUi();
        }
    }

    private async void RefreshInstallSessions_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            SetBusy(true, "تحديث جلسات مراقبة التثبيت...");
            await RefreshInstallMonitorSessionsAsync();
            SetStatus("تم تحديث جلسات مراقبة التثبيت.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر تحديث جلسات مراقبة التثبيت.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void InstallSessionsGrid_SelectionChanged(object sender, System.Windows.Controls.SelectionChangedEventArgs e)
    {
        if (_isRefreshingInstallMonitorSelection)
        {
            return;
        }

        if (InstallSessionsGrid.SelectedItem is not InstallMonitorSessionSummary session)
        {
            _selectedInstallMonitorSessionId = string.Empty;
            InstallMonitorChanges.Clear();
            UpdateInstallMonitorUi();
            return;
        }

        _selectedInstallMonitorSessionId = session.SessionId;
        try
        {
            await LoadInstallMonitorChangesAsync(session);
        }
        catch (Exception ex)
        {
            HandleError("تعذر قراءة تغييرات جلسة التثبيت.", ex);
        }
        UpdateInstallMonitorUi();
    }

    private void OpenInstallReport_Click(object sender, RoutedEventArgs e)
    {
        InstallMonitorSessionSummary? session = InstallSessionsGrid.SelectedItem as InstallMonitorSessionSummary;
        if (session is null
            || string.IsNullOrWhiteSpace(session.ReportPath)
            || !File.Exists(session.ReportPath))
        {
            ShowLocalizedMessage("لا يوجد تقرير HTML لهذه الجلسة.", "تقرير التثبيت", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        OpenPathWithShell(session.ReportPath, "تعذر فتح تقرير مراقبة التثبيت.");
    }

    private void OpenInstallMonitorFolder_Click(object sender, RoutedEventArgs e)
    {
        Directory.CreateDirectory(InstallMonitorService.MonitorRoot);
        OpenPathWithShell(InstallMonitorService.MonitorRoot, "تعذر فتح مجلد جلسات مراقبة التثبيت.");
    }

    private async void AnalyzeInstallResiduals_Click(object sender, RoutedEventArgs e)
    {
        if (InstallSessionsGrid.SelectedItem is not InstallMonitorSessionSummary session
            || session.Status != InstallMonitorStatus.Completed)
        {
            ShowLocalizedMessage("اختر جلسة مكتملة أولًا.", "تحليل البقايا", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        try
        {
            SetBusy(true, "فحص العناصر التي ما زالت موجودة من جلسة التثبيت...");
            MonitoredResidualAnalysisResult result = await _installMonitorService.AnalyzeResidualsAsync(session.SessionId);
            InstallMonitorChanges.Clear();
            foreach (InstallChangeItem change in result.Changes)
            {
                InstallMonitorChanges.Add(change);
            }

            InstallChangesSummaryText.Text =
                L($"البقايا الحالية — ملفات/مجلدات: {result.ExistingFileSystemItems:N0}، خدمات: {result.ExistingServices:N0}، مهام: {result.ExistingScheduledTasks:N0}، ريجستري: {result.ExistingRegistryItems:N0}.");
            await RecordActivityAsync(
                "تحليل بقايا تثبيت مراقب",
                "اكتمل",
                InstallChangesSummaryText.Text,
                result.ExistingFileSystemItems + result.ExistingServices + result.ExistingScheduledTasks + result.ExistingRegistryItems);
            await RefreshActivityAsync();
            SetStatus("اكتمل تحليل البقايا الحالية للجلسة.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر تحليل بقايا جلسة التثبيت.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void UninstallMonitoredApp_Click(object sender, RoutedEventArgs e)
    {
        if (InstallSessionsGrid.SelectedItem is not InstallMonitorSessionSummary session
            || session.Status != InstallMonitorStatus.Completed)
        {
            ShowLocalizedMessage("اختر جلسة مكتملة أولًا.", "إزالة مراقبة", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        if (string.IsNullOrWhiteSpace(session.UninstallString))
        {
            ShowLocalizedMessage("لم يُكتشف أمر إزالة رسمي لهذه الجلسة.", "إزالة مراقبة", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        string appName = string.IsNullOrWhiteSpace(session.DetectedApplicationName)
            ? session.InstallerName
            : session.DetectedApplicationName;

        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = "إزالة برنامج مراقب",
                Description = $"تشغيل أداة الإزالة الرسمية لبرنامج {appName} ثم إزالة البقايا المسجلة الآمنة من الملفات والريجستري والخدمات والمهام.",
                ItemCount = 1,
                RequiresAdministrator = true,
                RiskLevel = "متوسط",
                Items =
                [
                    new OperationPreviewItem
                    {
                        Name = appName,
                        Location = session.InstallerPath,
                        Action = "تشغيل الإزالة الرسمية ثم تنظيف كل البقايا المراقبة الآمنة",
                        Safety = "الملفات والمجلدات تنتقل للحجر، والريجستري والخدمات والمهام تُزال فقط عندما تكون إضافات مسجلة باسم البرنامج."
                    }
                ]
            }))
        {
            return;
        }

        MessageBoxResult confirmation = ShowLocalizedMessage(
            $"سيتم تشغيل أداة الإزالة الرسمية لـ {appName}. بعد انتهائها سيحذف البرنامج تلقائيًا كل البقايا الآمنة التي سجلها وقت التثبيت، مع نقل الملفات إلى الحجر. هل تريد المتابعة؟",
            "إزالة برنامج مراقب",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        RestorePointDecision restoreDecision = await PrepareRestorePointAsync(
            $"Safe Windows Cleaner — Before monitored uninstall {appName}",
            uninstallOperation: true);
        if (!restoreDecision.ContinueOperation)
        {
            return;
        }

        bool cancelRestore = true;
        try
        {
            Process? process = Process.Start(InstallMonitorService.CreateUninstallStartInfo(session.UninstallString));
            if (process is null)
            {
                throw new InvalidOperationException("لم تبدأ أداة الإزالة الرسمية.");
            }

            SetBusy(true, "أكمل خطوات إزالة البرنامج في النافذة المفتوحة...");
            await process.WaitForExitAsync();
            int uninstallExitCode = process.ExitCode;
            if (uninstallExitCode is not 0 and not 1641 and not 3010)
            {
                throw new InvalidOperationException($"أداة الإزالة انتهت برمز {uninstallExitCode}. لم تُحذف البقايا تلقائيًا حتى لا يتضرر برنامج ما زال مثبتًا.");
            }

            SetBusy(true, "التحقق من اكتمال إزالة البرنامج...");
            bool removedFromInstalledApps = await WaitForMonitoredApplicationRemovalAsync(session);
            if (!removedFromInstalledApps)
            {
                throw new InvalidOperationException("ما زال البرنامج ظاهرًا في قائمة البرامج المثبتة. تم إيقاف تنظيف البقايا للحماية؛ أكمل الإزالة الرسمية ثم أعد المحاولة.");
            }

            cancelRestore = false;
            SetBusy(true, "تنظيف البقايا المسجلة للبرنامج...");
            MonitoredUninstallCleanupResult cleanup = await _monitoredUninstallCleanupService.CleanupAsync(
                session.SessionId,
                CreateProgress());
            MonitoredResidualAnalysisResult result = await _installMonitorService.AnalyzeResidualsAsync(session.SessionId);
            InstallMonitorChanges.Clear();
            foreach (InstallChangeItem change in result.Changes)
            {
                InstallMonitorChanges.Add(change);
            }
            InstallChangesSummaryText.Text =
                L($"حُذفت البقايا — مجلدات للحجر: {cleanup.DirectoriesQuarantined:N0}، ملفات للحجر: {cleanup.FilesQuarantined:N0}، ريجستري: {cleanup.RegistryItemsRemoved:N0}، خدمات: {cleanup.ServicesRemoved:N0}، مهام: {cleanup.ScheduledTasksRemoved:N0}. المتبقي للمراجعة: ملفات/مجلدات {result.ExistingFileSystemItems:N0}، خدمات {result.ExistingServices:N0}، مهام {result.ExistingScheduledTasks:N0}، ريجستري {result.ExistingRegistryItems:N0}.");

            await RecordActivityAsync(
                "حذف برنامج وكل بقاياه المراقبة",
                cleanup.FailedItems > 0 ? "اكتمل بتحذيرات" : "نجاح",
                $"اكتملت إزالة {appName} برمز خروج {uninstallExitCode}. {InstallChangesSummaryText.Text}",
                cleanup.TotalRemovedItems,
                cleanup.BytesQuarantined,
                restorePointSequence: restoreDecision.Session?.SequenceNumber ?? 0);
            await RefreshActivityAsync();
            await RefreshInstalledAppsAsync();
            await RefreshQuarantineAsync();
            SetStatus("اكتملت إزالة البرنامج وتنظيف بقاياه المراقبة.");
        }
        catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)
        {
            await RecordActivityAsync("إزالة برنامج مراقب", "ألغيت", "ألغى المستخدم طلب صلاحية المسؤول.");
            SetStatus("تم إلغاء أداة الإزالة.");
        }
        catch (Exception ex)
        {
            await RecordActivityAsync("إزالة برنامج مراقب", "فشل", ex.Message);
            HandleError("تعذر إكمال إزالة البرنامج المراقب.", ex);
        }
        finally
        {
            await FinishRestorePointAsync(restoreDecision.Session, cancelRestore);
            SetBusy(false);
        }
    }

    private async Task<bool> WaitForMonitoredApplicationRemovalAsync(
        InstallMonitorSessionSummary session,
        CancellationToken cancellationToken = default)
    {
        string expectedName = (session.DetectedApplicationName ?? string.Empty).Trim();
        InstallMonitorManifest manifest = await _installMonitorService.GetManifestAsync(session.SessionId, cancellationToken);
        string expectedPublisher = (manifest.DetectedPublisher ?? string.Empty).Trim();
        if (string.IsNullOrWhiteSpace(expectedName))
        {
            // There is no stable registry identity to verify; a successful official uninstaller exit code is the best signal available.
            await Task.Delay(1200, cancellationToken);
            return true;
        }

        for (int attempt = 0; attempt < 45; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            List<InstalledApp> apps = await _installedAppsService.GetInstalledAppsAsync(cancellationToken);
            bool stillInstalled = apps.Any(app =>
                string.Equals(app.DisplayName.Trim(), expectedName, StringComparison.OrdinalIgnoreCase)
                && (string.IsNullOrWhiteSpace(expectedPublisher)
                    || string.IsNullOrWhiteSpace(app.Publisher)
                    || string.Equals(app.Publisher.Trim(), expectedPublisher, StringComparison.OrdinalIgnoreCase)));
            if (!stillInstalled)
            {
                return true;
            }

            await Task.Delay(2000, cancellationToken);
        }

        return false;
    }

    private async void QuarantineMonitoredDirectories_Click(object sender, RoutedEventArgs e)
    {
        List<InstallChangeItem> selected = InstallMonitorChanges
            .Where(change => change.IsSelected && change.IsSafeToQuarantine && change.ExistsNow && change.IsDirectory)
            .ToList();
        if (selected.Count == 0)
        {
            ShowLocalizedMessage("حدد مجلد تطبيق آمنًا واحدًا على الأقل. عناصر الريجستري والخدمات والملفات الفردية للمراجعة فقط.", "الحجر", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        var leftovers = selected.Select(change => new LeftoverItem
        {
            Name = change.Name,
            Path = change.Location,
            Location = "@MonitoredInstallationSession",
            SizeBytes = change.SizeBytes,
            ConfidenceScore = 100,
            MatchReason = "@MonitoredRootFolderCreated",
            IsQuarantinable = true,
            IsSelected = true
        }).ToList();

        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = "نقل بقايا تثبيت مراقب إلى الحجر",
                Description = "نقل مجلدات التطبيقات المحددة إلى حجر قابل للاستعادة.",
                ItemCount = leftovers.Count,
                EstimatedBytes = leftovers.Sum(item => item.SizeBytes),
                RequiresAdministrator = leftovers.Any(item => item.Path.StartsWith(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), StringComparison.OrdinalIgnoreCase)),
                RiskLevel = "متوسط",
                Items = leftovers.Select(item => new OperationPreviewItem
                {
                    Name = item.Name,
                    Location = item.Path,
                    Action = "نقل المجلد إلى الحجر",
                    Safety = item.MatchReason,
                    SizeBytes = item.SizeBytes
                }).ToList()
            }))
        {
            return;
        }

        string list = string.Join("\n", leftovers.Take(8).Select(item => $"• {item.Path}"));
        MessageBoxResult confirmation = ShowLocalizedMessage(
            $"سيتم نقل المجلدات التالية إلى الحجر القابل للاستعادة:\n\n{list}\n\nراجع أن البرنامج أُزيل وأن هذه المجلدات لا تحتوي بيانات تريد الاحتفاظ بها.",
            "تأكيد النقل إلى الحجر",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        try
        {
            SetBusy(true, "نقل مجلدات التثبيت المراقب إلى الحجر...");
            QuarantineOperationResult result = await _quarantineService.QuarantineAsync(leftovers, CreateProgress());
            await RecordActivityAsync(
                "حجر بقايا تثبيت مراقب",
                result.FailedItems > 0 ? "اكتمل بتحذيرات" : "نجاح",
                $"نجح: {result.SucceededItems:N0}، فشل: {result.FailedItems:N0}، تجاوز: {result.SkippedItems:N0}.",
                result.SucceededItems,
                result.BytesProcessed);
            await RefreshActivityAsync();
            await RefreshQuarantineAsync();
            if (InstallSessionsGrid.SelectedItem is InstallMonitorSessionSummary session)
            {
                await LoadInstallMonitorChangesAsync(session);
            }
            ShowLocalizedMessage(BuildOperationMessage("تم نقل", result, "إلى الحجر"), "نتيجة الحجر", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            HandleError("تعذر نقل بعض المجلدات إلى الحجر.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void DeleteInstallSession_Click(object sender, RoutedEventArgs e)
    {
        if (InstallSessionsGrid.SelectedItem is not InstallMonitorSessionSummary session)
        {
            return;
        }

        MessageBoxResult confirmation = ShowLocalizedMessage(
            $"سيتم حذف سجل جلسة {session.InstallerName} وتقاريرها فقط. لن تُحذف أي ملفات تابعة للبرنامج. هل تريد المتابعة؟",
            "حذف سجل الجلسة",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        try
        {
            await _installMonitorService.DeleteSessionAsync(session.SessionId);
            await RecordActivityAsync("حذف سجل مراقبة تثبيت", "نجاح", $"حُذف سجل الجلسة {session.SessionId}.");
            await RefreshActivityAsync();
            _selectedInstallMonitorSessionId = string.Empty;
            await RefreshInstallMonitorSessionsAsync();
            SetStatus("تم حذف سجل جلسة المراقبة.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر حذف سجل جلسة المراقبة.", ex);
        }
    }

    private async Task FinishInstallMonitorRestorePointAsync(bool cancelled)
    {
        RestorePointSession? session = _installMonitorRestoreSession;
        _installMonitorRestoreSession = null;
        await FinishRestorePointAsync(session, cancelled);
    }

    private void HandleInstallMonitorWindowClosing(CancelEventArgs e)
    {
        if (!_installMonitorService.HasActiveSession)
        {
            _installMonitorService.Dispose();
            return;
        }

        MessageBoxResult result = ShowLocalizedMessage(
            "توجد جلسة مراقبة تثبيت فعالة. إغلاق البرنامج سيوقف المراقبة ويسجل الجلسة كملغاة، ولن يغلق المثبت نفسه. هل تريد إغلاق البرنامج؟",
            "جلسة مراقبة فعالة",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);
        if (result != MessageBoxResult.Yes)
        {
            e.Cancel = true;
            return;
        }

        try
        {
            _installMonitorService.CancelActiveSessionOnShutdown();
            if (_installMonitorRestoreSession is not null)
            {
                _restorePointService.Complete(_installMonitorRestoreSession, cancelled: true);
                _installMonitorRestoreSession = null;
            }
        }
        catch (Exception ex)
        {
            AppLogger.Error("Could not close the active install-monitor session cleanly.", ex);
        }
        finally
        {
            _installMonitorService.Dispose();
        }
    }
}
