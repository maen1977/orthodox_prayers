using SafeWindowsCleaner.Win7.Models;
using SafeWindowsCleaner.Win7.Services;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;

namespace SafeWindowsCleaner.Win7
{
    public partial class MainWindow : Window
    {
        private readonly CleanupService _cleanupService = new CleanupService();
        private readonly QuarantineService _quarantineService = new QuarantineService();
        private readonly InstalledProgramService _programService = new InstalledProgramService();
        private readonly ProcessService _processService = new ProcessService();
        private readonly VirtualMemoryService _virtualMemoryService = new VirtualMemoryService();

        private readonly ObservableCollection<CleanupItem> _cleanupItems = new ObservableCollection<CleanupItem>();
        private readonly ObservableCollection<InstalledProgram> _programs = new ObservableCollection<InstalledProgram>();
        private readonly ObservableCollection<ProcessItem> _processes = new ObservableCollection<ProcessItem>();
        private readonly ObservableCollection<QuarantineEntry> _restoreItems = new ObservableCollection<QuarantineEntry>();
        private bool _loadingLanguage;

        public MainWindow()
        {
            InitializeComponent();
            CleanupGrid.ItemsSource = _cleanupItems;
            ProgramsGrid.ItemsSource = _programs;
            ProcessesGrid.ItemsSource = _processes;
            RestoreGrid.ItemsSource = _restoreItems;
            ApplyLanguage();
            MainTabs.SelectedIndex = 0;
        }

        private void ApplyLanguage()
        {
            LocalizationService.ApplyCulture(this);
            Title = LocalizationService.Get("AppTitle");
            SideTitle.Text = LocalizationService.Get("AppTitle");
            HomeButton.Content = LocalizationService.Get("Home");
            CleanButton.Content = LocalizationService.Get("Clean");
            ProgramsButton.Content = LocalizationService.Get("Programs");
            MemoryButton.Content = LocalizationService.Get("Memory");
            RestoreButton.Content = LocalizationService.Get("Restore");
            SettingsButton.Content = LocalizationService.Get("Settings");
            StatusText.Text = LocalizationService.Get("StatusReady");

            WelcomeTitle.Text = LocalizationService.Get("Welcome");
            WelcomeBody.Text = LocalizationService.Get("WelcomeBody");
            HomeScanButton.Content = LocalizationService.Get("ScanNow");
            HomeProgramsButton.Content = LocalizationService.Get("Programs");
            HomeMemoryButton.Content = LocalizationService.Get("Memory");
            HomeRestoreButton.Content = LocalizationService.Get("Restore");

            CleanTitle.Text = LocalizationService.Get("Clean");
            ScanButton.Content = LocalizationService.Get("ScanNow");
            CleanSelectedButton.Content = LocalizationService.Get("CleanSelected");
            CleanupSelectedColumn.Header = "✓";
            CleanupCategoryColumn.Header = LocalizationService.Get("Category");
            CleanupPathColumn.Header = LocalizationService.Get("Path");
            CleanupSizeColumn.Header = LocalizationService.Get("Size");

            ProgramsTitle.Text = LocalizationService.Get("Programs");
            ProgramsRefreshButton.Content = LocalizationService.Get("Refresh");
            UninstallButton.Content = LocalizationService.Get("UninstallSelected");
            ProgramNameColumn.Header = LocalizationService.Get("Name");
            ProgramPublisherColumn.Header = LocalizationService.Get("Publisher");
            ProgramVersionColumn.Header = LocalizationService.Get("Version");

            MemoryTitle.Text = LocalizationService.Get("Memory");
            ProcessesRefreshButton.Content = LocalizationService.Get("Refresh");
            CloseProcessButton.Content = LocalizationService.Get("CloseSelected");
            ProcessNameColumn.Header = LocalizationService.Get("Name");
            ProcessWindowColumn.Header = LocalizationService.Get("WindowOrStatus");
            ProcessMemoryColumn.Header = LocalizationService.Get("MemoryUse");
            ReservePagefileButton.Content = LocalizationService.Get("ReservePagefile");
            RestorePagefileButton.Content = LocalizationService.Get("RestorePagefile");
            PagefileInfoText.Text = LocalizationService.Get("PagefileInfo");
            UpdatePagefileStatus();

            RestoreTitle.Text = LocalizationService.Get("Restore");
            RestoreRefreshButton.Content = LocalizationService.Get("Refresh");
            RestoreSelectedButton.Content = LocalizationService.Get("RestoreSelected");
            DeleteSelectedButton.Content = LocalizationService.Get("DeleteSelected");
            RestorePathColumn.Header = LocalizationService.Get("OriginalPath");
            RestoreSizeColumn.Header = LocalizationService.Get("Size");
            RestoreDateColumn.Header = LocalizationService.Get("Date");

            SettingsTitle.Text = LocalizationService.Get("Settings");
            LanguageLabel.Text = LocalizationService.Get("Language");
            _loadingLanguage = true;
            ((ComboBoxItem)LanguageCombo.Items[0]).Content = LocalizationService.Get("Arabic");
            ((ComboBoxItem)LanguageCombo.Items[1]).Content = LocalizationService.Get("English");
            LanguageCombo.SelectedIndex = SettingsService.LanguageCode == "en" ? 1 : 0;
            _loadingLanguage = false;

            RefreshLocalizedSummaries();
        }

