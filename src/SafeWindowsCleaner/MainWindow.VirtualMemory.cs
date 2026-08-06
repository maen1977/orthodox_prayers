using System.Windows;
using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Models;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner;

public partial class MainWindow
{
    private readonly VirtualMemoryService _virtualMemoryService = new();

    private async Task RefreshVirtualMemoryPanelAsync()
    {
        string code = _settings.LanguageCode;
        try
        {
            VirtualMemoryStatus status = await _virtualMemoryService.GetStatusAsync();
            VirtualMemoryDriveText.Text = LocalizationService.Format(
                "@VirtualMemorySystemDrive",
                code,
                status.SystemDrive.TrimEnd('\\'));
            VirtualMemoryFreeSpaceText.Text = LocalizationService.Format(
                "@VirtualMemoryFreeSpace",
                code,
                SizeFormatter.Format(status.FreeBytes, code));

            PagingFileConfiguration? configuration = status.SystemDriveConfiguration;
            bool litePreset = !status.AutomaticManagedPagefile
                              && VirtualMemoryService.IsLitePreset(configuration);
            int configuredSizeMb = litePreset ? configuration!.InitialSizeMb : 0;
            int recommendedSizeMb = VirtualMemoryService.GetRecommendedPageFileSizeMb(status.FreeBytes);

            if (litePreset)
            {
                string configuredSize = SizeFormatter.Format(configuredSizeMb * 1024L * 1024L, code);
                VirtualMemoryStatusText.Text = LocalizationService.Format(
                    status.RestartRequired
                        ? "@VirtualMemoryPresetPendingRestart"
                        : "@VirtualMemoryPresetActive",
                    code,
                    configuredSize);
            }
            else if (status.AutomaticManagedPagefile)
            {
                VirtualMemoryStatusText.Text = LocalizationService.T("@VirtualMemoryWindowsManaged", code);
            }
            else if (configuration is not null)
            {
                VirtualMemoryStatusText.Text = LocalizationService.Format(
                    "@VirtualMemoryCustomStatus",
                    code,
                    LocalizationService.FormatNumber(configuration.InitialSizeMb, code),
                    LocalizationService.FormatNumber(configuration.MaximumSizeMb, code));
            }
            else
            {
                VirtualMemoryStatusText.Text = LocalizationService.T("@VirtualMemoryNotDetected", code);
            }

            ApplyVirtualMemoryButton.IsEnabled = recommendedSizeMb > 0
                                                 && (!litePreset || configuredSizeMb != recommendedSizeMb);
            RestoreVirtualMemoryButton.IsEnabled = status.BackupAvailable;
        }
        catch (Exception ex)
        {
            AppLogger.Error("Could not read the Windows virtual-memory configuration.", ex);
            VirtualMemoryStatusText.Text = LocalizationService.T("@VirtualMemoryReadFailed", code);
            VirtualMemoryDriveText.Text = string.Empty;
            VirtualMemoryFreeSpaceText.Text = string.Empty;
            ApplyVirtualMemoryButton.IsEnabled = false;
            RestoreVirtualMemoryButton.IsEnabled = _virtualMemoryService.HasBackup;
        }

        try
        {
            IReadOnlyList<GpuMemoryInfo> adapters = await _virtualMemoryService.GetGpuMemoryInfoAsync();
            if (adapters.Count == 0)
            {
                GpuMemoryStatusText.Text = LocalizationService.T("@GpuMemoryNotDetected", code);
                return;
            }

            GpuMemoryStatusText.Text = string.Join(
                Environment.NewLine,
                adapters.Select(adapter => adapter.DedicatedMemoryBytes is > 0
                    ? LocalizationService.Format(
                        "@GpuMemoryAdapterWithDedicated",
                        code,
                        adapter.Name,
                        SizeFormatter.Format(adapter.DedicatedMemoryBytes.Value, code))
                    : LocalizationService.Format("@GpuMemoryAdapterManaged", code, adapter.Name)));
        }
        catch (Exception ex)
        {
            AppLogger.Error("Could not read display-adapter memory information.", ex);
            GpuMemoryStatusText.Text = LocalizationService.T("@GpuMemoryReadFailed", code);
        }
    }

