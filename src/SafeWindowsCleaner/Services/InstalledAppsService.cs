using Microsoft.Win32;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class InstalledAppsService
{
    private const string UninstallPath = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall";

    public Task<List<InstalledApp>> GetInstalledAppsAsync(CancellationToken cancellationToken = default)
    {
        return Task.Run(() =>
        {
            var apps = new Dictionary<string, InstalledApp>(StringComparer.OrdinalIgnoreCase);

            ReadRegistryView(RegistryHive.LocalMachine, RegistryView.Registry64, apps, cancellationToken);
            ReadRegistryView(RegistryHive.LocalMachine, RegistryView.Registry32, apps, cancellationToken);
            ReadRegistryView(RegistryHive.CurrentUser, RegistryView.Registry64, apps, cancellationToken);
            ReadRegistryView(RegistryHive.CurrentUser, RegistryView.Registry32, apps, cancellationToken);

            return apps.Values
                .OrderBy(app => app.DisplayName, StringComparer.CurrentCultureIgnoreCase)
                .ToList();
        }, cancellationToken);
    }

    private static void ReadRegistryView(
        RegistryHive hive,
        RegistryView view,
        IDictionary<string, InstalledApp> apps,
        CancellationToken cancellationToken)
    {
        try
        {
            using RegistryKey baseKey = RegistryKey.OpenBaseKey(hive, view);
            using RegistryKey? uninstallKey = baseKey.OpenSubKey(UninstallPath);
            if (uninstallKey is null)
            {
                return;
            }

            foreach (string subKeyName in uninstallKey.GetSubKeyNames())
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    using RegistryKey? appKey = uninstallKey.OpenSubKey(subKeyName);
                    if (appKey is null)
                    {
                        continue;
                    }

                    string displayName = ReadString(appKey, "DisplayName");
                    if (string.IsNullOrWhiteSpace(displayName))
                    {
                        continue;
                    }

                    int systemComponent = ReadInt(appKey, "SystemComponent");
                    string releaseType = ReadString(appKey, "ReleaseType");
                    string parentKeyName = ReadString(appKey, "ParentKeyName");
                    if (systemComponent == 1 || !string.IsNullOrWhiteSpace(parentKeyName)
                                             || releaseType.Contains("Update", StringComparison.OrdinalIgnoreCase)
                                             || releaseType.Contains("Hotfix", StringComparison.OrdinalIgnoreCase))
                    {
                        continue;
                    }

                    long estimatedSizeBytes = ReadLong(appKey, "EstimatedSize") * 1024L;
                    string uninstallString = ReadString(appKey, "UninstallString");
                    string quietUninstallString = ReadString(appKey, "QuietUninstallString");
                    string publisher = ReadString(appKey, "Publisher");
                    string version = ReadString(appKey, "DisplayVersion");
                    // Registry identity is the source of truth. Using only display name,
                    // version and publisher could hide separate x86/x64 or per-user entries.
                    string key = $"{hive}|{view}|{subKeyName}";

                    apps.TryAdd(key, new InstalledApp
                    {
                        DisplayName = displayName,
                        Publisher = publisher,
                        Version = version,
                        InstallLocation = ReadString(appKey, "InstallLocation"),
                        UninstallString = !string.IsNullOrWhiteSpace(uninstallString)
                            ? uninstallString
                            : quietUninstallString,
                        QuietUninstallString = quietUninstallString,
                        EstimatedSizeBytes = estimatedSizeBytes,
                        RegistryHiveName = hive.ToString(),
                        RegistryViewName = view.ToString(),
                        RegistryKeyPath = $@"{UninstallPath}\{subKeyName}",
                        RegistrySubKeyName = subKeyName,
                        ProductCode = IsProductCode(subKeyName) ? subKeyName : string.Empty
                    });
                }
                catch (Exception ex)
                {
                    AppLogger.Error($"Could not read installed application registry key: {subKeyName}", ex);
                }
            }
        }
        catch (Exception ex)
        {
            AppLogger.Error($"Could not read uninstall registry view: {hive}/{view}", ex);
        }
    }

    private static string ReadString(RegistryKey key, string name)
        => key.GetValue(name)?.ToString()?.Trim() ?? string.Empty;

    private static long ReadLong(RegistryKey key, string name)
    {
        object? value = key.GetValue(name);
        return value switch
        {
            int intValue when intValue >= 0 => intValue,
            int intValue => unchecked((uint)intValue),
            long longValue when longValue >= 0 => longValue,
            uint uintValue => uintValue,
            _ when long.TryParse(value?.ToString(), out long parsed) && parsed >= 0 => parsed,
            _ => 0
        };
    }

    private static bool IsProductCode(string value)
        => Guid.TryParse(value.Trim('{', '}'), out _);

    private static int ReadInt(RegistryKey key, string name)
    {
        object? value = key.GetValue(name);
        return value switch
        {
            int intValue => intValue,
            long longValue when longValue <= int.MaxValue => (int)longValue,
            _ when int.TryParse(value?.ToString(), out int parsed) => parsed,
            _ => 0
        };
    }
}
