using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using SafeWindowsCleaner.Models;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner;

public partial class MainWindow
{
    private readonly CleanupProfileService _cleanupProfileService = new();
    private readonly ScheduledCleanupService _scheduledCleanupService = new();
    private bool _advancedToolsVisible;

    private void InitializeV20Controls()
    {
        IReadOnlyList<CleanupProfileOption> profiles = _cleanupProfileService.GetProfiles(_settings.LanguageCode);
        CleanupProfileComboBox.ItemsSource = profiles;
        CleanupProfileComboBox.SelectedValue = CleanupProfileService.Normalize(_settings.DefaultCleanupProfile);
        DefaultProfileComboBox.ItemsSource = profiles;
        DefaultProfileComboBox.SelectedValue = CleanupProfileService.Normalize(_settings.DefaultCleanupProfile);

        RequireSignedUpdatesCheckBox.IsChecked = _settings.RequireSignedUpdates;
        ScheduledCleanupCheckBox.IsChecked = _settings.ScheduledCleanupEnabled;
        ScheduledHourTextBox.Text = _settings.ScheduledCleanupHour.ToString();
        SelectScheduleDay(_settings.ScheduledCleanupDay);
        SimpleNavigationCheckBox.IsChecked = true;
        SimpleNavigationCheckBox.IsEnabled = false;
        ApplyNavigationMode(simpleNavigation: true);

        HomeModeText.Text = LocalizationService.Translate(
            _settings.LowResourceMode ? "Lite — حدود ذاكرة وفحص محافظة" : "قياسي — نتائج أكثر",
            _settings.LanguageCode);
        HomeElevationText.Text = LocalizationService.Translate(
            ElevationService.IsAdministrator
                ? "صلاحية مسؤول لهذه الجلسة"
                : "تعذر التحقق من صلاحية المسؤول",
            _settings.LanguageCode);
        HeaderPrivilegeText.Text = LocalizationService.Translate(
            ElevationService.IsAdministrator ? "صلاحية مسؤول" : "صلاحية غير مؤكدة",
            _settings.LanguageCode);
    }

    private void ApplyNavigationMode(bool simpleNavigation)
        => SetAdvancedToolsVisible(!simpleNavigation);

    private void SetAdvancedToolsVisible(bool visible)
    {
        // Lite 2.1 has one fixed, understandable navigation model. Advanced engines
        // remain in the codebase but are not exposed in the normal user interface.
        _advancedToolsVisible = false;
        AutomaticCleanupTab.Visibility = Visibility.Collapsed;
        DiskAnalyzerTab.Visibility = Visibility.Collapsed;
        LeftoversTab.Visibility = Visibility.Collapsed;
        InstallMonitorTab.Visibility = Visibility.Collapsed;
        StartupTab.Visibility = Visibility.Collapsed;
        PreviewActivityTab.Visibility = Visibility.Collapsed;
        AboutTab.Visibility = Visibility.Collapsed;
        ProcessesTab.Visibility = Visibility.Visible;
        AdvancedToolsButton.Visibility = Visibility.Collapsed;

        if (RootTabs.SelectedItem is TabItem selected && selected.Visibility != Visibility.Visible)
        {
            RootTabs.SelectedItem = HomeTab;
        }
    }

    private void UpdateAdvancedToolsButton()
    {
        if (AdvancedToolsButton is null)
        {
            return;
        }

        AdvancedToolsButton.Content = LocalizationService.Translate(
            _advancedToolsVisible ? "إخفاء الأدوات المتقدمة" : "إظهار كل الأدوات",
            _settings.LanguageCode);
    }

    private async Task RefreshHomeDashboardAsync()
    {
        try
        {
            List<ActivityLogEntry> activities = await _activityLogService.GetEntriesAsync(1);
            HomeLastActionText.Text = activities.Count == 0
                ? LocalizationService.Translate("لا توجد عمليات مسجلة بعد", _settings.LanguageCode)
                : $"{LocalizationService.Translate(activities[0].Operation, _settings.LanguageCode)} — " +
                  LocalizationService.Translate(activities[0].Status, _settings.LanguageCode);

            List<QuarantineItem> quarantine = await _quarantineService.GetItemsAsync();
            HomeQuarantineText.Text = quarantine.Count == 0
                ? LocalizationService.Translate("لا توجد عناصر في الحجر", _settings.LanguageCode)
                : LocalizationService.Format("@RecoverableItemsCount", _settings.LanguageCode, quarantine.Count);

            await LoadOperationSessionsAsync();
        }
        catch (Exception ex)
        {
            AppLogger.Error("Could not refresh the home dashboard.", ex);
            HomeLastActionText.Text = LocalizationService.Translate("تعذر قراءة آخر نشاط", _settings.LanguageCode);
            HomeQuarantineText.Text = LocalizationService.Translate("تعذر قراءة الحجر", _settings.LanguageCode);
        }
    }

