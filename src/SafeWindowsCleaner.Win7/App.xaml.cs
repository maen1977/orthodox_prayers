using System;
using System.Linq;
using System.Threading;
using System.Windows;

namespace SafeWindowsCleaner.Win7
{
    public partial class App : Application
    {
        private Mutex _singleInstanceMutex;

        protected override void OnStartup(StartupEventArgs e)
        {
            string languageArgument = e.Args.FirstOrDefault(x => x.StartsWith("--language=", StringComparison.OrdinalIgnoreCase));
            if (!string.IsNullOrEmpty(languageArgument))
            {
                Services.SettingsService.LanguageCode = languageArgument.Substring("--language=".Length);
            }

            if (e.Args.Any(x => string.Equals(x, "--restore-virtual-memory", StringComparison.OrdinalIgnoreCase)))
            {
                try { new Services.VirtualMemoryService().RestorePrevious(); Shutdown(0); }
                catch (Exception ex) { Services.LogService.Write("Command restore failed: " + ex); Shutdown(1); }
                return;
            }

            bool createdNew;
            _singleInstanceMutex = new Mutex(true, "SafeWindowsCleanerLite.Application", out createdNew);
            if (!createdNew)
            {
                MessageBox.Show(Services.LocalizationService.Get("AlreadyRunning"), Services.LocalizationService.Get("AppTitle"), MessageBoxButton.OK, MessageBoxImage.Information);
                Shutdown();
                return;
            }

            AppDomain.CurrentDomain.UnhandledException += delegate(object sender, UnhandledExceptionEventArgs args)
            {
                try { Services.LogService.Write("Unhandled error: " + args.ExceptionObject); } catch { }
            };
            base.OnStartup(e);
        }

        protected override void OnExit(ExitEventArgs e)
        {
            if (_singleInstanceMutex != null)
            {
                try { _singleInstanceMutex.ReleaseMutex(); } catch { }
                _singleInstanceMutex.Dispose();
            }
            base.OnExit(e);
        }
    }
}
