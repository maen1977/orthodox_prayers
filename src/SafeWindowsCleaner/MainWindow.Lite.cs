using System.Windows.Controls;

namespace SafeWindowsCleaner;

public partial class MainWindow
{
    private readonly HashSet<string> _liteLoadedTabs = new(StringComparer.Ordinal);
    private bool _liteUiReady;
    private bool _liteTabLoadInProgress;

    private async void RootTabs_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (!_liteUiReady || _liteTabLoadInProgress || !ReferenceEquals(e.OriginalSource, RootTabs))
        {
            return;
        }

        if (RootTabs.SelectedItem is not TabItem tab || string.IsNullOrWhiteSpace(tab.Name))
        {
            return;
        }

        string key = tab.Name;
        if (_liteLoadedTabs.Contains(key))
        {
            return;
        }

        _liteTabLoadInProgress = true;
        try
        {
            switch (key)
            {
                case nameof(InstalledAppsTab):
                    await RefreshInstalledAppsAsync();
                    break;
                case nameof(InstallMonitorTab):
                    await RefreshInstallMonitorSessionsAsync();
                    break;
                case nameof(StartupTab):
                    await RefreshStartupItemsAsync();
                    break;
                case nameof(QuarantineTab):
                    await RefreshQuarantineAsync();
                    break;
                case nameof(PreviewActivityTab):
                    await RefreshActivityAsync();
                    break;
                case nameof(ProcessesTab):
                    await RefreshProcessesAsync();
                    break;
                default:
                    return;
            }

            _liteLoadedTabs.Add(key);
        }
        finally
        {
            _liteTabLoadInProgress = false;
        }
    }
}