    private void ApplyStartupNavigation()
    {
        string? requested = App.StartupArguments
            .FirstOrDefault(argument => argument.StartsWith("--navigate=", StringComparison.OrdinalIgnoreCase));
        string target = requested is null ? string.Empty : requested["--navigate=".Length..].Trim().Trim('"');
        if (string.IsNullOrWhiteSpace(target))
        {
            RootTabs.SelectedItem = HomeTab;
            return;
        }

        TabItem? tab = RootTabs.Items.OfType<TabItem>()
            .FirstOrDefault(item => string.Equals(item.Name, target, StringComparison.OrdinalIgnoreCase));
        RootTabs.SelectedItem = tab ?? HomeTab;
    }

    private void CleanupProfile_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (CleanupProfileComboBox.SelectedValue is string profile && CleanupTargets.Count > 0)
        {
            _cleanupProfileService.Apply(profile, CleanupTargets);
        }
    }

    private async void HomeAnalyze_Click(object sender, RoutedEventArgs e)
    {
        RootTabs.SelectedItem = CleanupTab;
        await ScanCleanupAsync();
    }

    private void HomeCleanup_Click(object sender, RoutedEventArgs e) => RootTabs.SelectedItem = CleanupTab;
    private void HomeDisk_Click(object sender, RoutedEventArgs e) => OpenSystemTarget("ms-settings:storagesense");
    private void HomeApps_Click(object sender, RoutedEventArgs e) => RootTabs.SelectedItem = InstalledAppsTab;

    private async void HomeMemory_Click(object sender, RoutedEventArgs e)
    {
        RootTabs.SelectedItem = ProcessesTab;
        await RefreshProcessesAsync();
    }

    private void HomeStartup_Click(object sender, RoutedEventArgs e)
        => OpenSystemTarget("ms-settings:startupapps");

    private void HomeRescue_Click(object sender, RoutedEventArgs e) => RootTabs.SelectedItem = QuarantineTab;

    private void OpenStorageSettings_Click(object sender, RoutedEventArgs e) => OpenSystemTarget("ms-settings:storagesense");
    private void OpenWindowsSecurity_Click(object sender, RoutedEventArgs e) => OpenSystemTarget("windowsdefender:");
    private void OpenWindowsUpdate_Click(object sender, RoutedEventArgs e) => OpenSystemTarget("ms-settings:windowsupdate");
    private void OpenTaskManager_Click(object sender, RoutedEventArgs e) => OpenSystemTarget("taskmgr.exe");

    private void OpenSystemTarget(string target)
    {
        try
        {
            Process.Start(new ProcessStartInfo(target) { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            HandleError("تعذر فتح أداة ويندوز المطلوبة.", ex);
        }
    }

    private void SelectScheduleDay(string day)
    {
        foreach (object item in ScheduledDayComboBox.Items)
        {
            if (item is ComboBoxItem comboBoxItem
                && string.Equals(comboBoxItem.Tag?.ToString(), day, StringComparison.OrdinalIgnoreCase))
            {
                ScheduledDayComboBox.SelectedItem = comboBoxItem;
                return;
            }
        }
        ScheduledDayComboBox.SelectedIndex = 6;
    }

    private async void BatchUninstallSelected_Click(object sender, RoutedEventArgs e)
    {
        List<InstalledApp> selected = InstalledAppsGrid.SelectedItems.Cast<InstalledApp>()
            .DistinctBy(app => string.Join("|", app.RegistryHiveName, app.RegistryViewName, app.RegistryKeyPath, app.DisplayName, app.UninstallString), StringComparer.OrdinalIgnoreCase)
            .Take(20)
            .ToList();
        if (selected.Count < 2)
        {
            ShowLocalizedMessage(
                "حدد برنامجين أو أكثر باستخدام Ctrl أو Shift، أو استخدم زر الإزالة العميقة لبرنامج واحد.",
                "الإزالة المتتابعة",
                MessageBoxButton.OK,
                MessageBoxImage.Information);
            return;
        }

        long estimatedBytes = selected.Sum(app => app.EstimatedSizeBytes);
        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = "إزالة برامج متعددة بالتتابع",
                Description = "تشغيل أدوات الإزالة الرسمية واحدًا تلو الآخر، ثم تنظيف البقايا المؤكدة لكل برنامج.",
                ItemCount = selected.Count,
                EstimatedBytes = estimatedBytes,
                RequiresAdministrator = true,
                RiskLevel = "مرتفع",
                Items = selected.Select(app => new OperationPreviewItem
                {
                    Name = app.DisplayName,
                    Location = string.IsNullOrWhiteSpace(app.InstallLocation) ? app.Publisher : app.InstallLocation,
                    Action = "إزالة رسمية ثم تنظيف مؤكد",
                    Safety = "تنفيذ متتابع؛ لا تعمل أداتا إزالة في الوقت نفسه.",
                    SizeBytes = app.EstimatedSizeBytes
                }).ToList()
            }))
        {
            return;
        }

        MessageBoxResult confirmation = ShowLocalizedMessage(
            $"سيتم تشغيل إزالة {selected.Count:N0} برامج بالتتابع. قد تطلب بعض أدوات الإزالة تأكيدًا منك، ولن يبدأ البرنامج التالي قبل انتهاء الحالي. هل تريد المتابعة؟",
            "تأكيد الإزالة المتتابعة",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        RestorePointDecision restoreDecision = await PrepareRestorePointAsync(
            $"Safe Windows Cleaner — Before batch uninstall ({selected.Count} apps)",
            uninstallOperation: true);
        if (!restoreDecision.ContinueOperation)
        {
            return;
        }

        int succeeded = 0;
        int failed = 0;
        bool cancelRestoreSession = true;
        try
        {
            foreach (InstalledApp app in selected)
            {
                if (string.IsNullOrWhiteSpace(app.UninstallString))
                {
                    failed++;
                    await RecordActivityAsync("إزالة متتابعة", "تم التجاوز", $"لا يملك {app.DisplayName} أمر إزالة رسميًا.");
                    continue;
                }

                try
                {
                    SetBusy(true, $"إزالة {app.DisplayName} ({succeeded + failed + 1}/{selected.Count})...", disableTabs: false);
                    InstallMonitorSessionSummary? monitoredSession = await FindMatchingCompletedMonitorSessionAsync(app);
                    Process? uninstallProcess = Process.Start(CreateUninstallStartInfo(app.UninstallString));
                    if (uninstallProcess is null)
                    {
                        throw new InvalidOperationException("تعذر تشغيل أداة الإزالة الرسمية.");
                    }

                    await uninstallProcess.WaitForExitAsync();
                    if (uninstallProcess.ExitCode is not 0 and not 1641 and not 3010)
                    {
                        throw new InvalidOperationException($"أنهت أداة الإزالة العمل بالرمز {uninstallProcess.ExitCode}.");
                    }

                    if (!await WaitForInstalledApplicationRemovalAsync(app))
                    {
                        throw new InvalidOperationException("لا يزال البرنامج ظاهرًا في قائمة البرامج المثبتة.");
                    }

                    MonitoredUninstallCleanupResult? monitoredCleanup = null;
                    if (monitoredSession is not null)
                    {
                        monitoredCleanup = await _monitoredUninstallCleanupService.CleanupAsync(monitoredSession.SessionId, progress: null);
                    }

                    DeepUninstallResult cleanup = await _deepUninstallService.CleanupAsync(
                        app,
                        _settings.LanguageCode,
                        CreateProgress(),
                        monitoredCleanup);
                    succeeded++;
                    cancelRestoreSession = false;
                    await RecordActivityAsync(
                        "إزالة متتابعة",
                        cleanup.FailedItems > 0 ? "اكتملت بتحذيرات" : "نجاح",
                        $"{app.DisplayName}: أزيل {cleanup.TotalRemovedItems:N0} عنصر مؤكد، فشل {cleanup.FailedItems:N0}.",
                        cleanup.TotalRemovedItems,
                        cleanup.BytesQuarantined,
                        restoreDecision.Session?.SequenceNumber ?? 0);
                }
                catch (Exception ex)
                {
                    failed++;
                    AppLogger.Error($"Batch uninstall failed for {app.DisplayName}.", ex);
                    await RecordActivityAsync("إزالة متتابعة", "فشل", $"{app.DisplayName}: {ex.Message}");
                }
            }

            await RefreshInstalledAppsAsync();
            await RefreshQuarantineAsync();
            await RefreshActivityAsync();
            await RefreshHomeDashboardAsync();
            ShowLocalizedMessage(
                $"اكتملت قائمة الإزالة المتتابعة. نجح: {succeeded:N0}، تعذر: {failed:N0}.",
                "نتيجة الإزالة المتتابعة",
                MessageBoxButton.OK,
                failed > 0 ? MessageBoxImage.Warning : MessageBoxImage.Information);
        }
        finally
        {
            await FinishRestorePointAsync(restoreDecision.Session, cancelRestoreSession);
            SetBusy(false);
        }
    }
}
