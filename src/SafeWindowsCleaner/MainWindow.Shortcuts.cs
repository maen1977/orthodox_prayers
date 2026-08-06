using System.Windows;
using System.Windows.Input;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner;

public partial class MainWindow
{
    private async void Window_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        ModifierKeys modifiers = Keyboard.Modifiers;
        bool control = modifiers.HasFlag(ModifierKeys.Control);

        if (e.Key == Key.F5)
        {
            e.Handled = true;
            RootTabs.SelectedItem = CleanupTab;
            await ScanCleanupAsync();
            return;
        }

        if (e.Key == Key.Escape)
        {
            bool cancelled = false;
            if (_diskScanCancellation is not null)
            {
                _diskScanCancellation.Cancel();
                cancelled = true;
            }

            if (_automaticCleanupCancellation is not null)
            {
                _automaticCleanupCancellation.Cancel();
                cancelled = true;
            }

            if (_updateCancellation is not null)
            {
                _updateCancellation.Cancel();
                cancelled = true;
            }

            if (cancelled)
            {
                SetStatus("جارٍ إيقاف العملية...");
                e.Handled = true;
            }

            return;
        }

        if (!control)
        {
            return;
        }

        switch (e.Key)
        {
            case Key.D1:
            case Key.NumPad1:
                RootTabs.SelectedItem = HomeTab;
                break;
            case Key.D2:
            case Key.NumPad2:
                RootTabs.SelectedItem = CleanupTab;
                break;
            case Key.D3:
            case Key.NumPad3:
                RootTabs.SelectedItem = InstalledAppsTab;
                await RefreshInstalledAppsAsync();
                break;
            case Key.D4:
            case Key.NumPad4:
                RootTabs.SelectedItem = ProcessesTab;
                await RefreshProcessesAsync();
                break;
            case Key.D5:
            case Key.NumPad5:
                RootTabs.SelectedItem = QuarantineTab;
                await RefreshQuarantineAsync();
                break;
            case Key.D6:
            case Key.NumPad6:
            case Key.OemComma:
                RootTabs.SelectedItem = SettingsTab;
                break;
            case Key.L:
                OpenLogs_Click(this, new RoutedEventArgs());
                break;
            default:
                return;
        }
        e.Handled = true;
    }

    private void OpenSettingsShortcut_Click(object sender, RoutedEventArgs e)
        => RootTabs.SelectedItem = SettingsTab;

    private void ToggleAdvancedTools_Click(object sender, RoutedEventArgs e)
        => SetAdvancedToolsVisible(!_advancedToolsVisible);
}
