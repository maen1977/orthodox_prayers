using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Windows;
using SafeWindowsCleaner.Models;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner;

public partial class MainWindow
{
    private readonly ActivityLogService _activityLogService = new();
    private readonly PreviewReportService _previewReportService = new();
    private readonly RestorePointService _restorePointService = new();
    private readonly OperationSessionService _operationSessionService = new();
    private string _latestPreviewHtmlPath = string.Empty;

    public ObservableCollection<ActivityLogEntry> ActivityEntries { get; } = [];

    private async Task<bool> HandlePreviewOnlyAsync(OperationPreview preview)
    {
        Guid operationSessionId = await _operationSessionService.CreatePlanAsync(preview);
        if (_settings.PreviewOnlyMode)
        {
            PreviewReportResult report = await _previewReportService.CreateAsync(preview);
            _latestPreviewHtmlPath = report.HtmlPath;
            PreviewStatusText.Text = L($"تم إنشاء تقرير معاينة فقط: {Path.GetFileName(report.HtmlPath)}");
            PreviewModeStatusText.Text = L("وضع المعاينة فقط مفعّل — لن تُنفّذ العمليات الحساسة.");
            await RecordActivityAsync(
                preview.Operation,
                "معاينة فقط",
                $"تم إنشاء تقرير ولم يُنفّذ أي تغيير. التقرير: {Path.GetFileName(report.HtmlPath)}",
                preview.ItemCount,
                preview.EstimatedBytes);
            await RefreshActivityAsync();
            RootTabs.SelectedItem = PreviewActivityTab;

            await _operationSessionService.UpdateStatusAsync(
                operationSessionId, OperationSessionStatus.PreviewOnly, "تم إنشاء تقرير معاينة دون تنفيذ تغييرات.");
            ShowLocalizedMessage(
                $"تم إنشاء تقرير معاينة ولم يُنفّذ البرنامج أي تغيير.\n\n{report.HtmlPath}",
                "وضع المعاينة فقط",
                MessageBoxButton.OK,
                MessageBoxImage.Information);
            return true;
        }

        if (preview.RequiresAdministrator && !ElevationService.IsAdministrator)
        {
            MessageBoxResult choice = ShowLocalizedMessage(
                "هذه العملية تحتاج صلاحية مسؤول، بينما الواجهة تعمل الآن بصلاحية عادية لحماية الجهاز. سيُعاد فتح البرنامج بصلاحية مسؤول لهذه العملية فقط. هل تريد المتابعة؟",
                "صلاحية مسؤول مطلوبة",
                MessageBoxButton.YesNo,
                MessageBoxImage.Information);
            if (choice == MessageBoxResult.Yes)
            {
                string navigation = (RootTabs.SelectedItem as FrameworkElement)?.Name ?? string.Empty;
                if (ElevationService.TryRelaunchElevated(navigation))
                {
                    await _operationSessionService.UpdateStatusAsync(
                        operationSessionId, OperationSessionStatus.ElevationRequested, "طُلبت صلاحية مسؤول عند الحاجة.");
                    await RecordActivityAsync(preview.Operation, "طلب صلاحية", "أعيد تشغيل الواجهة بصلاحية مسؤول لإكمال العملية.");
                    Close();
                }
            }

            return true;
        }

        await _operationSessionService.UpdateStatusAsync(
            operationSessionId, OperationSessionStatus.Approved, "تمت الموافقة على الخطة وبدأت مرحلة التأكيد والتنفيذ.");
        return false;
    }

    private async Task<RestorePointDecision> PrepareRestorePointAsync(string description, bool uninstallOperation = false)
    {
        if (!_settings.CreateRestorePointBeforeDeepChanges)
        {
            RestorePointStatusText.Text = L("إنشاء نقطة الاستعادة معطّل من الإعدادات.");
            return new(true, null);
        }

        RestorePointSessionResult result = await _restorePointService.BeginAsync(description, uninstallOperation);
        RestorePointStatusText.Text = L(result.Message);
        if (result.Succeeded && result.Session is not null)
        {
            await RecordActivityAsync("نقطة استعادة", "نجاح", result.Message, restorePointSequence: result.Session.SequenceNumber);
            return new(true, result.Session);
        }

        await RecordActivityAsync("نقطة استعادة", "تعذر الإنشاء", result.Message);
        MessageBoxResult choice = ShowLocalizedMessage(
            result.Message + "\n\nهل تريد متابعة العملية بدون نقطة استعادة؟",
            "تعذر إنشاء نقطة استعادة",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);
        return new(choice == MessageBoxResult.Yes, null);
    }

    private async Task FinishRestorePointAsync(RestorePointSession? session, bool cancelled = false)
    {
        if (session is null)
        {
            return;
        }

        RestorePointCompletionResult result = await _restorePointService.CompleteAsync(session, cancelled);
        RestorePointStatusText.Text = L(result.Message);
        await RecordActivityAsync(
            "نقطة استعادة",
            result.Succeeded ? "اكتملت" : "تحذير",
            result.Message,
            restorePointSequence: session.SequenceNumber);
    }

