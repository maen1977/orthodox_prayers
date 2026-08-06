using Microsoft.Win32;
using System.Text.Json;
using System.Text.RegularExpressions;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class SettingsService
{
    private static readonly Regex RepositoryPattern = new(
        "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
        RegexOptions.Compiled | RegexOptions.CultureInvariant);

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

    public static string DataDirectory { get; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "SafeWindowsCleaner");

    public static string SettingsPath { get; } = Path.Combine(DataDirectory, "settings.json");

    public AppSettings Load()
    {
        try
        {
            if (!File.Exists(SettingsPath))
            {
                return Normalize(ApplyInstallerLanguage(new AppSettings()));
            }

            string json = File.ReadAllText(SettingsPath);
            AppSettings? settings = JsonSerializer.Deserialize<AppSettings>(json, JsonOptions);
            return Normalize(ApplyInstallerLanguage(settings ?? new AppSettings()));
        }
        catch (Exception ex)
        {
            AppLogger.Error("Could not load application settings. Defaults will be used.", ex);
            return Normalize(ApplyInstallerLanguage(new AppSettings()));
        }
    }

    public async Task SaveAsync(AppSettings settings, CancellationToken cancellationToken = default)
    {
        AppSettings normalized = Normalize(settings.Clone());
        Directory.CreateDirectory(DataDirectory);

        string temporaryPath = SettingsPath + ".tmp";
        string json = JsonSerializer.Serialize(normalized, JsonOptions);
        await File.WriteAllTextAsync(temporaryPath, json, cancellationToken);
        File.Move(temporaryPath, SettingsPath, true);
    }


    private static AppSettings ApplyInstallerLanguage(AppSettings settings)
    {
        if (!string.IsNullOrWhiteSpace(settings.LanguageCode) || !OperatingSystem.IsWindows())
        {
            return settings;
        }

        try
        {
            using RegistryKey? key = Registry.CurrentUser.OpenSubKey(@"Software\SafeWindowsCleaner");
            string? language = key?.GetValue("LanguageCode")?.ToString();
            if (!string.IsNullOrWhiteSpace(language))
            {
                settings.LanguageCode = LocalizationService.NormalizeLanguage(language);
            }
        }
        catch (Exception ex)
        {
            AppLogger.Error("Could not read the language selected by Setup.", ex);
        }

        return settings;
    }

    public static AppSettings Normalize(AppSettings settings)
    {
        // Version 2 is the low-resource profile. Existing v1.6 settings are migrated once
        // so the Lite build does not inherit memory-heavy defaults such as 500 results and
        // automatic duplicate hashing on a 4 GB / HDD computer.
        if (settings.SettingsSchemaVersion < 2)
        {
            settings.CheckForUpdatesOnStartup = false;
            settings.LowResourceMode = true;
            settings.CalculateDuplicatesDuringDiskScan = false;
            settings.MinimumDuplicateSizeMb = Math.Max(settings.MinimumDuplicateSizeMb, 50);
            settings.LargestFilesLimit = Math.Min(settings.LargestFilesLimit <= 0 ? 200 : settings.LargestFilesLimit, 200);
            settings.SettingsSchemaVersion = 2;
        }


        if (settings.SettingsSchemaVersion < 3)
        {
            settings.LanguageCode = string.IsNullOrWhiteSpace(settings.LanguageCode) ? string.Empty : settings.LanguageCode;
            settings.SettingsSchemaVersion = 3;
        }

        if (settings.SettingsSchemaVersion < 4)
        {
            settings.DefaultCleanupProfile = CleanupProfileService.SafeProfile;
            settings.EnableTemporaryMemoryRelease = false;
            settings.RequireSignedUpdates = true;
            settings.SimpleNavigation = true;
            settings.SettingsSchemaVersion = 4;
        }

        if (settings.SettingsSchemaVersion < 5)
        {
            settings.EnableTemporaryMemoryRelease = false;
            settings.SimpleNavigation = true;
            settings.SettingsSchemaVersion = 5;
        }

        // Lite 2.1 intentionally does not trim working sets or close applications automatically.
        settings.EnableTemporaryMemoryRelease = false;
        settings.SimpleNavigation = true;

        settings.LanguageCode = string.IsNullOrWhiteSpace(settings.LanguageCode)
            ? string.Empty
            : LocalizationService.NormalizeLanguage(settings.LanguageCode);
        settings.Theme = string.Equals(settings.Theme, "Dark", StringComparison.OrdinalIgnoreCase)
            ? "Dark"
            : "Light";
        settings.QuarantineRetentionDays = Math.Clamp(settings.QuarantineRetentionDays, 1, 3650);
        settings.MinimumDuplicateSizeMb = Math.Clamp(settings.MinimumDuplicateSizeMb, 10, 10240);
        settings.LargestFilesLimit = Math.Clamp(settings.LargestFilesLimit, 50, settings.LowResourceMode ? 500 : 5000);
        settings.DefaultCleanupProfile = CleanupProfileService.Normalize(settings.DefaultCleanupProfile);
        settings.TrustedPublisherThumbprint = NormalizeThumbprint(settings.TrustedPublisherThumbprint);
        settings.ScheduledCleanupDay = NormalizeScheduleDay(settings.ScheduledCleanupDay);
        settings.ScheduledCleanupHour = Math.Clamp(settings.ScheduledCleanupHour, 0, 23);
        settings.GitHubRepository = NormalizeRepository(settings.GitHubRepository);
        return settings;
    }

    public static string NormalizeThumbprint(string? thumbprint)
    {
        string value = new string((thumbprint ?? string.Empty).Where(Uri.IsHexDigit).ToArray()).ToUpperInvariant();
        return value.Length is 40 or 64 ? value : string.Empty;
    }

    public static string NormalizeScheduleDay(string? day)
    {
        string value = (day ?? string.Empty).Trim();
        string[] allowed = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
        return allowed.FirstOrDefault(candidate => string.Equals(candidate, value, StringComparison.OrdinalIgnoreCase)) ?? "Sunday";
    }

    public static string NormalizeRepository(string? repository)
    {
        string value = (repository ?? string.Empty).Trim();
        if (value.StartsWith("https://github.com/", StringComparison.OrdinalIgnoreCase))
        {
            value = value["https://github.com/".Length..];
        }

        value = value.Trim().Trim('/');
        if (value.EndsWith(".git", StringComparison.OrdinalIgnoreCase))
        {
            value = value[..^4];
        }

        return RepositoryPattern.IsMatch(value) ? value : string.Empty;
    }
}
