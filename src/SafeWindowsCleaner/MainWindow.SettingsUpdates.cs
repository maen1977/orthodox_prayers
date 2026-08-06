using System.Diagnostics;
using System.Net.Http;
using System.Windows;
using System.Windows.Controls;
using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Models;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner;

public partial class MainWindow
{
    private readonly UpdateService _updateService = new();
    private AppSettings _settings = App.CurrentSettings.Clone();
    private UpdateInfo? _availableUpdate;
    private CancellationTokenSource? _updateCancellation;

    private void LoadSettingsIntoControls()
    {
        _settings = App.CurrentSettings.Clone();
        string interfaceLanguage = LocalizationService.NormalizeLanguage(_settings.LanguageCode);
        LanguageComboBox.ItemsSource = LocalizationService.GetLanguageDisplayOptions(interfaceLanguage);
        LanguageComboBox.SelectedValue = interfaceLanguage;
        SelectTheme(_settings.Theme);
        AutoUpdateCheckBox.IsChecked = _settings.CheckForUpdatesOnStartup;
        RepositoryTextBox.Text = GetEffectiveRepository();
        RetentionDaysTextBox.Text = _settings.QuarantineRetentionDays.ToString();
        MinimumDuplicateSizeTextBox.Text = _settings.MinimumDuplicateSizeMb.ToString();
        LargestFilesLimitTextBox.Text = _settings.LargestFilesLimit.ToString();
        CalculateDuplicatesCheckBox.IsChecked = _settings.CalculateDuplicatesDuringDiskScan;
        DiskDuplicateScanCheckBox.IsChecked = _settings.CalculateDuplicatesDuringDiskScan;
        LowResourceModeCheckBox.IsChecked = _settings.LowResourceMode;
        ConfirmDangerousOperationsCheckBox.IsChecked = _settings.ConfirmDangerousOperations;
        PreviewOnlyModeCheckBox.IsChecked = _settings.PreviewOnlyMode;
        CreateRestorePointCheckBox.IsChecked = _settings.CreateRestorePointBeforeDeepChanges;
        InitializeV20Controls();
        UpdateV15Status();
        SettingsStatusText.Text = L("تُحفظ الإعدادات تلقائيًا لهذا المستخدم.");
    }

    private void SelectTheme(string theme)
    {
        foreach (object item in ThemeComboBox.Items)
        {
            if (item is ComboBoxItem comboBoxItem
                && string.Equals(comboBoxItem.Tag?.ToString(), theme, StringComparison.OrdinalIgnoreCase))
            {
                ThemeComboBox.SelectedItem = comboBoxItem;
                return;
            }
        }

        ThemeComboBox.SelectedIndex = 0;
    }