        private void RefreshLocalizedSummaries()
        {
            CleanSummaryText.Text = LocalizationService.Format("ScanSummary", _cleanupItems.Count, SizeFormatter.Format(_cleanupItems.Sum(x => x.SizeBytes)));
            ProgramsSummaryText.Text = LocalizationService.Format("ProgramsFound", _programs.Count);
            ProcessesSummaryText.Text = LocalizationService.Format("ProcessesFound", _processes.Count);
            RestoreSummaryText.Text = LocalizationService.Format("RestoreFound", _restoreItems.Count);
        }

        private void SetPage(int index) { MainTabs.SelectedIndex = index; }
        private void HomeButton_Click(object sender, RoutedEventArgs e) { SetPage(0); }
        private void CleanButton_Click(object sender, RoutedEventArgs e) { SetPage(1); }
        private async void ProgramsButton_Click(object sender, RoutedEventArgs e) { SetPage(2); if (_programs.Count == 0) await RefreshProgramsAsync(); }
        private async void MemoryButton_Click(object sender, RoutedEventArgs e) { SetPage(3); if (_processes.Count == 0) await RefreshProcessesAsync(); }
        private void RestoreButton_Click(object sender, RoutedEventArgs e) { SetPage(4); RefreshRestoreItems(); }
        private void SettingsButton_Click(object sender, RoutedEventArgs e) { SetPage(5); }
        private async void HomeScanButton_Click(object sender, RoutedEventArgs e) { SetPage(1); await ScanAsync(); }
        private async void HomeProgramsButton_Click(object sender, RoutedEventArgs e) { SetPage(2); await RefreshProgramsAsync(); }
        private async void HomeMemoryButton_Click(object sender, RoutedEventArgs e) { SetPage(3); await RefreshProcessesAsync(); }
        private void HomeRestoreButton_Click(object sender, RoutedEventArgs e) { SetPage(4); RefreshRestoreItems(); }

        private async void ScanButton_Click(object sender, RoutedEventArgs e) { await ScanAsync(); }

        private async Task ScanAsync()
        {
            ToggleBusy(true, LocalizationService.Get("Scanning"));
            try
            {
                List<CleanupItem> items = await Task.Factory.StartNew(() => _cleanupService.Scan());
                Replace(_cleanupItems, items);
                CleanSelectedButton.IsEnabled = _cleanupItems.Count > 0;
                CleanSummaryText.Text = LocalizationService.Format("ScanSummary", _cleanupItems.Count, SizeFormatter.Format(_cleanupItems.Sum(x => x.SizeBytes)));
            }
            catch (Exception ex) { ShowError(ex); }
            finally { ToggleBusy(false, LocalizationService.Get("StatusReady")); }
        }

