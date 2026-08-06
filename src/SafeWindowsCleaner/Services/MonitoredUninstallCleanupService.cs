using System.Diagnostics;
using Microsoft.Win32;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class MonitoredUninstallCleanupService
{
    private static readonly string[] ProtectedRegistryTokens =
    [
        "\\microsoft\\windows nt", "\\classes\\clsid", "\\classes\\interface",
        "\\policies", "\\currentversion\\component based servicing"
    ];

    private readonly InstallMonitorService _monitorService;
    private readonly QuarantineService _quarantineService;

    public MonitoredUninstallCleanupService(InstallMonitorService monitorService, QuarantineService quarantineService)
    {
        _monitorService = monitorService;
        _quarantineService = quarantineService;
    }

    public async Task<MonitoredUninstallCleanupResult> CleanupAsync(
        string sessionId,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        InstallMonitorManifest manifest = await _monitorService.GetManifestAsync(sessionId, cancellationToken);
        MonitoredResidualAnalysisResult residuals = await _monitorService.AnalyzeResidualsAsync(sessionId, cancellationToken);
        var result = new MonitoredUninstallCleanupResult();
        string[] ownershipTokens = BuildOwnershipTokens(manifest);

        List<InstallChangeItem> directories = residuals.Changes
            .Where(change => change.ExistsNow
                             && change.Category == InstallChangeCategory.FileSystem
                             && change.Kind == InstallChangeKind.Added
                             && change.IsDirectory
                             && change.IsSafeToQuarantine)
            .ToList();
        foreach (InstallChangeItem directory in directories)
        {
            directory.IsSelected = true;
        }

        if (directories.Count > 0)
        {
            progress?.Report("نقل مجلدات البرنامج المتبقية إلى الحجر...");
            List<LeftoverItem> items = directories.Select(change => new LeftoverItem
            {
                Name = change.Name,
                Path = change.Location,
                Location = "@MonitoredUninstall",
                SizeBytes = change.SizeBytes,
                ItemType = "@MonitoredApplicationDirectory",
                ConfidenceScore = 100,
                MatchReason = "@CreatedDuringMonitoredInstallation",
                IsQuarantinable = true,
                IsSelected = true,
                LastModifiedUtc = SafeLastWriteTimeUtc(change.Location)
            }).ToList();
            QuarantineOperationResult quarantine = await _quarantineService.QuarantineAsync(items, progress, cancellationToken);
            result.DirectoriesQuarantined += quarantine.SucceededItems;
            result.BytesQuarantined += quarantine.BytesProcessed;
            result.FailedItems += quarantine.FailedItems;
            result.SkippedItems += quarantine.SkippedItems;
        }

        HashSet<string> quarantinedRoots = directories
            .Where(change => !Directory.Exists(change.Location))
            .Select(change => TryGetFullPath(change.Location))
            .Where(path => !string.IsNullOrWhiteSpace(path))
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        List<DiskFileItem> files = residuals.Changes
            .Where(change => change.ExistsNow
                             && change.Category == InstallChangeCategory.FileSystem
                             && change.Kind == InstallChangeKind.Added
                             && !change.IsDirectory
                             && File.Exists(change.Location)
                             && !quarantinedRoots.Any(root => PathSafetyService.IsPathUnder(change.Location, root))
                             && IsSafeOwnedFile(change.Location, manifest, ownershipTokens))
            .Select(change => new DiskFileItem
            {
                Name = change.Name,
                Path = change.Location,
                SizeBytes = SafeFileLength(change.Location),
                LastModified = SafeLastWriteTime(change.Location),
                Category = "@MonitoredLeftover",
                IsSafeToQuarantine = true,
                ProtectionReason = "@MonitoredMatchedProtection",
                ScanRoot = manifest.DetectedInstallLocation,
                IsSelected = true
            }).ToList();
        if (files.Count > 0)
        {
            progress?.Report("نقل ملفات واختصارات البرنامج المتبقية إلى الحجر...");
            QuarantineOperationResult quarantine = await _quarantineService.QuarantineDiskFilesAsync(files, progress, cancellationToken);
            result.FilesQuarantined += quarantine.SucceededItems;
            result.BytesQuarantined += quarantine.BytesProcessed;
            result.FailedItems += quarantine.FailedItems;
            result.SkippedItems += quarantine.SkippedItems;
        }

        IEnumerable<InstallChangeItem> removableChanges = residuals.Changes
            .Where(change => change.ExistsNow && change.Kind == InstallChangeKind.Added)
            // Registry values must be removed before their now-empty parent keys.
            .OrderBy(change => change.Category == InstallChangeCategory.Registry
                               && !change.Location.Contains(" — ", StringComparison.Ordinal) ? 1 : 0);

        foreach (InstallChangeItem change in removableChanges)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                switch (change.Category)
                {
                    case InstallChangeCategory.Registry when IsSafeOwnedRegistryLocation(change.Location, ownershipTokens):
                        progress?.Report($"تنظيف ريجستري البرنامج: {change.Name}");
                        if (TryDeleteRegistryEntry(change.Location))
                        {
                            result.RegistryItemsRemoved++;
                            result.Actions.Add($"Registry: {change.Location}");
                        }
                        else
                        {
                            result.SkippedItems++;
                        }
                        break;
                    case InstallChangeCategory.Service when IsSafeOwnedService(change, manifest, ownershipTokens):
                        progress?.Report($"إزالة خدمة البرنامج: {change.Name}");
                        if (await DeleteServiceAsync(change.Location, cancellationToken))
                        {
                            result.ServicesRemoved++;
                            result.Actions.Add($"Service: {change.Location}");
                        }
                        else
                        {
                            result.FailedItems++;
                        }
                        break;
                    case InstallChangeCategory.ScheduledTask when IsSafeOwnedTask(change, manifest, ownershipTokens):
                        progress?.Report($"إزالة مهمة البرنامج: {change.Name}");
                        if (await DeleteTaskAsync(change.Location, cancellationToken))
                        {
                            result.ScheduledTasksRemoved++;
                            result.Actions.Add($"Scheduled task: {change.Location}");
                        }
                        else
                        {
                            result.FailedItems++;
                        }
                        break;
                }
            }
            catch (Exception ex)
            {
                result.FailedItems++;
                result.Warnings.Add($"{change.Category}: {change.Location} — {ex.Message}");
                AppLogger.Error($"Could not remove monitored residual {change.Location}", ex);
            }
        }

        return result;
    }

    private static string[] BuildOwnershipTokens(InstallMonitorManifest manifest)
    {
        return new[] { manifest.DetectedApplicationName, manifest.DetectedPublisher, Path.GetFileNameWithoutExtension(manifest.InstallerName) }
            .Select(NormalizeToken)
            .Where(token => token.Length >= 3 && token is not "setup" and not "install" and not "installer")
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static bool IsSafeOwnedFile(string path, InstallMonitorManifest manifest, IReadOnlyCollection<string> tokens)
    {
        if (PathSafetyService.IsProtectedSystemPath(path) || IsReparsePoint(path))
        {
            return false;
        }

        if (!string.IsNullOrWhiteSpace(manifest.DetectedInstallLocation)
            && PathSafetyService.IsPathUnder(path, manifest.DetectedInstallLocation))
        {
            return true;
        }

        string extension = Path.GetExtension(path);
        bool shortcut = extension.Equals(".lnk", StringComparison.OrdinalIgnoreCase)
                        || extension.Equals(".url", StringComparison.OrdinalIgnoreCase);
        string normalized = NormalizeToken(path);
        return shortcut && tokens.Any(token => normalized.Contains(token, StringComparison.OrdinalIgnoreCase));
    }

    private static bool IsSafeOwnedRegistryLocation(string location, IReadOnlyCollection<string> tokens)
    {
        string normalized = location.Replace('/', '\\').ToLowerInvariant();
        if (ProtectedRegistryTokens.Any(token => normalized.Contains(token, StringComparison.OrdinalIgnoreCase)))
        {
            return false;
        }

        // A monitored application may add a named Run/RunOnce value under the shared Windows key.
        // Only that individual value is eligible; the shared key itself is never deleted.
        bool sharedRunLocation = normalized.Contains("\\microsoft\\windows\\currentversion\\run", StringComparison.OrdinalIgnoreCase);
        if (sharedRunLocation)
        {
            int separator = location.LastIndexOf(" — ", StringComparison.Ordinal);
            if (separator < 0)
            {
                return false;
            }

            string valueName = NormalizeToken(location[(separator + 3)..]);
            return tokens.Any(token => valueName.Contains(token, StringComparison.OrdinalIgnoreCase));
        }

        // Other shared Microsoft Windows locations are not automatically changed.
        if (normalized.Contains("\\microsoft\\windows", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        string ownershipText = NormalizeToken(location);
        return tokens.Any(token => ownershipText.Contains(token, StringComparison.OrdinalIgnoreCase));
    }

    private static bool IsSafeOwnedService(InstallChangeItem change, InstallMonitorManifest manifest, IReadOnlyCollection<string> tokens)
    {
        string combined = NormalizeToken($"{change.Name} {change.Location} {change.Details}");
        if (combined.Contains("system32") || combined.Contains("microsoft") || combined.Contains("windows"))
        {
            return false;
        }

        return (!string.IsNullOrWhiteSpace(manifest.DetectedInstallLocation)
                && change.Details.Contains(manifest.DetectedInstallLocation, StringComparison.OrdinalIgnoreCase))
               || tokens.Any(token => combined.Contains(token, StringComparison.OrdinalIgnoreCase));
    }

    private static bool IsSafeOwnedTask(InstallChangeItem change, InstallMonitorManifest manifest, IReadOnlyCollection<string> tokens)
    {
        string combined = NormalizeToken($"{change.Name} {change.Location} {change.Details}");
        if (combined.Contains("microsoft") || change.Location.StartsWith("Microsoft\\", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        if (tokens.Any(token => combined.Contains(token, StringComparison.OrdinalIgnoreCase)))
        {
            return true;
        }

        string taskPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "System32", "Tasks", change.Location);
        try
        {
            string content = File.Exists(taskPath) ? File.ReadAllText(taskPath) : string.Empty;
            return (!string.IsNullOrWhiteSpace(manifest.DetectedInstallLocation)
                    && content.Contains(manifest.DetectedInstallLocation, StringComparison.OrdinalIgnoreCase))
                   || tokens.Any(token => NormalizeToken(content).Contains(token, StringComparison.OrdinalIgnoreCase));
        }
        catch
        {
            return false;
        }
    }

    private static bool TryDeleteRegistryEntry(string displayLocation)
    {
        if (!TryParseRegistryLocation(displayLocation, out RegistryHive hive, out RegistryView view, out string keyPath, out string valueName))
        {
            return false;
        }

        using RegistryKey baseKey = RegistryKey.OpenBaseKey(hive, view);
        if (valueName == "$KEY")
        {
            int separator = keyPath.LastIndexOf('\\');
            if (separator <= 0)
            {
                return false;
            }

            string parentPath = keyPath[..separator];
            string childName = keyPath[(separator + 1)..];
            using RegistryKey? parent = baseKey.OpenSubKey(parentPath, writable: true);
            using RegistryKey? child = parent?.OpenSubKey(childName, writable: false);
            if (parent is null || child is null || child.SubKeyCount > 0 || child.ValueCount > 0)
            {
                return false;
            }

            child.Close();
            parent.DeleteSubKey(childName, throwOnMissingSubKey: false);
            return true;
        }

        using RegistryKey? key = baseKey.OpenSubKey(keyPath, writable: true);
        if (key is null || !key.GetValueNames().Contains(valueName, StringComparer.OrdinalIgnoreCase))
        {
            return false;
        }

        key.DeleteValue(valueName, throwOnMissingValue: false);
        return true;
    }

    private static bool TryParseRegistryLocation(
        string location,
        out RegistryHive hive,
        out RegistryView view,
        out string keyPath,
        out string valueName)
    {
        hive = RegistryHive.CurrentUser;
        view = RegistryView.Default;
        keyPath = string.Empty;
        valueName = "$KEY";
        int slash = location.IndexOf('\\');
        if (slash <= 0)
        {
            return false;
        }

        string prefix = location[..slash];
        string remainder = location[(slash + 1)..];
        hive = prefix.StartsWith(nameof(RegistryHive.LocalMachine), StringComparison.OrdinalIgnoreCase)
            ? RegistryHive.LocalMachine
            : RegistryHive.CurrentUser;
        view = prefix.Contains(nameof(RegistryView.Registry32), StringComparison.OrdinalIgnoreCase)
            ? RegistryView.Registry32
            : prefix.Contains(nameof(RegistryView.Registry64), StringComparison.OrdinalIgnoreCase)
                ? RegistryView.Registry64
                : RegistryView.Default;

        int valueSeparator = remainder.LastIndexOf(" — ", StringComparison.Ordinal);
        keyPath = valueSeparator >= 0 ? remainder[..valueSeparator] : remainder;
        valueName = valueSeparator >= 0 ? remainder[(valueSeparator + 3)..] : "$KEY";
        return keyPath.StartsWith("Software", StringComparison.OrdinalIgnoreCase)
               && keyPath.Length > "Software".Length + 1;
    }

    private static async Task<bool> DeleteServiceAsync(string serviceName, CancellationToken cancellationToken)
    {
        await RunToolAsync("sc.exe", $"stop \"{serviceName}\"", cancellationToken, acceptNonZero: true);
        int exitCode = await RunToolAsync("sc.exe", $"delete \"{serviceName}\"", cancellationToken, acceptNonZero: false);
        return exitCode == 0;
    }

    private static async Task<bool> DeleteTaskAsync(string relativePath, CancellationToken cancellationToken)
    {
        string taskName = relativePath.StartsWith('\\') ? relativePath : "\\" + relativePath;
        int exitCode = await RunToolAsync("schtasks.exe", $"/Delete /TN \"{taskName}\" /F", cancellationToken, acceptNonZero: false);
        return exitCode == 0;
    }

    private static async Task<int> RunToolAsync(string fileName, string arguments, CancellationToken cancellationToken, bool acceptNonZero)
    {
        using var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = fileName,
                Arguments = arguments,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            }
        };
        if (!process.Start())
        {
            AppLogger.Error($"Could not start {fileName} {arguments}.");
            return -1;
        }

        Task<string> outputTask = process.StandardOutput.ReadToEndAsync();
        Task<string> errorTask = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync(cancellationToken);
        string output = await outputTask;
        string error = await errorTask;

        if (!acceptNonZero && process.ExitCode != 0)
        {
            AppLogger.Error($"{fileName} {arguments} failed with {process.ExitCode}: {error} {output}".Trim());
        }

        return process.ExitCode;
    }


    private static bool IsReparsePoint(string path)
    {
        try
        {
            FileAttributes attributes = File.GetAttributes(path);
            return (attributes & FileAttributes.ReparsePoint) != 0;
        }
        catch
        {
            return true;
        }
    }

    private static long SafeFileLength(string path)
    {
        try { return new FileInfo(path).Length; }
        catch { return 0; }
    }

    private static DateTime SafeLastWriteTime(string path)
    {
        try { return File.GetLastWriteTime(path); }
        catch { return DateTime.Now; }
    }

    private static DateTime SafeLastWriteTimeUtc(string path)
    {
        try { return Directory.GetLastWriteTimeUtc(path); }
        catch { return DateTime.UtcNow; }
    }

    private static string TryGetFullPath(string path)
    {
        try { return Path.GetFullPath(path); }
        catch { return string.Empty; }
    }

    private static string NormalizeToken(string? value)
        => new string((value ?? string.Empty).ToLowerInvariant().Where(char.IsLetterOrDigit).ToArray());
}