    private async void ApplyVirtualMemory_Click(object sender, RoutedEventArgs e)
    {
        string code = _settings.LanguageCode;
        VirtualMemoryStatus currentStatus;
        try
        {
            currentStatus = await _virtualMemoryService.GetStatusAsync();
        }
        catch (Exception ex)
        {
            ShowVirtualMemoryFailure("@VirtualMemoryReadFailed", ex);
            return;
        }

        int recommendedSizeMb = VirtualMemoryService.GetRecommendedPageFileSizeMb(currentStatus.FreeBytes);
        if (recommendedSizeMb == 0)
        {
            ShowLocalizedMessage(
                LocalizationService.Format(
                    "@VirtualMemoryInsufficientSpace",
                    code,
                    SizeFormatter.Format(currentStatus.FreeBytes, code),
                    SizeFormatter.Format(VirtualMemoryService.MinimumFreeBytesAfterApply, code)),
                LocalizationService.T("@VirtualMemoryTitle", code),
                MessageBoxButton.OK,
                MessageBoxImage.Information);
            return;
        }

        string recommendedSize = SizeFormatter.Format(recommendedSizeMb * 1024L * 1024L, code);
        MessageBoxResult confirmation = ShowLocalizedMessage(
            LocalizationService.Format(
                "@VirtualMemoryApplyConfirm",
                code,
                recommendedSize),
            LocalizationService.T("@VirtualMemoryTitle", code),
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        try
        {
            SetBusy(true, LocalizationService.T("@VirtualMemoryApplying", code));
            VirtualMemoryStatus appliedStatus = await _virtualMemoryService.ApplyRecommendedAsync();
            int appliedSizeMb = appliedStatus.SystemDriveConfiguration?.InitialSizeMb ?? recommendedSizeMb;
            string appliedSize = SizeFormatter.Format(appliedSizeMb * 1024L * 1024L, code);
            await RecordActivityAsync(
                LocalizationService.T("@VirtualMemoryTitle", code),
                LocalizationService.T("@Success", code),
                LocalizationService.Format("@VirtualMemoryApplyActivity", code, appliedSize),
                1,
                appliedSizeMb * 1024L * 1024L);
            await RefreshActivityAsync();
            await RefreshVirtualMemoryPanelAsync();
            ShowLocalizedMessage(
                LocalizationService.Format("@VirtualMemoryApplySuccess", code, appliedSize),
                LocalizationService.T("@RestartRequired", code),
                MessageBoxButton.OK,
                MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            ShowVirtualMemoryFailure("@VirtualMemoryApplyFailed", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async void RestoreVirtualMemory_Click(object sender, RoutedEventArgs e)
    {
        string code = _settings.LanguageCode;
        MessageBoxResult confirmation = ShowLocalizedMessage(
            LocalizationService.T("@VirtualMemoryRestoreConfirm", code),
            LocalizationService.T("@VirtualMemoryTitle", code),
            MessageBoxButton.YesNo,
            MessageBoxImage.Question);
        if (confirmation != MessageBoxResult.Yes)
        {
            return;
        }

        try
        {
            SetBusy(true, LocalizationService.T("@VirtualMemoryRestoring", code));
            await _virtualMemoryService.RestorePreviousAsync();
            await RecordActivityAsync(
                LocalizationService.T("@VirtualMemoryTitle", code),
                LocalizationService.T("@Success", code),
                LocalizationService.T("@VirtualMemoryRestoreActivity", code),
                1,
                0);
            await RefreshActivityAsync();
            await RefreshVirtualMemoryPanelAsync();
            ShowLocalizedMessage(
                LocalizationService.T("@VirtualMemoryRestoreSuccess", code),
                LocalizationService.T("@RestartRequired", code),
                MessageBoxButton.OK,
                MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            ShowVirtualMemoryFailure("@VirtualMemoryRestoreFailed", ex);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void ShowVirtualMemoryFailure(string messageKey, Exception exception)
    {
        string code = _settings.LanguageCode;
        string userMessage = LocalizationService.T(messageKey, code);
        AppLogger.Error(userMessage, exception);
        _ = CrashReportService.CreateReport(exception, userMessage);
        StatusText.Text = userMessage;
        ShowLocalizedMessage(
            userMessage + Environment.NewLine + Environment.NewLine
            + LocalizationService.T("@VirtualMemoryDetailsSaved", code),
            LocalizationService.T("@VirtualMemoryTitle", code),
            MessageBoxButton.OK,
            MessageBoxImage.Error);
    }
}