        private async void CleanSelectedButton_Click(object sender, RoutedEventArgs e)
        {
            List<CleanupItem> selected = _cleanupItems.Where(x => x.IsSelected).ToList();
            if (selected.Count == 0) { ShowInfo(LocalizationService.Get("SelectItem")); return; }
            ToggleBusy(true, LocalizationService.Get("Cleaning"));
            try
            {
                int moved = await Task.Factory.StartNew(() => _quarantineService.Quarantine(selected));
                foreach (CleanupItem item in selected.Where(x => !System.IO.File.Exists(x.Path)).ToList()) _cleanupItems.Remove(item);
                CleanSummaryText.Text = LocalizationService.Format("CleanSummary", moved);
                CleanSelectedButton.IsEnabled = _cleanupItems.Count > 0;
            }
            catch (Exception ex) { ShowError(ex); }
            finally { ToggleBusy(false, LocalizationService.Get("StatusReady")); }
        }

        private async void ProgramsRefreshButton_Click(object sender, RoutedEventArgs e) { await RefreshProgramsAsync(); }
        private async Task RefreshProgramsAsync()
        {
            ToggleBusy(true, LocalizationService.Get("Programs"));
            try
            {
                List<InstalledProgram> items = await Task.Factory.StartNew(() => _programService.GetPrograms());
                Replace(_programs, items);
                ProgramsSummaryText.Text = LocalizationService.Format("ProgramsFound", _programs.Count);
            }
            catch (Exception ex) { ShowError(ex); }
            finally { ToggleBusy(false, LocalizationService.Get("StatusReady")); }
        }

        private void UninstallButton_Click(object sender, RoutedEventArgs e)
        {
            InstalledProgram program = ProgramsGrid.SelectedItem as InstalledProgram;
            if (program == null) { ShowInfo(LocalizationService.Get("SelectItem")); return; }
            if (MessageBox.Show(LocalizationService.Get("ConfirmUninstall"), LocalizationService.Get("Programs"), MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes) return;
            try { _programService.RunUninstaller(program); }
            catch (Exception ex) { ShowError(ex); }
        }

        private async void ProcessesRefreshButton_Click(object sender, RoutedEventArgs e) { await RefreshProcessesAsync(); }
        private async Task RefreshProcessesAsync()
        {
            ToggleBusy(true, LocalizationService.Get("Memory"));
            try
            {
                List<ProcessItem> items = await Task.Factory.StartNew(() => _processService.GetHeavyUserApps());
                Replace(_processes, items);
                ProcessesSummaryText.Text = LocalizationService.Format("ProcessesFound", _processes.Count);
                UpdatePagefileStatus();
            }
            catch (Exception ex) { ShowError(ex); }
            finally { ToggleBusy(false, LocalizationService.Get("StatusReady")); }
        }

        private async void CloseProcessButton_Click(object sender, RoutedEventArgs e)
        {
            ProcessItem item = ProcessesGrid.SelectedItem as ProcessItem;
            if (item == null) { ShowInfo(LocalizationService.Get("SelectItem")); return; }
            if (MessageBox.Show(LocalizationService.Get("ConfirmClose"), LocalizationService.Get("Memory"), MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes) return;
            bool requested = await Task.Factory.StartNew(() => _processService.RequestClose(item));
            if (!requested) ShowInfo(LocalizationService.Get("Unknown"));
            await Task.Delay(700);
            await RefreshProcessesAsync();
        }

        private void ReservePagefileButton_Click(object sender, RoutedEventArgs e)
        {
            int recommendedSizeMb = _virtualMemoryService.GetRecommendedSizeMb();
            if (recommendedSizeMb == 0)
            {
                ShowInfo(LocalizationService.Get("NeedSpace"));
                return;
            }

            string recommendedSize = SizeFormatter.Format(recommendedSizeMb * 1024L * 1024L);
            if (MessageBox.Show(
                    LocalizationService.Format("ConfirmPagefile", recommendedSize),
                    LocalizationService.Get("Memory"),
                    MessageBoxButton.YesNo,
                    MessageBoxImage.Question) != MessageBoxResult.Yes) return;
            try
            {
                int appliedSizeMb = _virtualMemoryService.ApplyRecommended();
                UpdatePagefileStatus();
                ShowInfo(LocalizationService.Format(
                    "PagefileApplied",
                    SizeFormatter.Format(appliedSizeMb * 1024L * 1024L)));
            }
            catch (Exception ex)
            {
                LogService.Write(ex.ToString());
                ShowInfo(LocalizationService.Get("PagefileUnavailable"));
            }
        }

        private void RestorePagefileButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_virtualMemoryService.RestorePrevious()) ShowInfo(LocalizationService.Get("PagefileRestored"));
                else ShowInfo(LocalizationService.Get("Unknown"));
                UpdatePagefileStatus();
            }
            catch (Exception ex) { ShowError(ex); }
        }