    private async void SaveSettings_Click(object sender, RoutedEventArgs e)
    {
        if (!TryReadNumber(RetentionDaysTextBox.Text, 1, 3650, "عمر الحجر", out int retentionDays)
            || !TryReadNumber(MinimumDuplicateSizeTextBox.Text, 10, 10240, "أقل حجم للتكرار", out int duplicateSizeMb)
            || !TryReadNumber(LargestFilesLimitTextBox.Text, 50, 5000, "عدد أكبر الملفات", out int largestFilesLimit)
            || !TryReadNumber(ScheduledHourTextBox.Text, 0, 23, "ساعة التنظيف الأسبوعي", out int scheduledHour))
        {
            return;
        }

        string repositoryInput = RepositoryTextBox.Text.Trim();
        string repository = SettingsService.NormalizeRepository(repositoryInput);
        if (!string.IsNullOrWhiteSpace(repositoryInput) && string.IsNullOrWhiteSpace(repository))
        {
            ShowLocalizedMessage(
                "صيغة مستودع GitHub غير صحيحة. استخدم owner/repository مثل: myname/SafeWindowsCleaner",
                "الإعدادات",
                MessageBoxButton.OK,
                MessageBoxImage.Information);
            return;
        }

        string theme = (ThemeComboBox.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "Light";
        string previousLanguageCode = LocalizationService.NormalizeLanguage(_settings.LanguageCode);
        string languageCode = LocalizationService.NormalizeLanguage(LanguageComboBox.SelectedValue?.ToString() ?? "ar");
        var newSettings = new AppSettings
        {
            LanguageCode = languageCode,
            Theme = theme,
            CheckForUpdatesOnStartup = AutoUpdateCheckBox.IsChecked == true,
            QuarantineRetentionDays = retentionDays,
            MinimumDuplicateSizeMb = duplicateSizeMb,
            LargestFilesLimit = largestFilesLimit,
            CalculateDuplicatesDuringDiskScan = CalculateDuplicatesCheckBox.IsChecked == true,
            LowResourceMode = LowResourceModeCheckBox.IsChecked == true,
            ConfirmDangerousOperations = ConfirmDangerousOperationsCheckBox.IsChecked == true,
            PreviewOnlyMode = PreviewOnlyModeCheckBox.IsChecked == true,
            CreateRestorePointBeforeDeepChanges = CreateRestorePointCheckBox.IsChecked == true,
            DefaultCleanupProfile = DefaultProfileComboBox.SelectedValue?.ToString() ?? CleanupProfileService.SafeProfile,
            EnableTemporaryMemoryRelease = false,
            RequireSignedUpdates = RequireSignedUpdatesCheckBox.IsChecked == true,
            TrustedPublisherThumbprint = _settings.TrustedPublisherThumbprint,
            ScheduledCleanupEnabled = ScheduledCleanupCheckBox.IsChecked == true,
            ScheduledCleanupDay = (ScheduledDayComboBox.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "Sunday",
            ScheduledCleanupHour = scheduledHour,
            SimpleNavigation = true,
            GitHubRepository = repository
        };

        try
        {
            SetBusy(true, "حفظ إعدادات البرنامج...");
            await App.SaveSettingsAsync(newSettings);
            _settings = App.CurrentSettings.Clone();
            await _scheduledCleanupService.ConfigureAsync(
                _settings.ScheduledCleanupEnabled,
                _settings.ScheduledCleanupDay,
                _settings.ScheduledCleanupHour,
                _settings.DefaultCleanupProfile);

            if (!string.Equals(previousLanguageCode, _settings.LanguageCode, StringComparison.Ordinal))
            {
                RestartWithSelectedLanguage(_settings.LanguageCode);
                return;
            }

            LoadSettingsIntoControls();
            LocalizationService.Apply(this, _settings.LanguageCode);
            UpdateAboutPage();
            await LoadQuarantineItemsAsync();
            UpdateV15Status();
            await RecordActivityAsync("الإعدادات", "تم الحفظ", "تم تحديث إعدادات البرنامج.");
            await RefreshActivityAsync();
            DiskDuplicateScanCheckBox.IsChecked = _settings.CalculateDuplicatesDuringDiskScan;
            SettingsStatusText.Text = L(_settings.LowResourceMode
                ? "تم حفظ الإعدادات. وضع الأجهزة الضعيفة مفعّل."
                : "تم حفظ الإعدادات وتطبيق المظهر.");
            SetStatus("تم حفظ إعدادات البرنامج.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر حفظ إعدادات البرنامج.", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void ResetSettings_Click(object sender, RoutedEventArgs e)
    {
        MessageBoxResult confirmation = ShowLocalizedMessage(
            "سيتم استعادة الإعدادات الافتراضية مع الاحتفاظ باسم مستودع GitHub المضمّن في البناء. هل تريد المتابعة؟",
            "استعادة الإعدادات",
            MessageBoxButton.YesNo,
            MessageBoxImage.Question);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        var defaults = new AppSettings
        {
            LanguageCode = _settings.LanguageCode,
            GitHubRepository = SettingsService.NormalizeRepository(BuildInfo.EmbeddedGitHubRepository)
        };

        try
        {
            await _scheduledCleanupService.ConfigureAsync(
                enabled: false,
                day: defaults.ScheduledCleanupDay,
                hour: defaults.ScheduledCleanupHour,
                profileId: defaults.DefaultCleanupProfile);
            await App.SaveSettingsAsync(defaults);
            _settings = App.CurrentSettings.Clone();
            LoadSettingsIntoControls();
            UpdateAboutPage();
            await LoadQuarantineItemsAsync();
            UpdateV15Status();
            await RecordActivityAsync("الإعدادات", "استعادة افتراضية", "تمت استعادة إعدادات البرنامج الافتراضية.");
            await RefreshActivityAsync();
            SettingsStatusText.Text = L("تمت استعادة الإعدادات الافتراضية.");
        }
        catch (Exception ex)
        {
            HandleError("تعذر استعادة الإعدادات الافتراضية.", ex);
        }
    }

    private bool TryReadNumber(string value, int minimum, int maximum, string fieldName, out int result)
    {
        if (int.TryParse(value.Trim(), out result) && result >= minimum && result <= maximum)
        {
            return true;
        }

        ShowLocalizedMessage(
            $"قيمة «{fieldName}» يجب أن تكون رقمًا بين {minimum:N0} و{maximum:N0}.",
            "الإعدادات",
            MessageBoxButton.OK,
            MessageBoxImage.Information);
        return false;
    }

    private void RestartWithSelectedLanguage(string languageCode)
    {
        string code = LocalizationService.NormalizeLanguage(languageCode);
        string executable = Environment.ProcessPath
                            ?? throw new InvalidOperationException("The application executable path is unavailable.");

        MessageBox.Show(
            LocalizationService.Translate("تم حفظ اللغة. سيُعاد تشغيل البرنامج الآن حتى تظهر كل النصوص والوحدات بلغة واحدة.", code),
            LocalizationService.Translate("إعادة تشغيل البرنامج", code),
            MessageBoxButton.OK,
            MessageBoxImage.Information);

        if (Application.Current is App app)
        {
            app.ReleaseSingleInstanceForRestart();
        }

        Process.Start(new ProcessStartInfo
        {
            FileName = executable,
            Arguments = $"--language={code}",
            WorkingDirectory = AppContext.BaseDirectory,
            UseShellExecute = true
        });
        Application.Current.Shutdown();
    }

    private void UpdateAboutPage()
    {
        string repository = GetEffectiveRepository();
        AboutVersionText.Text = L($"الإصدار الحالي: {BuildInfo.DisplayVersion} — نسخة Lite للأجهزة ذات ذاكرة RAM سعتها 4 غيغابايت وقرص HDD");
        AboutRepositoryText.Text = L(string.IsNullOrWhiteSpace(repository)
            ? "مستودع GitHub غير مضبوط. أدخله من صفحة الإعدادات."
            : $"GitHub: {repository}");
        AboutPublisherText.Text = $"{LocalizationService.T("@Publisher", _settings.LanguageCode)}: {PublisherInfo.GetDisplayName(_settings.LanguageCode)} — {LocalizationService.T("@Phone", _settings.LanguageCode)}: {PublisherInfo.Phone}";
    }

    private string GetEffectiveRepository()
    {
        string configured = SettingsService.NormalizeRepository(_settings.GitHubRepository);
        return string.IsNullOrWhiteSpace(configured)
            ? SettingsService.NormalizeRepository(BuildInfo.EmbeddedGitHubRepository)
            : configured;
    }

    private async void CheckForUpdates_Click(object sender, RoutedEventArgs e)
        => await CheckForUpdatesAsync(showMessages: true);

    private async Task CheckForUpdatesAsync(bool showMessages)
    {
        if (_updateCancellation is not null)
        {
            if (showMessages)
            {
                ShowLocalizedMessage("يوجد فحص تحديثات جارٍ بالفعل.", "التحديث", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            return;
        }

        string repository = GetEffectiveRepository();
        if (string.IsNullOrWhiteSpace(repository))
        {
            UpdateStatusText.Text = L("أدخل مستودع GitHub من صفحة الإعدادات أولًا.");
            if (showMessages)
            {
                RootTabs.SelectedItem = SettingsTab;
                ShowLocalizedMessage("أدخل المستودع بصيغة owner/repository ثم احفظ الإعدادات.", "التحديث", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            return;
        }

        _updateCancellation = new CancellationTokenSource();
        InstallUpdateButton.IsEnabled = false;
        _availableUpdate = null;
        UpdateProgressBar.Visibility = Visibility.Collapsed;
        UpdateStatusText.Text = L("جارٍ الاتصال بـ GitHub والبحث عن إصدار جديد...");

        try
        {
            UpdateInfo? update = await _updateService.CheckForUpdateAsync(
                repository,
                BuildInfo.Version,
                _updateCancellation.Token);

            if (update is null)
            {
                UpdateStatusText.Text = L($"أنت تستخدم أحدث إصدار متاح ({BuildInfo.DisplayVersion}).");
                UpdateReleaseNotesTextBox.Text = L("لا يوجد تحديث جديد حاليًا.");
                if (showMessages)
                {
                    ShowLocalizedMessage("البرنامج محدث إلى آخر إصدار.", "التحديث", MessageBoxButton.OK, MessageBoxImage.Information);
                }
                return;
            }

            _availableUpdate = update;
            InstallUpdateButton.IsEnabled = true;
            string published = update.PublishedAt?.LocalDateTime.ToString("yyyy/MM/dd HH:mm") ?? "غير معروف";
            UpdateStatusText.Text = L($"يتوفر الإصدار {update.TagName} — تاريخ النشر: {published}.");
            UpdateReleaseNotesTextBox.Text = update.ReleaseNotes;
            AppLogger.Info($"Update available: {update.TagName}");

            if (showMessages)
            {
                RootTabs.SelectedItem = AboutTab;
                ShowLocalizedMessage($"يتوفر تحديث جديد: {update.TagName}", "التحديث", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }
        catch (OperationCanceledException)
        {
            UpdateStatusText.Text = L("تم إلغاء فحص التحديثات.");
        }
        catch (HttpRequestException ex)
        {
            AppLogger.Error("GitHub update check failed.", ex);
            UpdateStatusText.Text = L("تعذر الاتصال بـ GitHub. تحقق من الإنترنت واسم المستودع.");
            if (showMessages)
            {
                ShowLocalizedMessage(UpdateStatusText.Text, "التحديث", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }
        catch (Exception ex)
        {
            AppLogger.Error("Update check failed.", ex);
            UpdateStatusText.Text = L("تعذر فحص التحديث. راجع سجل البرنامج للتفاصيل.");
            if (showMessages)
            {
                ShowLocalizedMessage("تعذر فحص التحديث. راجع سجل البرنامج للتفاصيل.", "التحديث", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }
        finally
        {
            _updateCancellation.Dispose();
            _updateCancellation = null;
        }
    }

    private async void InstallUpdate_Click(object sender, RoutedEventArgs e)
    {
        UpdateInfo? update = _availableUpdate;
        if (update is null)
        {
            ShowLocalizedMessage("ابحث عن تحديث أولًا.", "التحديث", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        if (await HandlePreviewOnlyAsync(new OperationPreview
            {
                Operation = "تثبيت تحديث البرنامج",
                Description = $"تنزيل الإصدار {update.TagName} والتحقق من SHA-256 والتوقيع الرقمي ثم تشغيل المثبت.",
                ItemCount = 1,
                EstimatedBytes = update.SetupAsset.SizeBytes,
                RequiresAdministrator = true,
                RiskLevel = "متوسط",
                Items =
                [
                    new OperationPreviewItem
                    {
                        Name = update.SetupAsset.Name,
                        Location = update.ReleasePageUrl,
                        Action = "تنزيل، تحقق، ثم تثبيت",
                        Safety = "لن يُشغّل المثبت قبل مطابقة SHA-256 والتحقق من توقيع الناشر.",
                        SizeBytes = update.SetupAsset.SizeBytes
                    }
                ]
            }))
        {
            return;
        }

        MessageBoxResult confirmation = ShowLocalizedMessage(
            $"سيتم تنزيل مثبت {update.TagName}، والتحقق من بصمته، ثم إغلاق البرنامج وتشغيل التثبيت. هل تريد المتابعة؟",
            "تثبيت التحديث",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        _updateCancellation = new CancellationTokenSource();
        InstallUpdateButton.IsEnabled = false;
        UpdateProgressBar.Value = 0;
        UpdateProgressBar.IsIndeterminate = true;
        UpdateProgressBar.Visibility = Visibility.Visible;

        try
        {
            var progress = new Progress<UpdateDownloadProgress>(value =>
            {
                UpdateStatusText.Text = L(value.Message);
                if (value.TotalBytes is > 0)
                {
                    UpdateProgressBar.IsIndeterminate = false;
                    UpdateProgressBar.Value = Math.Clamp(value.BytesReceived * 100d / value.TotalBytes.Value, 0, 100);
                }
            });

            PreparedUpdate prepared = await _updateService.DownloadAndVerifyAsync(
                update,
                progress,
                _updateCancellation.Token,
                _settings.RequireSignedUpdates,
                _settings.TrustedPublisherThumbprint);

            UpdateStatusText.Text = L("تم التحقق من التحديث. جارٍ تشغيل المثبت...");
            await RecordActivityAsync(
                "تثبيت تحديث البرنامج",
                "تم التحقق",
                $"تم تنزيل {update.TagName} ومطابقة بصمة المثبت، وسيبدأ التثبيت.",
                1,
                update.SetupAsset.SizeBytes);
            UpdateProgressBar.IsIndeterminate = false;
            UpdateProgressBar.Value = 100;
            UpdateService.LaunchInstaller(prepared);
            Application.Current.Shutdown();
        }
        catch (OperationCanceledException)
        {
            UpdateStatusText.Text = L("تم إلغاء تنزيل التحديث.");
            InstallUpdateButton.IsEnabled = true;
        }
        catch (Exception ex)
        {
            AppLogger.Error("Update download or launch failed.", ex);
            UpdateStatusText.Text = L("تعذر تنزيل التحديث أو تشغيله. راجع سجل البرنامج للتفاصيل.");
            InstallUpdateButton.IsEnabled = true;
            ShowLocalizedMessage("تعذر تنزيل التحديث أو تشغيله. راجع سجل البرنامج للتفاصيل.", "فشل التحديث", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            UpdateProgressBar.IsIndeterminate = false;
            _updateCancellation?.Dispose();
            _updateCancellation = null;
        }
    }

    private void OpenGitHub_Click(object sender, RoutedEventArgs e)
    {
        string repository = GetEffectiveRepository();
        if (string.IsNullOrWhiteSpace(repository))
        {
            RootTabs.SelectedItem = SettingsTab;
            ShowLocalizedMessage("اضبط مستودع GitHub في الإعدادات أولًا.", "GitHub", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo($"https://github.com/{repository}") { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            HandleError("تعذر فتح صفحة GitHub.", ex);
        }
    }

    private void OpenDataFolder_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            Directory.CreateDirectory(SettingsService.DataDirectory);
            Process.Start(new ProcessStartInfo(SettingsService.DataDirectory) { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            HandleError("تعذر فتح مجلد بيانات البرنامج.", ex);
        }
    }
}
