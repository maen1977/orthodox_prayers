using System.ComponentModel;
using System.Diagnostics;
using System.Security.Principal;

namespace SafeWindowsCleaner.Services;

public static class ElevationService
{
    public static bool IsAdministrator
    {
        get
        {
            if (!OperatingSystem.IsWindows())
            {
                return false;
            }

            try
            {
                using WindowsIdentity identity = WindowsIdentity.GetCurrent();
                return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
            }
            catch
            {
                return false;
            }
        }
    }

    public static bool TryRelaunchElevated(string? navigationTarget = null, IEnumerable<string>? extraArguments = null)
    {
        string executable = Environment.ProcessPath
                            ?? throw new InvalidOperationException("The application executable path is unavailable.");
        var arguments = new List<string>
        {
            "--elevated",
            $"--language={QuoteArgument(App.CurrentSettings.LanguageCode)}"
        };
        if (!string.IsNullOrWhiteSpace(navigationTarget))
        {
            arguments.Add($"--navigate={QuoteArgument(navigationTarget)}");
        }

        if (extraArguments is not null)
        {
            arguments.AddRange(extraArguments.Where(argument => !string.IsNullOrWhiteSpace(argument)));
        }

        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = executable,
                Arguments = string.Join(' ', arguments),
                WorkingDirectory = AppContext.BaseDirectory,
                UseShellExecute = true,
                Verb = "runas"
            });
            return true;
        }
        catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)
        {
            AppLogger.Info("The user cancelled the administrator permission request.");
            return false;
        }
    }

    private static string QuoteArgument(string value)
    {
        string escaped = (value ?? string.Empty).Replace("\\", "\\\\").Replace("\"", "\\\"");
        return $"\"{escaped}\"";
    }
}
