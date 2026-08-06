using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Microsoft.Win32;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class DeepUninstallService
{
    private const int MaximumDirectoriesInspected = 2500;
    private const int MaximumShortcutFilesInspected = 12000;
    private const int MaximumRegistryKeysBackedUp = 6000;
    private const int MoveFileDelayUntilReboot = 0x4;

    private static readonly HashSet<string> BlockedIdentityTokens = new(StringComparer.OrdinalIgnoreCase)
    {
        "app", "application", "client", "desktop", "helper", "install", "installer", "launcher",
        "manager", "microsoft", "program", "setup", "software", "system", "tool", "tools",
        "update", "updater", "windows", "common", "service"
    };

    private static readonly HashSet<string> BlockedDirectoryParts = new(StringComparer.OrdinalIgnoreCase)
    {
        "Microsoft", "Windows", "WindowsApps", "Packages", "Common Files", "System32",
        "Program Files", "Program Files (x86)", "ProgramData", "Users", "Temp"
    };

    private static readonly string[] RunKeyPaths =
    [
        @"Software\Microsoft\Windows\CurrentVersion\Run",
        @"Software\Microsoft\Windows\CurrentVersion\RunOnce"
    ];

    private readonly QuarantineService _quarantineService;
    private readonly DeepUninstallReportService _reportService = new();

    public DeepUninstallService(QuarantineService quarantineService)
    {
        _quarantineService = quarantineService;
    }

    public async Task<DeepUninstallResult> CleanupAsync(
        InstalledApp app,
        string languageCode,
        IProgress<string>? progress = null,
        MonitoredUninstallCleanupResult? monitoredCleanup = null,
        CancellationToken cancellationToken = default)
    {
        var result = new DeepUninstallResult
        {
            ApplicationName = app.DisplayName,
            Publisher = app.Publisher,
            LanguageCode = LocalizationService.NormalizeLanguage(languageCode),
            StartedAt = DateTimeOffset.UtcNow,
            DirectoriesQuarantined = monitoredCleanup?.DirectoriesQuarantined ?? 0,
            FilesQuarantined = monitoredCleanup?.FilesQuarantined ?? 0,
            BytesQuarantined = monitoredCleanup?.BytesQuarantined ?? 0,
            RegistryValuesRemoved = monitoredCleanup?.RegistryItemsRemoved ?? 0,
            ServicesRemoved = monitoredCleanup?.ServicesRemoved ?? 0,
            ScheduledTasksRemoved = monitoredCleanup?.ScheduledTasksRemoved ?? 0,
            FailedItems = monitoredCleanup?.FailedItems ?? 0,
            SkippedItems = monitoredCleanup?.SkippedItems ?? 0
        };

        if (monitoredCleanup is not null)
        {
            result.Warnings.AddRange(monitoredCleanup.Warnings);
            foreach (string action in monitoredCleanup.Actions)
            {
                DeepUninstallArtifactKind kind = action.StartsWith("Service:", StringComparison.OrdinalIgnoreCase)
                    ? DeepUninstallArtifactKind.Service
                    : action.StartsWith("Scheduled task:", StringComparison.OrdinalIgnoreCase)
                        ? DeepUninstallArtifactKind.ScheduledTask
                        : DeepUninstallArtifactKind.RegistryValue;
                result.Artifacts.Add(new DeepUninstallArtifact
                {
                    Kind = kind,
                    Name = LocalizationService.T("@MonitoredRecord", result.LanguageCode),
                    Location = action,
                    Reason = "@ReasonMonitoredInstallationRecord",
                    ConfidenceScore = 100,
                    Removed = true
                });
            }
        }

        string[] tokens = BuildIdentityTokens(app);
        if (tokens.Length == 0)
        {
            result.Warnings.Add("No sufficiently specific application identity was available; deep cleanup was stopped for safety.");
            result.CompletedAt = DateTimeOffset.UtcNow;
            DeepUninstallReportResult emptyReport = await _reportService.CreateAsync(result, cancellationToken);
            result.HtmlReportPath = emptyReport.HtmlPath;
            result.JsonReportPath = emptyReport.JsonPath;
            return result;
        }

        progress?.Report(LocalizationService.T("@SearchDeepDirectories", result.LanguageCode));
        List<OwnedPathCandidate> directories = await Task.Run(
            () => DiscoverOwnedDirectories(app, tokens, result, cancellationToken), cancellationToken);
        List<OwnedPathCandidate> files = await Task.Run(
            () => DiscoverOwnedShortcutFiles(app, tokens, result, cancellationToken), cancellationToken);

        await StopOwnedProcessesAsync(directories, result, progress, cancellationToken);
        await QuarantineOwnedPathsAsync(directories, files, result, progress, cancellationToken);

        progress?.Report(LocalizationService.T("@CleanConfirmedRegistry", result.LanguageCode));
        await CleanupRegistryAsync(app, tokens, directories, result, cancellationToken);

        progress?.Report(LocalizationService.T("@RemoveRemainingServices", result.LanguageCode));
        await CleanupServicesAsync(app, tokens, directories, result, cancellationToken);

        progress?.Report(LocalizationService.T("@RemoveRemainingTasks", result.LanguageCode));
        await CleanupScheduledTasksAsync(app, tokens, directories, result, cancellationToken);

        progress?.Report(LocalizationService.T("@ScheduleLockedFiles", result.LanguageCode));
        ScheduleRemainingOwnedPaths(directories, files, result, cancellationToken);

        result.CompletedAt = DateTimeOffset.UtcNow;
        DeepUninstallReportResult report = await _reportService.CreateAsync(result, cancellationToken);
        result.HtmlReportPath = report.HtmlPath;
        result.JsonReportPath = report.JsonPath;
        return result;
    }

    public static string[] BuildIdentityTokens(InstalledApp app)
    {
        var tokens = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        AddIdentityToken(tokens, app.DisplayName);
        AddIdentityToken(tokens, RemoveVersionLikeSuffix(app.DisplayName));

        foreach (string word in SplitIdentityWords(app.DisplayName))
        {
            AddIdentityToken(tokens, word);
        }

        string installFolder = SafeFileName(app.InstallLocation);
        AddIdentityToken(tokens, installFolder);
        if (!string.IsNullOrWhiteSpace(app.ProductCode))
        {
            AddIdentityToken(tokens, app.ProductCode);
        }

        return tokens
            .Where(token => token.Length >= 4 && !BlockedIdentityTokens.Contains(token))
            .OrderByDescending(token => token.Length)
            .ToArray();
    }

    public static bool IsStrongIdentityMatch(string candidate, IReadOnlyCollection<string> tokens)
    {
        string normalized = Normalize(candidate);
        return normalized.Length >= 4
               && tokens.Any(token => token.Length >= 4
                                      && (string.Equals(normalized, token, StringComparison.OrdinalIgnoreCase)
                                          || (token.Length >= 6 && normalized.Contains(token, StringComparison.OrdinalIgnoreCase))));
    }

    private static List<OwnedPathCandidate> DiscoverOwnedDirectories(
        InstalledApp app,
        IReadOnlyCollection<string> tokens,
        DeepUninstallResult result,
        CancellationToken cancellationToken)
    {
        var candidates = new Dictionary<string, OwnedPathCandidate>(StringComparer.OrdinalIgnoreCase);
        string installLocation = TryFullPath(app.InstallLocation);
        if (Directory.Exists(installLocation)
            && IsApprovedApplicationDirectory(installLocation)
            && !IsReparsePoint(installLocation))
        {
            AddDirectoryCandidate(candidates, installLocation, 100, "@ReasonInstallLocation");
        }

        int inspected = 0;
        foreach (string root in GetApplicationRoots())
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (!Directory.Exists(root))
            {
                continue;
            }

            IEnumerable<string> children;
            try
            {
                children = Directory.EnumerateDirectories(root, "*", System.IO.SearchOption.TopDirectoryOnly);
            }
            catch (Exception ex)
            {
                result.Warnings.Add($"Could not scan {root}: {ex.Message}");
                continue;
            }

            foreach (string child in children)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (++inspected > MaximumDirectoriesInspected)
                {
                    result.Warnings.Add("The application-directory scan reached its Lite safety limit.");
                    return candidates.Values.OrderByDescending(item => item.ConfidenceScore).ToList();
                }

                if (!IsApprovedApplicationDirectory(child) || IsReparsePoint(child))
                {
                    continue;
                }

                string childName = Path.GetFileName(child);
                if (IsStrongIdentityMatch(childName, tokens))
                {
                    int confidence = ContainsOwnedBinary(child, app, tokens) ? 98 : 94;
                    AddDirectoryCandidate(candidates, child, confidence, "@ReasonDirectoryName");
                    continue;
                }

                if (IsPublisherDirectory(childName, app.Publisher))
                {
                    IEnumerable<string> vendorChildren;
                    try
                    {
                        vendorChildren = Directory.EnumerateDirectories(child, "*", System.IO.SearchOption.TopDirectoryOnly);
                    }
                    catch
                    {
                        continue;
                    }

                    foreach (string vendorChild in vendorChildren.Take(300))
                    {
                        cancellationToken.ThrowIfCancellationRequested();
                        if (IsApprovedApplicationDirectory(vendorChild)
                            && !IsReparsePoint(vendorChild)
                            && (IsStrongIdentityMatch(Path.GetFileName(vendorChild), tokens)
                                || ContainsOwnedBinary(vendorChild, app, tokens)))
                        {
                            AddDirectoryCandidate(candidates, vendorChild, 98,
                                "@ReasonPublisherChild");
                        }
                    }
                }
                else if (ContainsOwnedBinary(child, app, tokens))
                {
                    AddDirectoryCandidate(candidates, child, 92,
                        "@ReasonBinaryMetadata");
                }
            }
        }

        foreach (string shortcutRoot in GetShortcutRoots())
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (!Directory.Exists(shortcutRoot))
            {
                continue;
            }

            IEnumerable<string> shortcutDirectories;
            try
            {
                shortcutDirectories = Directory.EnumerateDirectories(shortcutRoot, "*", new EnumerationOptions
                {
                    RecurseSubdirectories = true,
                    IgnoreInaccessible = true,
                    ReturnSpecialDirectories = false,
                    AttributesToSkip = FileAttributes.ReparsePoint,
                    MaxRecursionDepth = 3
                });
            }
            catch
            {
                continue;
            }

            foreach (string shortcutDirectory in shortcutDirectories.Take(1500))
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (IsApprovedShortcutDirectory(shortcutDirectory)
                    && IsStrongIdentityMatch(Path.GetFileName(shortcutDirectory), tokens))
                {
                    AddDirectoryCandidate(candidates, shortcutDirectory, 97, "@ReasonShortcutFolder");
                }
            }
        }

        return RemoveParentChildDuplicates(candidates.Values);
    }

    private static List<OwnedPathCandidate> DiscoverOwnedShortcutFiles(
        InstalledApp app,
        IReadOnlyCollection<string> tokens,
        DeepUninstallResult result,
        CancellationToken cancellationToken)
    {
        var files = new Dictionary<string, OwnedPathCandidate>(StringComparer.OrdinalIgnoreCase);
        int inspected = 0;
        foreach (string root in GetShortcutRoots())
        {
            if (!Directory.Exists(root))
            {
                continue;
            }

            IEnumerable<string> entries;
            try
            {
                entries = Directory.EnumerateFiles(root, "*", new EnumerationOptions
                {
                    RecurseSubdirectories = true,
                    IgnoreInaccessible = true,
                    ReturnSpecialDirectories = false,
                    AttributesToSkip = FileAttributes.ReparsePoint,
                    MaxRecursionDepth = 8
                });
            }
            catch (Exception ex)
            {
                result.Warnings.Add($"Could not scan shortcut root {root}: {ex.Message}");
                continue;
            }

            foreach (string file in entries)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (++inspected > MaximumShortcutFilesInspected)
                {
                    result.Warnings.Add("The shortcut scan reached its Lite safety limit.");
                    return files.Values.ToList();
                }

                string extension = Path.GetExtension(file);
                if (!extension.Equals(".lnk", StringComparison.OrdinalIgnoreCase)
                    && !extension.Equals(".url", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                string fileName = Path.GetFileNameWithoutExtension(file);
                bool nameMatch = IsStrongIdentityMatch(fileName, tokens);
                bool contentMatch = extension.Equals(".url", StringComparison.OrdinalIgnoreCase)
                                    && SafeFileContainsIdentity(file, app, tokens);
                if (nameMatch || contentMatch)
                {
                    files[TryFullPath(file)] = new OwnedPathCandidate(
                        TryFullPath(file),
                        IsDirectory: false,
                        ConfidenceScore: contentMatch ? 99 : 95,
                        Reason: contentMatch
                            ? "@ReasonInternetShortcut"
                            : "@ReasonShortcutName",
                        SizeBytes: SafeFileLength(file));
                }
            }
        }

        return files.Values.ToList();
    }

    private async Task StopOwnedProcessesAsync(
        IReadOnlyCollection<OwnedPathCandidate> directories,
        DeepUninstallResult result,
        IProgress<string>? progress,
        CancellationToken cancellationToken)
    {
        string ownPath = Environment.ProcessPath ?? string.Empty;
        foreach (Process process in Process.GetProcesses())
        {
            using (process)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (process.Id == Environment.ProcessId)
                {
                    continue;
                }

                string executablePath;
                try
                {
                    executablePath = process.MainModule?.FileName ?? string.Empty;
                }
                catch
                {
                    continue;
                }

                if (string.IsNullOrWhiteSpace(executablePath)
                    || (!string.IsNullOrWhiteSpace(ownPath)
                        && string.Equals(executablePath, ownPath, StringComparison.OrdinalIgnoreCase))
                    || !directories.Any(directory => PathSafetyService.IsPathUnder(executablePath, directory.Path)))
                {
                    continue;
                }

                try
                {
                    progress?.Report(LocalizationService.Format("@StopRemainingProcess", result.LanguageCode, process.ProcessName));
                    bool closed = false;
                    if (process.MainWindowHandle != IntPtr.Zero)
                    {
                        closed = process.CloseMainWindow() && process.WaitForExit(2500);
                    }

                    if (!closed && !process.HasExited)
                    {
                        process.Kill(entireProcessTree: true);
                        await process.WaitForExitAsync(cancellationToken);
                    }

                    result.ProcessesStopped++;
                    result.Artifacts.Add(new DeepUninstallArtifact
                    {
                        Kind = DeepUninstallArtifactKind.Process,
                        Name = process.ProcessName,
                        Location = executablePath,
                        Reason = "@ReasonOwnedProcess",
                        ConfidenceScore = 100,
                        Removed = true
                    });
                }
                catch (Exception ex)
                {
                    result.FailedItems++;
                    result.Warnings.Add($"Could not stop process {process.ProcessName}: {ex.Message}");
                }
            }
        }
    }

    private async Task QuarantineOwnedPathsAsync(
        IReadOnlyCollection<OwnedPathCandidate> directories,
        IReadOnlyCollection<OwnedPathCandidate> files,
        DeepUninstallResult result,
        IProgress<string>? progress,
        CancellationToken cancellationToken)
    {
        List<LeftoverItem> directoryItems = directories
            .Where(item => Directory.Exists(item.Path))
            .Select(item => new LeftoverItem
            {
                Name = Path.GetFileName(item.Path),
                Path = item.Path,
                Location = "@DeepUninstall",
                SizeBytes = item.SizeBytes > 0 ? item.SizeBytes : SafeDirectorySize(item.Path, cancellationToken),
                ItemType = "@ConfirmedApplicationDirectory",
                ConfidenceScore = item.ConfidenceScore,
                MatchReason = item.Reason,
                IsQuarantinable = true,
                IsSelected = true,
                LastModifiedUtc = SafeDirectoryLastWriteUtc(item.Path)
            }).ToList();

        if (directoryItems.Count > 0)
        {
            progress?.Report(LocalizationService.T("@QuarantineConfirmedDirectories", result.LanguageCode));
            QuarantineOperationResult quarantine = await _quarantineService.QuarantineConfirmedApplicationDirectoriesAsync(
                directoryItems, progress, cancellationToken);
            result.DirectoriesQuarantined += quarantine.SucceededItems;
            result.BytesQuarantined += quarantine.BytesProcessed;
            result.FailedItems += quarantine.FailedItems;
            result.SkippedItems += quarantine.SkippedItems;
        }

        HashSet<string> movedDirectories = directories
            .Where(item => !Directory.Exists(item.Path))
            .Select(item => item.Path)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        List<DiskFileItem> fileItems = files
            .Where(item => File.Exists(item.Path)
                           && !movedDirectories.Any(root => PathSafetyService.IsPathUnder(item.Path, root)))
            .Select(item => new DiskFileItem
            {
                Name = Path.GetFileName(item.Path),
                Path = item.Path,
                SizeBytes = item.SizeBytes,
                LastModified = SafeFileLastWrite(item.Path),
                Category = "@DeepUninstall",
                IsSafeToQuarantine = true,
                ProtectionReason = item.Reason,
                ScanRoot = Path.GetDirectoryName(item.Path) ?? string.Empty,
                IsSelected = true
            }).ToList();

        if (fileItems.Count > 0)
        {
            progress?.Report(LocalizationService.T("@QuarantineConfirmedFiles", result.LanguageCode));
            QuarantineOperationResult quarantine = await _quarantineService.QuarantineConfirmedApplicationFilesAsync(
                fileItems, progress, cancellationToken);
            result.FilesQuarantined += quarantine.SucceededItems;
            result.BytesQuarantined += quarantine.BytesProcessed;
            result.FailedItems += quarantine.FailedItems;
            result.SkippedItems += quarantine.SkippedItems;
        }

        foreach (OwnedPathCandidate item in directories.Concat(files))
        {
            bool removed = item.IsDirectory ? !Directory.Exists(item.Path) : !File.Exists(item.Path);
            result.Artifacts.Add(new DeepUninstallArtifact
            {
                Kind = item.IsDirectory ? DeepUninstallArtifactKind.Directory : DeepUninstallArtifactKind.File,
                Name = Path.GetFileName(item.Path),
                Location = item.Path,
                Reason = item.Reason,
                ConfidenceScore = item.ConfidenceScore,
                SizeBytes = item.SizeBytes,
                Removed = removed
            });
        }
    }

    private static async Task CleanupRegistryAsync(
        InstalledApp app,
        IReadOnlyCollection<string> tokens,
        IReadOnlyCollection<OwnedPathCandidate> directories,
        DeepUninstallResult result,
        CancellationToken cancellationToken)
    {
        string backupDirectory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "SafeWindowsCleaner",
            "DeepUninstallBackups",
            $"{DateTime.UtcNow:yyyyMMdd-HHmmss}-{Guid.NewGuid():N}");
        Directory.CreateDirectory(backupDirectory);
        result.BackupDirectory = backupDirectory;

        var backup = new List<RegistryBackupRecord>();
        int backedUpKeys = 0;

        foreach ((RegistryHive hive, RegistryView view) in RegistryScopes())
        {
            cancellationToken.ThrowIfCancellationRequested();
            using RegistryKey baseKey = RegistryKey.OpenBaseKey(hive, view);

            if (MatchesOriginalRegistryIdentity(app, hive, view))
            {
                RemoveRegistryTree(baseKey, app.RegistryKeyPath, hive, view, backup, result, ref backedUpKeys,
                    "@ReasonOfficialUninstallRegistry", cancellationToken);
            }

            RemoveOwnedSoftwareKeys(baseKey, hive, view, app, tokens, backup, result, ref backedUpKeys, cancellationToken);
            RemoveOwnedRunValues(baseKey, hive, view, app, tokens, directories, backup, result, cancellationToken);
            RemoveOwnedApplicationClassKeys(baseKey, hive, view, app, tokens, directories, backup, result, ref backedUpKeys, cancellationToken);
        }

        RemoveOwnedEnvironmentPaths(app, directories, backup, result, cancellationToken);
        RemoveOwnedFirewallRules(app, tokens, directories, backup, result, cancellationToken);

        string backupPath = Path.Combine(backupDirectory, "registry-backup.json");
        await File.WriteAllTextAsync(
            backupPath,
            JsonSerializer.Serialize(backup, new JsonSerializerOptions { WriteIndented = true }),
            new UTF8Encoding(false),
            cancellationToken);
    }

    private static void RemoveOwnedSoftwareKeys(
        RegistryKey baseKey,
        RegistryHive hive,
        RegistryView view,
        InstalledApp app,
        IReadOnlyCollection<string> tokens,
        List<RegistryBackupRecord> backup,
        DeepUninstallResult result,
        ref int backedUpKeys,
        CancellationToken cancellationToken)
    {
        using RegistryKey? software = baseKey.OpenSubKey("Software", writable: false);
        if (software is null)
        {
            return;
        }

        foreach (string topName in SafeSubKeyNames(software).Take(2000))
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (IsProtectedSoftwareKey(topName))
            {
                continue;
            }

            string topPath = $@"Software\{topName}";
            if (IsStrongIdentityMatch(topName, tokens))
            {
                RemoveRegistryTree(baseKey, topPath, hive, view, backup, result, ref backedUpKeys,
                    "@ReasonSoftwareKey", cancellationToken);
                continue;
            }

            if (!IsPublisherDirectory(topName, app.Publisher))
            {
                continue;
            }

            using RegistryKey? publisherKey = baseKey.OpenSubKey(topPath, writable: false);
            if (publisherKey is null)
            {
                continue;
            }

            foreach (string childName in SafeSubKeyNames(publisherKey).Take(500))
            {
                if (IsStrongIdentityMatch(childName, tokens))
                {
                    RemoveRegistryTree(baseKey, $@"{topPath}\{childName}", hive, view, backup, result, ref backedUpKeys,
                        "@ReasonPublisherRegistry", cancellationToken);
                }
            }
        }
    }

    private static void RemoveOwnedRunValues(
        RegistryKey baseKey,
        RegistryHive hive,
        RegistryView view,
        InstalledApp app,
        IReadOnlyCollection<string> tokens,
        IReadOnlyCollection<OwnedPathCandidate> directories,
        List<RegistryBackupRecord> backup,
        DeepUninstallResult result,
        CancellationToken cancellationToken)
    {
        foreach (string keyPath in RunKeyPaths)
        {
            cancellationToken.ThrowIfCancellationRequested();
            using RegistryKey? key = baseKey.OpenSubKey(keyPath, writable: true);
            if (key is null)
            {
                continue;
            }

            foreach (string valueName in key.GetValueNames())
            {
                object? value = key.GetValue(valueName, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
                string text = value?.ToString() ?? string.Empty;
                bool ownedPath = directories.Any(directory => text.Contains(directory.Path, StringComparison.OrdinalIgnoreCase));
                string executable = ExtractExecutablePath(text);
                bool missingOwnedCommand = !string.IsNullOrWhiteSpace(executable)
                                           && !File.Exists(Environment.ExpandEnvironmentVariables(executable))
                                           && (IsStrongIdentityMatch(valueName, tokens)
                                               || IsStrongIdentityMatch(text, tokens));
                if (!ownedPath && !missingOwnedCommand)
                {
                    continue;
                }

                backup.Add(CaptureRegistryValue(hive, view, keyPath, valueName, value, key.GetValueKind(valueName)));
                try
                {
                    key.DeleteValue(valueName, throwOnMissingValue: false);
                    result.RegistryValuesRemoved++;
                    result.Artifacts.Add(new DeepUninstallArtifact
                    {
                        Kind = DeepUninstallArtifactKind.RegistryValue,
                        Name = valueName,
                        Location = $"{hive}/{view}/{keyPath}",
                        Reason = "@ReasonStartupRegistry",
                        ConfidenceScore = 99,
                        Removed = true
                    });
                }
                catch (Exception ex)
                {
                    result.FailedItems++;
                    result.Warnings.Add($"Could not remove startup registry value {valueName}: {ex.Message}");
                }
            }
        }
    }

    private static void RemoveOwnedApplicationClassKeys(
        RegistryKey baseKey,
        RegistryHive hive,
        RegistryView view,
        InstalledApp app,
        IReadOnlyCollection<string> tokens,
        IReadOnlyCollection<OwnedPathCandidate> directories,
        List<RegistryBackupRecord> backup,
        DeepUninstallResult result,
        ref int backedUpKeys,
        CancellationToken cancellationToken)
    {
        const string applicationsPath = @"Software\Classes\Applications";
        using RegistryKey? applications = baseKey.OpenSubKey(applicationsPath, writable: false);
        if (applications is not null)
        {
            foreach (string child in SafeSubKeyNames(applications).Take(2000))
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (!IsStrongIdentityMatch(Path.GetFileNameWithoutExtension(child), tokens))
                {
                    continue;
                }

                string keyPath = $@"{applicationsPath}\{child}";
                string command = ReadRegistryDefault(baseKey, $@"{keyPath}\shell\open\command");
                if (ReferencesOwnedLocation(command, app, tokens, directories) || CommandExecutableIsMissing(command))
                {
                    RemoveRegistryTree(baseKey, keyPath, hive, view, backup, result, ref backedUpKeys,
                        "@ReasonApplicationClass", cancellationToken);
                }
            }
        }

        const string classesPath = @"Software\Classes";
        using RegistryKey? classes = baseKey.OpenSubKey(classesPath, writable: false);
        if (classes is null)
        {
            return;
        }

        foreach (string progId in SafeSubKeyNames(classes).Take(4000))
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (progId.StartsWith(".", StringComparison.Ordinal)
                || progId.Equals("CLSID", StringComparison.OrdinalIgnoreCase)
                || progId.Equals("Interface", StringComparison.OrdinalIgnoreCase)
                || !IsStrongIdentityMatch(progId, tokens))
            {
                continue;
            }

            string keyPath = $@"{classesPath}\{progId}";
            string command = ReadRegistryDefault(baseKey, $@"{keyPath}\shell\open\command");
            if (ReferencesOwnedLocation(command, app, tokens, directories) || CommandExecutableIsMissing(command))
            {
                RemoveRegistryTree(baseKey, keyPath, hive, view, backup, result, ref backedUpKeys,
                    "@ReasonProgId", cancellationToken);
            }
        }

        foreach (string extensionKey in SafeSubKeyNames(classes).Where(name => name.StartsWith(".", StringComparison.Ordinal)).Take(3000))
        {
            cancellationToken.ThrowIfCancellationRequested();
            string progId = ReadRegistryDefault(baseKey, $@"{classesPath}\{extensionKey}");
            if (string.IsNullOrWhiteSpace(progId) || !IsStrongIdentityMatch(progId, tokens))
            {
                continue;
            }

            string progIdPath = $@"{classesPath}\{progId}";
            string command = ReadRegistryDefault(baseKey, $@"{progIdPath}\shell\open\command");
            using RegistryKey? progIdKey = baseKey.OpenSubKey(progIdPath, writable: false);
            if (progIdKey is null
                || ReferencesOwnedLocation(command, app, tokens, directories)
                || CommandExecutableIsMissing(command))
            {
                RemoveRegistryTree(baseKey, $@"{classesPath}\{extensionKey}", hive, view, backup, result, ref backedUpKeys,
                    "@ReasonFileExtension", cancellationToken);
            }
        }

        const string clsidPath = @"Software\Classes\CLSID";
        using RegistryKey? clsids = baseKey.OpenSubKey(clsidPath, writable: false);
        if (clsids is not null)
        {
            foreach (string clsid in SafeSubKeyNames(clsids).Take(12000))
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (!Guid.TryParse(clsid.Trim('{', '}'), out _))
                {
                    continue;
                }

                string inproc = ReadRegistryDefault(baseKey, $@"{clsidPath}\{clsid}\InprocServer32");
                string localServer = ReadRegistryDefault(baseKey, $@"{clsidPath}\{clsid}\LocalServer32");
                bool owned = (!string.IsNullOrWhiteSpace(inproc) && ReferencesOwnedLocation(inproc, app, tokens, directories))
                             || (!string.IsNullOrWhiteSpace(localServer) && ReferencesOwnedLocation(localServer, app, tokens, directories));
                if (owned)
                {
                    RemoveRegistryTree(baseKey, $@"{clsidPath}\{clsid}", hive, view, backup, result, ref backedUpKeys,
                        "@ReasonComRegistration", cancellationToken);
                }
            }
        }
    }

    private static void RemoveOwnedEnvironmentPaths(
        InstalledApp app,
        IReadOnlyCollection<OwnedPathCandidate> directories,
        List<RegistryBackupRecord> backup,
        DeepUninstallResult result,
        CancellationToken cancellationToken)
    {
        foreach ((RegistryHive hive, string keyPath) in new[]
                 {
                     (RegistryHive.CurrentUser, @"Environment"),
                     (RegistryHive.LocalMachine, @"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
                 })
        {
            cancellationToken.ThrowIfCancellationRequested();
            using RegistryKey baseKey = RegistryKey.OpenBaseKey(hive, RegistryView.Registry64);
            using RegistryKey? key = baseKey.OpenSubKey(keyPath, writable: true);
            if (key is null)
            {
                continue;
            }

            object? original = key.GetValue("Path", null, RegistryValueOptions.DoNotExpandEnvironmentNames);
            string originalText = original?.ToString() ?? string.Empty;
            if (string.IsNullOrWhiteSpace(originalText))
            {
                continue;
            }

            string[] parts = originalText.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            string[] kept = parts.Where(part => !IsOwnedEnvironmentPath(part, app, directories)).ToArray();
            if (kept.Length == parts.Length)
            {
                continue;
            }

            backup.Add(CaptureRegistryValue(hive, RegistryView.Registry64, keyPath, "Path", original, SafeRegistryValueKind(key, "Path")));
            try
            {
                key.SetValue("Path", string.Join(';', kept), SafeRegistryValueKind(key, "Path"));
                result.RegistryValuesRemoved += parts.Length - kept.Length;
                result.Artifacts.Add(new DeepUninstallArtifact
                {
                    Kind = DeepUninstallArtifactKind.RegistryValue,
                    Name = "Path",
                    Location = $"{hive}/Registry64/{keyPath}",
                    Reason = "@ReasonEnvironmentPath",
                    ConfidenceScore = 100,
                    Removed = true
                });
            }
            catch (Exception ex)
            {
                result.FailedItems++;
                result.Warnings.Add($"Could not remove the application directory from PATH: {ex.Message}");
            }
        }
    }

    private static void RemoveOwnedFirewallRules(
        InstalledApp app,
        IReadOnlyCollection<string> tokens,
        IReadOnlyCollection<OwnedPathCandidate> directories,
        List<RegistryBackupRecord> backup,
        DeepUninstallResult result,
        CancellationToken cancellationToken)
    {
        const string keyPath = @"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy\FirewallRules";
        using RegistryKey baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64);
        using RegistryKey? key = baseKey.OpenSubKey(keyPath, writable: true);
        if (key is null)
        {
            return;
        }

        foreach (string valueName in key.GetValueNames().Take(10000))
        {
            cancellationToken.ThrowIfCancellationRequested();
            object? value = key.GetValue(valueName, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
            string text = value?.ToString() ?? string.Empty;
            string applicationPath = ExtractFirewallApplicationPath(text);
            string installLocation = TryFullPath(app.InstallLocation);
            bool pathOwned = !string.IsNullOrWhiteSpace(applicationPath)
                             && (directories.Any(directory => PathSafetyService.IsPathUnder(applicationPath, directory.Path))
                                 || (!string.IsNullOrWhiteSpace(installLocation)
                                     && PathSafetyService.IsPathUnder(applicationPath, installLocation)));
            bool missingIdentityOwned = !string.IsNullOrWhiteSpace(applicationPath)
                                        && !File.Exists(applicationPath)
                                        && IsStrongIdentityMatch(text, tokens);
            if (!pathOwned && !missingIdentityOwned)
            {
                continue;
            }

            backup.Add(CaptureRegistryValue(RegistryHive.LocalMachine, RegistryView.Registry64, keyPath, valueName, value, SafeRegistryValueKind(key, valueName)));
            try
            {
                key.DeleteValue(valueName, throwOnMissingValue: false);
                result.RegistryValuesRemoved++;
                result.Artifacts.Add(new DeepUninstallArtifact
                {
                    Kind = DeepUninstallArtifactKind.RegistryValue,
                    Name = valueName,
                    Location = $"LocalMachine/Registry64/{keyPath}",
                    Reason = "@ReasonFirewallRule",
                    ConfidenceScore = pathOwned ? 100 : 97,
                    Removed = true
                });
            }
            catch (Exception ex)
            {
                result.FailedItems++;
                result.Warnings.Add($"Could not remove firewall rule {valueName}: {ex.Message}");
            }
        }
    }

    private static bool IsOwnedEnvironmentPath(
        string value,
        InstalledApp app,
        IReadOnlyCollection<OwnedPathCandidate> directories)
    {
        string expanded = TryFullPath(value.Trim().Trim('"'));
        if (string.IsNullOrWhiteSpace(expanded))
        {
            return false;
        }

        string installLocation = TryFullPath(app.InstallLocation);
        return directories.Any(directory => string.Equals(expanded, directory.Path, StringComparison.OrdinalIgnoreCase)
                                            || PathSafetyService.IsPathUnder(expanded, directory.Path))
               || (!string.IsNullOrWhiteSpace(installLocation)
                   && (string.Equals(expanded, installLocation, StringComparison.OrdinalIgnoreCase)
                       || PathSafetyService.IsPathUnder(expanded, installLocation)));
    }

    private static string ExtractFirewallApplicationPath(string rule)
    {
        const string marker = "App=";
        int start = rule.IndexOf(marker, StringComparison.OrdinalIgnoreCase);
        if (start < 0)
        {
            return string.Empty;
        }

        start += marker.Length;
        int end = rule.IndexOf('|', start);
        string value = end >= 0 ? rule[start..end] : rule[start..];
        return TryFullPath(value.Trim().Trim('"'));
    }

    private static async Task CleanupServicesAsync(
        InstalledApp app,
        IReadOnlyCollection<string> tokens,
        IReadOnlyCollection<OwnedPathCandidate> directories,
        DeepUninstallResult result,
        CancellationToken cancellationToken)
    {
        using RegistryKey baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64);
        using RegistryKey? services = baseKey.OpenSubKey(@"SYSTEM\CurrentControlSet\Services", writable: false);
        if (services is null)
        {
            return;
        }

        foreach (string serviceName in SafeSubKeyNames(services).Take(5000))
        {
            cancellationToken.ThrowIfCancellationRequested();
            using RegistryKey? service = services.OpenSubKey(serviceName, writable: false);
            if (service is null)
            {
                continue;
            }

            string imagePath = service.GetValue("ImagePath")?.ToString() ?? string.Empty;
            string displayName = service.GetValue("DisplayName")?.ToString() ?? string.Empty;
            string expanded = Environment.ExpandEnvironmentVariables(imagePath);
            if (expanded.Contains("System32", StringComparison.OrdinalIgnoreCase)
                || expanded.Contains("Microsoft", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            bool pathOwned = directories.Any(directory => expanded.Contains(directory.Path, StringComparison.OrdinalIgnoreCase))
                             || (!string.IsNullOrWhiteSpace(app.InstallLocation)
                                 && expanded.Contains(app.InstallLocation, StringComparison.OrdinalIgnoreCase));
            bool identityOwned = IsStrongIdentityMatch(serviceName, tokens)
                                 && (IsStrongIdentityMatch(displayName, tokens)
                                     || IsStrongIdentityMatch(imagePath, tokens));
            if (!pathOwned && !identityOwned)
            {
                continue;
            }

            int stopCode = await RunToolAsync("sc.exe", $"stop \"{serviceName}\"", cancellationToken, acceptNonZero: true);
            int deleteCode = await RunToolAsync("sc.exe", $"delete \"{serviceName}\"", cancellationToken, acceptNonZero: false);
            if (deleteCode == 0)
            {
                result.ServicesRemoved++;
                result.Artifacts.Add(new DeepUninstallArtifact
                {
                    Kind = DeepUninstallArtifactKind.Service,
                    Name = serviceName,
                    Location = imagePath,
                    Reason = pathOwned
                        ? "@ReasonServicePath"
                        : "@ReasonServiceIdentity",
                    ConfidenceScore = pathOwned ? 100 : 96,
                    Removed = true
                });
            }
            else
            {
                result.FailedItems++;
                result.Warnings.Add($"Could not delete service {serviceName}; stop exit code {stopCode}, delete exit code {deleteCode}.");
            }
        }
    }

    private static async Task CleanupScheduledTasksAsync(
        InstalledApp app,
        IReadOnlyCollection<string> tokens,
        IReadOnlyCollection<OwnedPathCandidate> directories,
        DeepUninstallResult result,
        CancellationToken cancellationToken)
    {
        string tasksRoot = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "System32", "Tasks");
        if (!Directory.Exists(tasksRoot))
        {
            return;
        }

        IEnumerable<string> tasks;
        try
        {
            tasks = Directory.EnumerateFiles(tasksRoot, "*", new EnumerationOptions
            {
                RecurseSubdirectories = true,
                IgnoreInaccessible = true,
                ReturnSpecialDirectories = false,
                AttributesToSkip = FileAttributes.ReparsePoint,
                MaxRecursionDepth = 12
            });
        }
        catch (Exception ex)
        {
            result.Warnings.Add($"Could not enumerate scheduled tasks: {ex.Message}");
            return;
        }

        foreach (string taskFile in tasks.Take(10000))
        {
            cancellationToken.ThrowIfCancellationRequested();
            string relative = Path.GetRelativePath(tasksRoot, taskFile);
            if (relative.StartsWith("Microsoft" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            string content;
            try
            {
                var info = new FileInfo(taskFile);
                if (info.Length > 2 * 1024 * 1024)
                {
                    continue;
                }
                content = await File.ReadAllTextAsync(taskFile, cancellationToken);
            }
            catch
            {
                continue;
            }

            bool pathOwned = directories.Any(directory => content.Contains(directory.Path, StringComparison.OrdinalIgnoreCase))
                             || (!string.IsNullOrWhiteSpace(app.InstallLocation)
                                 && content.Contains(app.InstallLocation, StringComparison.OrdinalIgnoreCase));
            bool identityOwned = IsStrongIdentityMatch(relative, tokens)
                                 && IsStrongIdentityMatch(content, tokens);
            if (!pathOwned && !identityOwned)
            {
                continue;
            }

            string taskName = "\\" + relative.Replace(Path.DirectorySeparatorChar, '\\');
            int exitCode = await RunToolAsync("schtasks.exe", $"/Delete /TN \"{taskName}\" /F", cancellationToken, acceptNonZero: false);
            if (exitCode == 0)
            {
                result.ScheduledTasksRemoved++;
                result.Artifacts.Add(new DeepUninstallArtifact
                {
                    Kind = DeepUninstallArtifactKind.ScheduledTask,
                    Name = Path.GetFileName(taskFile),
                    Location = taskName,
                    Reason = pathOwned
                        ? "@ReasonTaskPath"
                        : "@ReasonTaskIdentity",
                    ConfidenceScore = pathOwned ? 100 : 96,
                    Removed = true
                });
            }
            else
            {
                result.FailedItems++;
                result.Warnings.Add($"Could not delete scheduled task {taskName}; exit code {exitCode}.");
            }
        }
    }

    private static void ScheduleRemainingOwnedPaths(
        IReadOnlyCollection<OwnedPathCandidate> directories,
        IReadOnlyCollection<OwnedPathCandidate> files,
        DeepUninstallResult result,
        CancellationToken cancellationToken)
    {
        foreach (OwnedPathCandidate file in files.Where(item => File.Exists(item.Path)))
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (MoveFileEx(file.Path, null, MoveFileDelayUntilReboot))
            {
                result.PendingDeleteItems++;
                result.RestartRequired = true;
                result.Artifacts.Add(new DeepUninstallArtifact
                {
                    Kind = DeepUninstallArtifactKind.PendingDelete,
                    Name = Path.GetFileName(file.Path),
                    Location = file.Path,
                    Reason = "@ReasonLockedFile",
                    ConfidenceScore = file.ConfidenceScore,
                    SizeBytes = file.SizeBytes,
                    Removed = true,
                    RequiresRestart = true
                });
            }
            else
            {
                result.FailedItems++;
                result.Warnings.Add($"Locked file could not be scheduled for deletion: {file.Path}");
            }
        }

        foreach (OwnedPathCandidate directory in directories.Where(item => Directory.Exists(item.Path)))
        {
            cancellationToken.ThrowIfCancellationRequested();
            int scheduled = ScheduleDirectoryTreeForDeletion(directory.Path, cancellationToken);
            if (scheduled > 0)
            {
                result.PendingDeleteItems += scheduled;
                result.RestartRequired = true;
                result.Artifacts.Add(new DeepUninstallArtifact
                {
                    Kind = DeepUninstallArtifactKind.PendingDelete,
                    Name = Path.GetFileName(directory.Path),
                    Location = directory.Path,
                    Reason = "@ReasonLockedDirectory",
                    ConfidenceScore = directory.ConfidenceScore,
                    SizeBytes = directory.SizeBytes,
                    Removed = true,
                    RequiresRestart = true
                });
            }
            else
            {
                result.FailedItems++;
                result.Warnings.Add($"Remaining directory could not be quarantined or scheduled for deletion: {directory.Path}");
            }
        }
    }

    private static int ScheduleDirectoryTreeForDeletion(string root, CancellationToken cancellationToken)
    {
        if (!Directory.Exists(root) || IsReparsePoint(root))
        {
            return 0;
        }

        int scheduled = 0;
        var directories = new List<string>();
        try
        {
            foreach (string directory in Directory.EnumerateDirectories(root, "*", new EnumerationOptions
                     {
                         RecurseSubdirectories = true,
                         IgnoreInaccessible = true,
                         ReturnSpecialDirectories = false,
                         AttributesToSkip = FileAttributes.ReparsePoint,
                         MaxRecursionDepth = 16
                     }))
            {
                cancellationToken.ThrowIfCancellationRequested();
                directories.Add(directory);
            }

            foreach (string file in Directory.EnumerateFiles(root, "*", new EnumerationOptions
                     {
                         RecurseSubdirectories = true,
                         IgnoreInaccessible = true,
                         ReturnSpecialDirectories = false,
                         AttributesToSkip = FileAttributes.ReparsePoint,
                         MaxRecursionDepth = 16
                     }))
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (MoveFileEx(file, null, MoveFileDelayUntilReboot))
                {
                    scheduled++;
                }
            }

            foreach (string directory in directories.OrderByDescending(path => path.Length))
            {
                if (MoveFileEx(directory, null, MoveFileDelayUntilReboot))
                {
                    scheduled++;
                }
            }

            if (MoveFileEx(root, null, MoveFileDelayUntilReboot))
            {
                scheduled++;
            }
        }
        catch (Exception ex)
        {
            AppLogger.Error($"Could not schedule directory tree for deletion: {root}", ex);
        }

        return scheduled;
    }

    private static void RemoveRegistryTree(
        RegistryKey baseKey,
        string keyPath,
        RegistryHive hive,
        RegistryView view,
        List<RegistryBackupRecord> backup,
        DeepUninstallResult result,
        ref int backedUpKeys,
        string reason,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(keyPath)
            || keyPath.Equals("Software", StringComparison.OrdinalIgnoreCase)
            || (keyPath.StartsWith(@"Software\Microsoft\Windows", StringComparison.OrdinalIgnoreCase)
                && !keyPath.StartsWith(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\", StringComparison.OrdinalIgnoreCase))
            || (keyPath.StartsWith(@"Software\Classes\CLSID", StringComparison.OrdinalIgnoreCase)
                && !IsExactClsidKey(keyPath))
            || keyPath.StartsWith(@"Software\Classes\Interface", StringComparison.OrdinalIgnoreCase))
        {
            result.SkippedItems++;
            return;
        }

        if (backedUpKeys >= MaximumRegistryKeysBackedUp)
        {
            result.SkippedItems++;
            result.Warnings.Add("The registry backup safety limit was reached; additional keys were left unchanged.");
            return;
        }

        using RegistryKey? existing = baseKey.OpenSubKey(keyPath, writable: false);
        if (existing is null)
        {
            return;
        }

        CaptureRegistryTree(existing, hive, view, keyPath, backup, ref backedUpKeys, cancellationToken);
        int separator = keyPath.LastIndexOf('\\');
        if (separator <= 0)
        {
            result.SkippedItems++;
            return;
        }

        string parentPath = keyPath[..separator];
        string childName = keyPath[(separator + 1)..];
        try
        {
            using RegistryKey? parent = baseKey.OpenSubKey(parentPath, writable: true);
            if (parent is null)
            {
                result.SkippedItems++;
                return;
            }

            parent.DeleteSubKeyTree(childName, throwOnMissingSubKey: false);
            result.RegistryKeysRemoved++;
            result.Artifacts.Add(new DeepUninstallArtifact
            {
                Kind = DeepUninstallArtifactKind.RegistryKey,
                Name = childName,
                Location = $"{hive}/{view}/{keyPath}",
                Reason = reason,
                ConfidenceScore = 98,
                Removed = true
            });
        }
        catch (Exception ex)
        {
            result.FailedItems++;
            result.Warnings.Add($"Could not remove registry key {hive}/{view}/{keyPath}: {ex.Message}");
        }
    }

    private static bool IsExactClsidKey(string keyPath)
    {
        const string prefix = @"Software\Classes\CLSID\";
        if (!keyPath.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        string remainder = keyPath[prefix.Length..];
        return !remainder.Contains('\\') && Guid.TryParse(remainder.Trim('{', '}'), out _);
    }

    private static void CaptureRegistryTree(
        RegistryKey key,
        RegistryHive hive,
        RegistryView view,
        string keyPath,
        List<RegistryBackupRecord> backup,
        ref int count,
        CancellationToken cancellationToken)
    {
        if (count >= MaximumRegistryKeysBackedUp)
        {
            return;
        }

        cancellationToken.ThrowIfCancellationRequested();
        var values = new List<RegistryBackupValue>();
        foreach (string valueName in key.GetValueNames())
        {
            object? value = key.GetValue(valueName, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
            values.Add(new RegistryBackupValue
            {
                Name = valueName,
                Kind = SafeRegistryValueKind(key, valueName).ToString(),
                Value = SerializeRegistryValue(value)
            });
        }

        backup.Add(new RegistryBackupRecord
        {
            Hive = hive.ToString(),
            View = view.ToString(),
            KeyPath = keyPath,
            Values = values
        });
        count++;

        foreach (string subName in SafeSubKeyNames(key))
        {
            if (count >= MaximumRegistryKeysBackedUp)
            {
                break;
            }

            using RegistryKey? child = key.OpenSubKey(subName, writable: false);
            if (child is not null)
            {
                CaptureRegistryTree(child, hive, view, $@"{keyPath}\{subName}", backup, ref count, cancellationToken);
            }
        }
    }

    private static RegistryBackupRecord CaptureRegistryValue(
        RegistryHive hive,
        RegistryView view,
        string keyPath,
        string valueName,
        object? value,
        RegistryValueKind kind)
        => new()
        {
            Hive = hive.ToString(),
            View = view.ToString(),
            KeyPath = keyPath,
            Values =
            [
                new RegistryBackupValue
                {
                    Name = valueName,
                    Kind = kind.ToString(),
                    Value = SerializeRegistryValue(value)
                }
            ]
        };

    private static bool MatchesOriginalRegistryIdentity(InstalledApp app, RegistryHive hive, RegistryView view)
        => !string.IsNullOrWhiteSpace(app.RegistryKeyPath)
           && string.Equals(app.RegistryHiveName, hive.ToString(), StringComparison.OrdinalIgnoreCase)
           && string.Equals(app.RegistryViewName, view.ToString(), StringComparison.OrdinalIgnoreCase);

    private static bool ReferencesOwnedLocation(
        string value,
        InstalledApp app,
        IReadOnlyCollection<string> tokens,
        IReadOnlyCollection<OwnedPathCandidate> directories)
        => (!string.IsNullOrWhiteSpace(app.InstallLocation)
            && value.Contains(app.InstallLocation, StringComparison.OrdinalIgnoreCase))
           || directories.Any(directory => value.Contains(directory.Path, StringComparison.OrdinalIgnoreCase))
           || IsStrongIdentityMatch(value, tokens);

    private static bool CommandExecutableIsMissing(string command)
    {
        string path = ExtractExecutablePath(command);
        return !string.IsNullOrWhiteSpace(path)
               && !File.Exists(Environment.ExpandEnvironmentVariables(path));
    }

    private static string ReadRegistryDefault(RegistryKey baseKey, string keyPath)
    {
        try
        {
            using RegistryKey? key = baseKey.OpenSubKey(keyPath, writable: false);
            return key?.GetValue(null)?.ToString() ?? string.Empty;
        }
        catch
        {
            return string.Empty;
        }
    }

    private static string ExtractExecutablePath(string command)
    {
        string expanded = Environment.ExpandEnvironmentVariables(command ?? string.Empty).Trim();
        if (expanded.Length == 0)
        {
            return string.Empty;
        }

        if (expanded[0] == '"')
        {
            int end = expanded.IndexOf('"', 1);
            return end > 1 ? expanded[1..end] : string.Empty;
        }

        int exe = expanded.IndexOf(".exe", StringComparison.OrdinalIgnoreCase);
        if (exe >= 0)
        {
            return expanded[..(exe + 4)].Trim();
        }

        int space = expanded.IndexOf(' ');
        return space > 0 ? expanded[..space] : expanded;
    }

    private static bool ContainsOwnedBinary(string directory, InstalledApp app, IReadOnlyCollection<string> tokens)
    {
        try
        {
            var options = new EnumerationOptions
            {
                RecurseSubdirectories = true,
                IgnoreInaccessible = true,
                ReturnSpecialDirectories = false,
                AttributesToSkip = FileAttributes.ReparsePoint,
                MaxRecursionDepth = 2
            };

            foreach (string file in Directory.EnumerateFiles(directory, "*", options)
                         .Where(file => Path.GetExtension(file).Equals(".exe", StringComparison.OrdinalIgnoreCase)
                                        || Path.GetExtension(file).Equals(".dll", StringComparison.OrdinalIgnoreCase))
                         .Take(60))
            {
                FileVersionInfo info = FileVersionInfo.GetVersionInfo(file);
                bool productMatch = IsStrongIdentityMatch(info.ProductName ?? string.Empty, tokens)
                                    || IsStrongIdentityMatch(info.FileDescription ?? string.Empty, tokens)
                                    || IsStrongIdentityMatch(Path.GetFileNameWithoutExtension(file), tokens);
                string normalizedCompany = Normalize(info.CompanyName);
                string normalizedPublisher = Normalize(app.Publisher);
                bool publisherMatch = string.IsNullOrWhiteSpace(app.Publisher)
                                      || (normalizedCompany.Length >= 4
                                          && (normalizedCompany.Contains(normalizedPublisher, StringComparison.OrdinalIgnoreCase)
                                              || normalizedPublisher.Contains(normalizedCompany, StringComparison.OrdinalIgnoreCase)));
                if (productMatch && publisherMatch)
                {
                    return true;
                }
            }
        }
        catch
        {
            // Inaccessible metadata does not prove ownership.
        }

        return false;
    }

    private static bool SafeFileContainsIdentity(string path, InstalledApp app, IReadOnlyCollection<string> tokens)
    {
        try
        {
            var info = new FileInfo(path);
            if (info.Length > 1024 * 1024)
            {
                return false;
            }

            string content = File.ReadAllText(path);
            return (!string.IsNullOrWhiteSpace(app.InstallLocation)
                    && content.Contains(app.InstallLocation, StringComparison.OrdinalIgnoreCase))
                   || IsStrongIdentityMatch(content, tokens);
        }
        catch
        {
            return false;
        }
    }

    private static bool IsApprovedApplicationDirectory(string path)
    {
        string fullPath = TryFullPath(path);
        if (string.IsNullOrWhiteSpace(fullPath) || !Directory.Exists(fullPath))
        {
            return false;
        }

        string? root = GetApplicationRoots().FirstOrDefault(candidate =>
            PathSafetyService.IsPathUnder(fullPath, candidate)
            && !string.Equals(fullPath, candidate, StringComparison.OrdinalIgnoreCase));
        if (string.IsNullOrWhiteSpace(root))
        {
            return false;
        }

        string relative = Path.GetRelativePath(root, fullPath);
        string[] parts = relative.Split(
            new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar },
            StringSplitOptions.RemoveEmptyEntries);
        return parts.Length is >= 1 and <= 4
               && !parts.Any(part => BlockedDirectoryParts.Contains(part));
    }

    private static bool IsApprovedShortcutDirectory(string path)
    {
        string fullPath = TryFullPath(path);
        if (string.IsNullOrWhiteSpace(fullPath) || !Directory.Exists(fullPath) || IsReparsePoint(fullPath))
        {
            return false;
        }

        string? root = GetShortcutRoots().FirstOrDefault(candidate =>
            PathSafetyService.IsPathUnder(fullPath, candidate)
            && !string.Equals(fullPath, candidate, StringComparison.OrdinalIgnoreCase));
        if (string.IsNullOrWhiteSpace(root))
        {
            return false;
        }

        string relative = Path.GetRelativePath(root, fullPath);
        string[] parts = relative.Split(
            new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar },
            StringSplitOptions.RemoveEmptyEntries);
        return parts.Length is >= 1 and <= 3
               && !parts.Any(part => BlockedDirectoryParts.Contains(part));
    }

    private static List<OwnedPathCandidate> RemoveParentChildDuplicates(IEnumerable<OwnedPathCandidate> items)
    {
        List<OwnedPathCandidate> ordered = items
            .OrderByDescending(item => item.ConfidenceScore)
            .ThenBy(item => item.Path.Length)
            .ToList();
        var result = new List<OwnedPathCandidate>();
        foreach (OwnedPathCandidate item in ordered)
        {
            if (result.Any(existing => PathSafetyService.IsPathUnder(item.Path, existing.Path)))
            {
                continue;
            }

            result.RemoveAll(existing => PathSafetyService.IsPathUnder(existing.Path, item.Path));
            result.Add(item);
        }
        return result;
    }

    private static void AddDirectoryCandidate(
        IDictionary<string, OwnedPathCandidate> candidates,
        string path,
        int confidence,
        string reason)
    {
        string fullPath = TryFullPath(path);
        if (string.IsNullOrWhiteSpace(fullPath) || !Directory.Exists(fullPath))
        {
            return;
        }

        var candidate = new OwnedPathCandidate(
            fullPath,
            IsDirectory: true,
            ConfidenceScore: confidence,
            Reason: reason,
            SizeBytes: 0);
        if (!candidates.TryGetValue(fullPath, out OwnedPathCandidate? existing)
            || candidate.ConfidenceScore > existing.ConfidenceScore)
        {
            candidates[fullPath] = candidate;
        }
    }

    private static bool IsPublisherDirectory(string directoryName, string publisher)
    {
        string candidate = Normalize(directoryName);
        string expected = Normalize(publisher);
        return expected.Length >= 4
               && candidate.Length >= 4
               && (candidate.Equals(expected, StringComparison.OrdinalIgnoreCase)
                   || (expected.Length >= 6 && candidate.Contains(expected, StringComparison.OrdinalIgnoreCase))
                   || (candidate.Length >= 6 && expected.Contains(candidate, StringComparison.OrdinalIgnoreCase)));
    }

    private static IReadOnlyList<string> GetApplicationRoots()
    {
        var roots = new List<string>
        {
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            Path.GetTempPath(),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "Temp")
        };

        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string? userProfile = string.IsNullOrWhiteSpace(local) ? null : Directory.GetParent(local)?.Parent?.FullName;
        if (!string.IsNullOrWhiteSpace(userProfile))
        {
            roots.Add(Path.Combine(userProfile, "AppData", "LocalLow"));
        }

        foreach (DriveInfo drive in SafeFixedDrives())
        {
            foreach (string directoryName in new[] { "Program Files", "Program Files (x86)", "ProgramData", "Apps", "Applications", "Programs", "Software" })
            {
                string candidate = Path.Combine(drive.RootDirectory.FullName, directoryName);
                if (Directory.Exists(candidate))
                {
                    roots.Add(candidate);
                }
            }
        }

        return roots
            .Where(root => !string.IsNullOrWhiteSpace(root))
            .Select(TryFullPath)
            .Where(root => !string.IsNullOrWhiteSpace(root) && Directory.Exists(root))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderByDescending(root => root.Length)
            .ToList();
    }

    private static IEnumerable<DriveInfo> SafeFixedDrives()
    {
        try
        {
            return DriveInfo.GetDrives()
                .Where(drive => drive.DriveType == DriveType.Fixed && drive.IsReady)
                .ToArray();
        }
        catch
        {
            return [];
        }
    }

    private static IReadOnlyList<string> GetShortcutRoots()
        => new[]
        {
            Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonDesktopDirectory),
            Environment.GetFolderPath(Environment.SpecialFolder.Programs),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonPrograms),
            Environment.GetFolderPath(Environment.SpecialFolder.Startup),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonStartup),
            Environment.GetFolderPath(Environment.SpecialFolder.StartMenu),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonStartMenu)
        }
        .Where(root => !string.IsNullOrWhiteSpace(root))
        .Select(TryFullPath)
        .Where(root => !string.IsNullOrWhiteSpace(root))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .OrderByDescending(root => root.Length)
        .ToList();

    private static IEnumerable<(RegistryHive Hive, RegistryView View)> RegistryScopes()
    {
        yield return (RegistryHive.CurrentUser, RegistryView.Registry64);
        yield return (RegistryHive.CurrentUser, RegistryView.Registry32);
        yield return (RegistryHive.LocalMachine, RegistryView.Registry64);
        yield return (RegistryHive.LocalMachine, RegistryView.Registry32);
    }

    private static IEnumerable<string> SafeSubKeyNames(RegistryKey key)
    {
        try { return key.GetSubKeyNames(); }
        catch { return []; }
    }

    private static bool IsProtectedSoftwareKey(string name)
        => name.Equals("Microsoft", StringComparison.OrdinalIgnoreCase)
           || name.Equals("Classes", StringComparison.OrdinalIgnoreCase)
           || name.Equals("Policies", StringComparison.OrdinalIgnoreCase)
           || name.Equals("Windows", StringComparison.OrdinalIgnoreCase);

    private static RegistryValueKind SafeRegistryValueKind(RegistryKey key, string valueName)
    {
        try { return key.GetValueKind(valueName); }
        catch { return RegistryValueKind.String; }
    }

    private static object? SerializeRegistryValue(object? value)
        => value switch
        {
            byte[] bytes => Convert.ToBase64String(bytes),
            string[] strings => strings,
            _ => value?.ToString()
        };

    private static async Task<int> RunToolAsync(
        string fileName,
        string arguments,
        CancellationToken cancellationToken,
        bool acceptNonZero)
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

    private static long SafeDirectorySize(string path, CancellationToken cancellationToken)
    {
        long total = 0;
        int count = 0;
        try
        {
            foreach (string file in Directory.EnumerateFiles(path, "*", new EnumerationOptions
                     {
                         RecurseSubdirectories = true,
                         IgnoreInaccessible = true,
                         ReturnSpecialDirectories = false,
                         AttributesToSkip = FileAttributes.ReparsePoint,
                         MaxRecursionDepth = 16
                     }))
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (++count > 200000)
                {
                    break;
                }
                total += SafeFileLength(file);
            }
        }
        catch
        {
            // Best-effort size only.
        }
        return total;
    }

    private static long SafeFileLength(string path)
    {
        try { return new FileInfo(path).Length; }
        catch { return 0; }
    }

    private static DateTime SafeFileLastWrite(string path)
    {
        try { return File.GetLastWriteTime(path); }
        catch { return DateTime.Now; }
    }

    private static DateTime SafeDirectoryLastWriteUtc(string path)
    {
        try { return Directory.GetLastWriteTimeUtc(path); }
        catch { return DateTime.UtcNow; }
    }

    private static bool IsReparsePoint(string path)
    {
        try { return File.GetAttributes(path).HasFlag(FileAttributes.ReparsePoint); }
        catch { return true; }
    }

    private static string TryFullPath(string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return string.Empty;
        }
        try { return Path.TrimEndingDirectorySeparator(Path.GetFullPath(Environment.ExpandEnvironmentVariables(path.Trim().Trim('"')))); }
        catch { return string.Empty; }
    }

    private static string SafeFileName(string? path)
    {
        try { return Path.GetFileName(Path.TrimEndingDirectorySeparator(path ?? string.Empty)); }
        catch { return string.Empty; }
    }

    private static void AddIdentityToken(ISet<string> tokens, string? value)
    {
        string normalized = Normalize(value);
        if (normalized.Length >= 4 && !BlockedIdentityTokens.Contains(normalized))
        {
            tokens.Add(normalized);
        }
    }

    private static IEnumerable<string> SplitIdentityWords(string value)
        => value.Split(new[] { ' ', '-', '_', '.', '(', ')', '[', ']' }, StringSplitOptions.RemoveEmptyEntries)
            .Select(Normalize)
            .Where(word => word.Length >= 8 && !BlockedIdentityTokens.Contains(word));

    private static string RemoveVersionLikeSuffix(string value)
    {
        string[] parts = value.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return string.Join(' ', parts.Where(part => !part.Any(char.IsDigit)));
    }

    private static string Normalize(string? value)
        => new string((value ?? string.Empty).ToLowerInvariant().Where(char.IsLetterOrDigit).ToArray());

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool MoveFileEx(string existingFileName, string? newFileName, int flags);

    private sealed record OwnedPathCandidate(
        string Path,
        bool IsDirectory,
        int ConfidenceScore,
        string Reason,
        long SizeBytes);

    private sealed class RegistryBackupRecord
    {
        public string Hive { get; init; } = string.Empty;
        public string View { get; init; } = string.Empty;
        public string KeyPath { get; init; } = string.Empty;
        public List<RegistryBackupValue> Values { get; init; } = [];
    }

    private sealed class RegistryBackupValue
    {
        public string Name { get; init; } = string.Empty;
        public string Kind { get; init; } = string.Empty;
        public object? Value { get; init; }
    }
}