        private void UpdatePagefileStatus()
        {
            PagefileStatusText.Text = LocalizationService.Format("PagefileCurrent", _virtualMemoryService.GetStatus());
        }

        private void RestoreRefreshButton_Click(object sender, RoutedEventArgs e) { RefreshRestoreItems(); }
        private void RefreshRestoreItems()
        {
            Replace(_restoreItems, _quarantineService.Load());
            RestoreSummaryText.Text = LocalizationService.Format("RestoreFound", _restoreItems.Count);
        }

        private void RestoreSelectedButton_Click(object sender, RoutedEventArgs e)
        {
            QuarantineEntry entry = RestoreGrid.SelectedItem as QuarantineEntry;
            if (entry == null) { ShowInfo(LocalizationService.Get("SelectItem")); return; }
            if (_quarantineService.Restore(entry)) RefreshRestoreItems(); else ShowInfo(LocalizationService.Get("Unknown"));
        }

        private void DeleteSelectedButton_Click(object sender, RoutedEventArgs e)
        {
            QuarantineEntry entry = RestoreGrid.SelectedItem as QuarantineEntry;
            if (entry == null) { ShowInfo(LocalizationService.Get("SelectItem")); return; }
            if (_quarantineService.Delete(entry)) RefreshRestoreItems(); else ShowInfo(LocalizationService.Get("Unknown"));
        }

        private void LanguageCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (_loadingLanguage || LanguageCombo.SelectedItem == null) return;
            string code = Convert.ToString(((ComboBoxItem)LanguageCombo.SelectedItem).Tag);
            if (code == SettingsService.LanguageCode) return;
            SettingsService.LanguageCode = code;
            MessageBox.Show(LocalizationService.Get("RestartLanguage"), LocalizationService.Get("Settings"), MessageBoxButton.OK, MessageBoxImage.Information);
            Process.Start(new ProcessStartInfo { FileName = Process.GetCurrentProcess().MainModule.FileName, UseShellExecute = true });
            Application.Current.Shutdown();
        }

        private void ToggleBusy(bool busy, string status)
        {
            StatusText.Text = status;
            ScanButton.IsEnabled = !busy;
            ProgramsRefreshButton.IsEnabled = !busy;
            ProcessesRefreshButton.IsEnabled = !busy;
            Cursor = busy ? System.Windows.Input.Cursors.Wait : null;
        }

        private static void Replace<T>(ObservableCollection<T> collection, IEnumerable<T> items)
        {
            collection.Clear();
            foreach (T item in items) collection.Add(item);
        }

        private void ShowError(Exception ex)
        {
            LogService.Write(ex.ToString());
            MessageBox.Show(LocalizationService.Get("OperationFailed"), LocalizationService.Get("Error"), MessageBoxButton.OK, MessageBoxImage.Error);
        }

        private void ShowInfo(string message)
        {
            MessageBox.Show(message, LocalizationService.Get("Information"), MessageBoxButton.OK, MessageBoxImage.Information);
        }
    }
}
