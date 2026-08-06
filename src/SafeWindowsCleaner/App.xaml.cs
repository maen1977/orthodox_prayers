using System.Globalization;
using System.Windows;
using SafeWindowsCleaner.Models;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner;

public partial class App : Application
{
    private const string ApplicationMutexName = "SafeWindowsCleanerLite.Application";
    private static readonly SettingsService SettingsService = new();
    private Mutex? _singleInstanceMutex;
    private bool _ownsSingleInstanceMutex;

    public static AppSettings CurrentSettings { get; private set; } = new();
    public static IReadOnlyList<string> StartupArguments { get; private set; } = [];

    protected override void OnStartup(StartupEventArgs e)
    {
        ShutdownMode = ShutdownMode.OnExplicitShutdown;
        StartupArguments = e.Args.ToArray();
        CurrentSettings = SettingsService.Load();
        bool commandLineMode = CommandLineRunner.IsCommandLineMode(e.Args);

        if (!commandLineMode)
        {
            _singleInstanceMutex = new Mutex(initiallyOwned: true, ApplicationMutexName, out bool createdNew);
            _ownsSingleInstanceMutex = createdNew;
            if (!createdNew)
            {
                string code = LocalizationService.NormalizeLanguage(CurrentSettings.LanguageCode);
                MessageBox.Show(
                    LocalizationService.Translate("البرنامج يعمل بالفعل. أغلق النافذة المفتوحة ثم حاول مجددًا.", code),
                    LocalizationService.Translate("البرنامج يعمل", code),
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
                Shutdown();
                return;
            }
        }

        if (string.IsNullOrWhiteSpace(CurrentSettings.GitHubRepository))
        {
            CurrentSettings.GitHubRepository = SettingsService.NormalizeRepository(BuildInfo.EmbeddedGitHubRepository);
        }

        string commandLanguage = ReadLanguageArgument(e.Args);
        if (!string.IsNullOrWhiteSpace(commandLanguage))
        {
            CurrentSettings.LanguageCode = LocalizationService.NormalizeLanguage(commandLanguage);
            SettingsService.SaveAsync(CurrentSettings).GetAwaiter().GetResult();
        }

        if (commandLineMode)
        {
            CurrentSettings.LanguageCode = string.IsNullOrWhiteSpace(CurrentSettings.LanguageCode)
                ? "ar"
                : LocalizationService.NormalizeLanguage(CurrentSettings.LanguageCode);
            LocalizationService.SetActiveLanguage(CurrentSettings.LanguageCode);
            CultureInfo commandCulture = LocalizationService.CultureFor(CurrentSettings.LanguageCode);
            CultureInfo.DefaultThreadCurrentCulture = commandCulture;
            CultureInfo.DefaultThreadCurrentUICulture = commandCulture;
            ThemeService.Apply(CurrentSettings.Theme);
            base.OnStartup(e);

            // Return control to the WPF dispatcher before awaiting command-line work.
            // Blocking here with GetAwaiter().GetResult() deadlocks any awaited I/O
            // because its continuation needs the same dispatcher thread.
            _ = RunCommandLineModeAsync(e.Args);
            return;
        }

        if (string.IsNullOrWhiteSpace(CurrentSettings.LanguageCode))
        {
            var languageWindow = new LanguageSelectionWindow("ar");
            if (languageWindow.ShowDialog() != true)
            {
                Shutdown();
                return;
            }

            CurrentSettings.LanguageCode = languageWindow.SelectedLanguageCode;
            SettingsService.SaveAsync(CurrentSettings).GetAwaiter().GetResult();
        }

        CurrentSettings.LanguageCode = LocalizationService.NormalizeLanguage(CurrentSettings.LanguageCode);
        LocalizationService.SetActiveLanguage(CurrentSettings.LanguageCode);
        CultureInfo culture = LocalizationService.CultureFor(CurrentSettings.LanguageCode);
        CultureInfo.DefaultThreadCurrentCulture = culture;
        CultureInfo.DefaultThreadCurrentUICulture = culture;
        ThemeService.Apply(CurrentSettings.Theme);

        DispatcherUnhandledException += (_, args) =>
        {
            AppLogger.Error("Unhandled UI exception", args.Exception);
            string? reportPath = CrashReportService.CreateReport(args.Exception, "DispatcherUnhandledException");
            MessageBox.Show(
                reportPath is null
                    ? LocalizationService.T("UnexpectedErrorLogged", CurrentSettings.LanguageCode)
                    : LocalizationService.T("UnexpectedErrorReport", CurrentSettings.LanguageCode) + "\n" + reportPath,
                LocalizationService.T("Error", CurrentSettings.LanguageCode),
                MessageBoxButton.OK,
                MessageBoxImage.Error);
            args.Handled = true;
        };

        AppDomain.CurrentDomain.UnhandledException += (_, args) =>
        {
            if (args.ExceptionObject is Exception ex)
            {
                AppLogger.Error("Unhandled application exception", ex);
                CrashReportService.CreateReport(ex, "AppDomain.UnhandledException");
            }
        };

        TaskScheduler.UnobservedTaskException += (_, args) =>
        {
            AppLogger.Error("Unobserved task exception", args.Exception);
            CrashReportService.CreateReport(args.Exception, "TaskScheduler.UnobservedTaskException");
            args.SetObserved();
        };

        base.OnStartup(e);
        var mainWindow = new MainWindow();
        MainWindow = mainWindow;
        ShutdownMode = ShutdownMode.OnMainWindowClose;
        mainWindow.Show();
    }



    private async Task RunCommandLineModeAsync(IReadOnlyList<string> arguments)
    {
        try
        {
            CommandLineRunResult result = await CommandLineRunner.RunAsync(arguments, CurrentSettings);
            AppLogger.Info($"Command-line operation completed. Report: {result.ReportPath}");
            Shutdown(result.Succeeded ? 0 : 1);
        }
        catch (Exception ex)
        {
            AppLogger.Error("Command-line startup failed.", ex);
            Shutdown(1);
        }
    }

    public void ReleaseSingleInstanceForRestart()
    {
        if (!_ownsSingleInstanceMutex)
        {
            return;
        }

        try
        {
            _singleInstanceMutex?.ReleaseMutex();
        }
        catch (ApplicationException)
        {
            // The mutex was already released.
        }
        finally
        {
            _ownsSingleInstanceMutex = false;
        }
    }

    protected override void OnExit(ExitEventArgs e)
    {
        if (_ownsSingleInstanceMutex)
        {
            try
            {
                _singleInstanceMutex?.ReleaseMutex();
            }
            catch (ApplicationException)
            {
                // The mutex was already released during shutdown.
            }
        }

        _singleInstanceMutex?.Dispose();
        base.OnExit(e);
    }

    public static async Task SaveSettingsAsync(AppSettings settings, CancellationToken cancellationToken = default)
    {
        AppSettings normalized = SettingsService.Normalize(settings.Clone());
        await SettingsService.SaveAsync(normalized, cancellationToken);
        CurrentSettings = normalized;
        LocalizationService.SetActiveLanguage(CurrentSettings.LanguageCode);
        CultureInfo culture = LocalizationService.CultureFor(CurrentSettings.LanguageCode);
        CultureInfo.DefaultThreadCurrentCulture = culture;
        CultureInfo.DefaultThreadCurrentUICulture = culture;
        ThemeService.Apply(CurrentSettings.Theme);
    }

    private static string ReadLanguageArgument(IEnumerable<string> arguments)
    {
        foreach (string argument in arguments)
        {
            if (argument.StartsWith("--language=", StringComparison.OrdinalIgnoreCase))
            {
                return argument["--language=".Length..];
            }

            if (argument.StartsWith("/language=", StringComparison.OrdinalIgnoreCase))
            {
                return argument["/language=".Length..];
            }
        }

        return string.Empty;
    }
}