    private async Task RecordActivityAsync(
        string operation,
        string status,
        string summary,
        int itemCount = 0,
        long bytesAffected = 0,
        long restorePointSequence = 0)
    {
        try
        {
            await _activityLogService.AppendAsync(
                operation,
                status,
                summary,
                itemCount,
                bytesAffected,
                restorePointSequence);
        }
        catch (Exception ex)
        {
            AppLogger.Error("Could not append activity record.", ex);
        }
    }

    private async Task RefreshActivityAsync()
    {
        List<ActivityLogEntry> entries = await _activityLogService.GetEntriesAsync();
        ActivityEntries.Clear();
        foreach (ActivityLogEntry entry in entries)
        {
            ActivityEntries.Add(entry);
        }

        ActivitySummaryText.Text = L(entries.Count == 0
            ? "لم تُسجّل عمليات بعد."
            : $"يعرض آخر {entries.Count:N0} عملية. لكل سجل بصمة مرتبطة بالسجل السابق.");
    }

    private async void RefreshActivity_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            SetBusy(true, "تحديث سجل النشاط...");
            await RefreshActivityAsync();
            SetStatus("تم تحديث سجل النشاط.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر قراءة سجل النشاط.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void VerifyActivityLog_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            SetBusy(true, "التحقق من سلسلة بصمات سجل النشاط...");
            ActivityLogVerificationResult result = await _activityLogService.VerifyAsync();
            ActivityVerificationText.Text = L(result.Message);
            ShowLocalizedMessage(
                result.Message,
                "التحقق من سجل النشاط",
                MessageBoxButton.OK,
                result.IsValid ? MessageBoxImage.Information : MessageBoxImage.Warning);
        }
        catch (Exception ex)
        {
            HandleError("تعذر التحقق من سجل النشاط.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void OpenLatestPreview_Click(object sender, RoutedEventArgs e)
    {
        if (string.IsNullOrWhiteSpace(_latestPreviewHtmlPath) || !File.Exists(_latestPreviewHtmlPath))
        {
            ShowLocalizedMessage("لا يوجد تقرير معاينة حديث لفتحه.", "تقرير المعاينة", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        OpenPathWithShell(_latestPreviewHtmlPath, "تعذر فتح تقرير المعاينة.");
    }

    private void OpenReportsFolder_Click(object sender, RoutedEventArgs e)
    {
        Directory.CreateDirectory(PreviewReportService.ReportsDirectory);
        OpenPathWithShell(PreviewReportService.ReportsDirectory, "تعذر فتح مجلد التقارير.");
    }

    private void OpenDiagnosticsFolder_Click(object sender, RoutedEventArgs e)
    {
        Directory.CreateDirectory(CrashReportService.DiagnosticsDirectory);
        OpenPathWithShell(CrashReportService.DiagnosticsDirectory, "تعذر فتح مجلد التشخيص.");
    }

    private void OpenActivityFolder_Click(object sender, RoutedEventArgs e)
    {
        Directory.CreateDirectory(ActivityLogService.ActivityDirectory);
        OpenPathWithShell(ActivityLogService.ActivityDirectory, "تعذر فتح مجلد سجل النشاط.");
    }

    private void OpenPathWithShell(string path, string errorMessage)
    {
        try
        {
            Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            AppLogger.Error(errorMessage, ex);
            ShowLocalizedMessage(errorMessage, "فتح ملف أو مجلد", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }


    private void LoadLatestPreviewReport()
    {
        try
        {
            if (!Directory.Exists(PreviewReportService.ReportsDirectory))
            {
                PreviewStatusText.Text = L("لا يوجد تقرير معاينة حديث.");
                return;
            }

            _latestPreviewHtmlPath = Directory
                .EnumerateFiles(PreviewReportService.ReportsDirectory, "preview-*.html", SearchOption.TopDirectoryOnly)
                .OrderByDescending(File.GetLastWriteTimeUtc)
                .FirstOrDefault() ?? string.Empty;
            PreviewStatusText.Text = L(string.IsNullOrWhiteSpace(_latestPreviewHtmlPath)
                ? "لا يوجد تقرير معاينة حديث."
                : $"آخر تقرير: {Path.GetFileName(_latestPreviewHtmlPath)}");
        }
        catch (Exception ex)
        {
            AppLogger.Error("Could not locate latest preview report.", ex);
            _latestPreviewHtmlPath = string.Empty;
        }
    }

    private void UpdateV15Status()
    {
        string performance = _settings.LowResourceMode
            ? "وضع Lite مفعّل لجهاز بذاكرة RAM سعتها 4 غيغابايت وقرص HDD. "
            : string.Empty;
        PreviewModeStatusText.Text = L(performance + (_settings.PreviewOnlyMode
            ? "وضع المعاينة فقط مفعّل — لن تُنفّذ العمليات الحساسة."
            : "وضع التنفيذ الفعلي مفعّل. راجع كل رسالة تأكيد قبل المتابعة."));
        RestorePointStatusText.Text = L(_settings.CreateRestorePointBeforeDeepChanges
            ? "سيحاول البرنامج إنشاء نقطة استعادة قبل الإزالة وتغييرات بدء التشغيل."
            : "إنشاء نقطة الاستعادة معطّل من الإعدادات.");
    }

    private readonly record struct RestorePointDecision(bool ContinueOperation, RestorePointSession? Session);
}
