using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;

namespace SafeWindowsCleaner.Services;

public static class CrashReportService
{
    public static string DiagnosticsDirectory { get; } = Path.Combine(SettingsService.DataDirectory, "Diagnostics");

    public static string? CreateReport(Exception exception, string context)
    {
        try
        {
            Directory.CreateDirectory(DiagnosticsDirectory);
            string path = Path.Combine(DiagnosticsDirectory, $"diagnostic-{DateTime.Now:yyyyMMdd-HHmmss}-{Guid.NewGuid():N}.json");
            var report = new
            {
                Product = LocalizationService.ActiveLanguageCode == "ar"
                    ? PublisherInfo.ProductName
                    : PublisherInfo.EnglishProductName,
                Publisher = PublisherInfo.GetDisplayName(LocalizationService.ActiveLanguageCode),
                Version = BuildInfo.DisplayVersion,
                CreatedAtUtc = DateTimeOffset.UtcNow,
                Context = Sanitize(context),
                OperatingSystem = RuntimeInformation.OSDescription,
                OsArchitecture = RuntimeInformation.OSArchitecture.ToString(),
                ProcessArchitecture = RuntimeInformation.ProcessArchitecture.ToString(),
                DotNet = RuntimeInformation.FrameworkDescription,
                Is64BitProcess = Environment.Is64BitProcess,
                Exception = new
                {
                    Type = exception.GetType().FullName,
                    Message = Sanitize(exception.Message),
                    StackTrace = Sanitize(exception.StackTrace ?? string.Empty),
                    InnerException = exception.InnerException is null ? null : new
                    {
                        Type = exception.InnerException.GetType().FullName,
                        Message = Sanitize(exception.InnerException.Message)
                    }
                }
            };

            File.WriteAllText(path, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);
            return path;
        }
        catch
        {
            return null;
        }
    }

    private static string Sanitize(string value)
    {
        string result = value ?? string.Empty;
        foreach ((string path, string token) in GetSensitiveRoots())
        {
            if (!string.IsNullOrWhiteSpace(path))
            {
                result = result.Replace(path, token, StringComparison.OrdinalIgnoreCase);
            }
        }

        return result.Length <= 20000 ? result : result[..20000];
    }

    private static IEnumerable<(string Path, string Token)> GetSensitiveRoots()
    {
        yield return (Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "%USERPROFILE%");
        yield return (Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "%LOCALAPPDATA%");
        yield return (Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "%APPDATA%");
        yield return (Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "%DOCUMENTS%");
    }
}
