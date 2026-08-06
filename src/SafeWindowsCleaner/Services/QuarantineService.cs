using System.Text.Json;
using Microsoft.VisualBasic.FileIO;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class QuarantineService
{
    private const string ManifestFileName = "manifest.json";
    private const string ApplicationDirectoryPolicy = "ApplicationDirectory";
    private const string DiskFilePolicy = "DiskFile";
    private const string ConfirmedApplicationDirectoryPolicy = "ConfirmedApplicationDirectory";
    private const string ConfirmedApplicationFilePolicy = "ConfirmedApplicationFile";

    private static readonly HashSet<string> BlockedApplicationDirectoryNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "Microsoft", "Windows", "Packages", "Programs", "Common Files", "Temp",
        "System32", "WindowsApps", "ModifiableWindowsApps", "Users", "ProgramData"
    };

    private static readonly HashSet<string> BlockedDiskRootDirectoryNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "Windows", "Program Files", "Program Files (x86)", "ProgramData", "System Volume Information",
        "$Recycle.Bin", "Recovery", "Boot", "EFI", "PerfLogs"
    };

    private static readonly HashSet<string> BlockedSystemFileNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "pagefile.sys", "hiberfil.sys", "swapfile.sys", "bootmgr", "bootnxt", "ntldr", "ntdetect.com"
    };

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

    public static string QuarantineRoot { get; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "SafeWindowsCleaner",
        "Quarantine");

    public Task<List<QuarantineItem>> GetItemsAsync(CancellationToken cancellationToken = default)
    {
        return Task.Run(() =>
        {
            Directory.CreateDirectory(QuarantineRoot);
            var items = new List<QuarantineItem>();

            foreach (string sessionDirectory in Directory.EnumerateDirectories(QuarantineRoot, "*", System.IO.SearchOption.TopDirectoryOnly))
            {
                cancellationToken.ThrowIfCancellationRequested();
                QuarantineManifest? manifest = ReadManifest(sessionDirectory);
                if (manifest is null)
                {
                    continue;
                }

                manifest.Items ??= [];
                string actualSessionId = Path.GetFileName(sessionDirectory);

                foreach (QuarantineEntry entry in manifest.Items)
                {
                    string quarantinedPath = Path.GetFullPath(Path.Combine(sessionDirectory, entry.StoredName));
                    string policy = NormalizePolicy(entry.SourcePolicy);
                    try
                    {
                        EnsurePathInsideQuarantine(quarantinedPath);
                        ValidateOriginalPath(entry.OriginalPath, policy);
                    }
                    catch (Exception ex)
                    {
                        AppLogger.Error($"Ignored unsafe quarantine entry: {entry.StoredName}", ex);
                        continue;
                    }

                    bool isDirectory = Directory.Exists(quarantinedPath);
                    bool isFile = File.Exists(quarantinedPath);
                    if (!isDirectory && !isFile)
                    {
                        continue;
                    }

                    if (entry.IsDirectory.HasValue && entry.IsDirectory.Value != isDirectory)
                    {
                        AppLogger.Error($"Ignored quarantine entry with mismatched item type: {entry.StoredName}");
                        continue;
                    }

                    if ((IsDirectoryPolicy(policy) && !isDirectory)
                        || (IsFilePolicy(policy) && !isFile))
                    {
                        AppLogger.Error($"Ignored quarantine entry whose policy does not match its item type: {entry.StoredName}");
                        continue;
                    }

                    items.Add(new QuarantineItem
                    {
                        SessionId = actualSessionId,
                        Name = entry.Name,
                        OriginalPath = entry.OriginalPath,
                        QuarantinedPath = quarantinedPath,
                        QuarantinedAt = entry.QuarantinedAt,
                        SizeBytes = entry.SizeBytes,
                        IsDirectory = isDirectory,
                        SourcePolicy = policy
                    });
                }
            }

            return items
                .OrderByDescending(item => item.QuarantinedAt)
                .ThenBy(item => item.Name, StringComparer.CurrentCultureIgnoreCase)
                .ToList();
        }, cancellationToken);
    }

    public Task<QuarantineOperationResult> QuarantineAsync(
        IEnumerable<LeftoverItem> items,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        List<QuarantineSource> sources = items
            .Where(item => item.IsSelected && item.IsQuarantinable)
            .Select(item => new QuarantineSource(
                item.Name,
                item.Path,
                item.SizeBytes,
                IsDirectory: true,
                ApplicationDirectoryPolicy))
            .ToList();

        return QuarantineSourcesAsync(sources, progress, cancellationToken);
    }

    public Task<QuarantineOperationResult> QuarantineDiskFilesAsync(
        IEnumerable<DiskFileItem> items,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        List<QuarantineSource> sources = items
            .Where(item => item.IsSelected && item.IsSafeToQuarantine)
            .GroupBy(item => Path.GetFullPath(item.Path), StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .Select(item => new QuarantineSource(
                item.Name,
                item.Path,
                item.SizeBytes,
                IsDirectory: false,
                DiskFilePolicy))
            .ToList();

        return QuarantineSourcesAsync(sources, progress, cancellationToken);
    }

    public Task<QuarantineOperationResult> QuarantineConfirmedApplicationDirectoriesAsync(
        IEnumerable<LeftoverItem> items,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        List<QuarantineSource> sources = items
            .Where(item => item.IsSelected && item.IsQuarantinable)
            .GroupBy(item => Path.GetFullPath(item.Path), StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .Select(item => new QuarantineSource(
                item.Name,
                item.Path,
                item.SizeBytes,
                IsDirectory: true,
                ConfirmedApplicationDirectoryPolicy))
            .ToList();

        return QuarantineSourcesAsync(sources, progress, cancellationToken);
    }

    public Task<QuarantineOperationResult> QuarantineConfirmedApplicationFilesAsync(
        IEnumerable<DiskFileItem> items,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        List<QuarantineSource> sources = items
            .Where(item => item.IsSelected && item.IsSafeToQuarantine)
            .GroupBy(item => Path.GetFullPath(item.Path), StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .Select(item => new QuarantineSource(
                item.Name,
                item.Path,
                item.SizeBytes,
                IsDirectory: false,
                ConfirmedApplicationFilePolicy))
            .ToList();

        return QuarantineSourcesAsync(sources, progress, cancellationToken);
    }

    private static Task<QuarantineOperationResult> QuarantineSourcesAsync(
        IReadOnlyCollection<QuarantineSource> sources,
        IProgress<string>? progress,
        CancellationToken cancellationToken)
    {
        return Task.Run(() =>
        {
            if (sources.Count == 0)
            {
                return new QuarantineOperationResult(0, 0, 0, 0);
            }

            Directory.CreateDirectory(QuarantineRoot);
            string sessionId = $"{DateTime.UtcNow:yyyyMMdd-HHmmss}-{Guid.NewGuid():N}";
            string sessionDirectory = Path.Combine(QuarantineRoot, sessionId);
            Directory.CreateDirectory(sessionDirectory);

            var manifest = new QuarantineManifest
            {
                SessionId = sessionId,
                CreatedAt = DateTimeOffset.UtcNow
            };

            int succeeded = 0;
            int failed = 0;
            int skipped = 0;
            long bytes = 0;

            foreach (QuarantineSource source in sources)
            {
                cancellationToken.ThrowIfCancellationRequested();
                progress?.Report(LocalizationService.Format("@MovingToQuarantine", LocalizationService.ActiveLanguageCode, source.Name));

                try
                {
                    bool exists = source.IsDirectory ? Directory.Exists(source.Path) : File.Exists(source.Path);
                    if (!exists)
                    {
                        skipped++;
                        continue;
                    }

                    EnsureSafeSourcePath(source);
                    string storedName = CreateStoredName(manifest.Items.Count + 1, source.Name);
                    string destination = Path.Combine(sessionDirectory, storedName);

                    MoveItem(source.Path, destination, source.IsDirectory);

                    var entry = new QuarantineEntry
                    {
                        Name = source.Name,
                        OriginalPath = Path.GetFullPath(source.Path),
                        StoredName = storedName,
                        QuarantinedAt = DateTimeOffset.UtcNow,
                        SizeBytes = source.SizeBytes,
                        IsDirectory = source.IsDirectory,
                        SourcePolicy = source.SourcePolicy
                    };
                    manifest.Items.Add(entry);

                    try
                    {
                        WriteManifest(sessionDirectory, manifest);
                    }
                    catch
                    {
                        manifest.Items.Remove(entry);
                        if (!ItemExists(source.Path, source.IsDirectory) && ItemExists(destination, source.IsDirectory))
                        {
                            MoveItem(destination, source.Path, source.IsDirectory);
                        }

                        throw;
                    }

                    succeeded++;
                    bytes += source.SizeBytes;
                }
                catch (Exception ex)
                {
                    failed++;
                    AppLogger.Error($"Could not quarantine item: {source.Path}", ex);
                }
            }

            if (manifest.Items.Count == 0)
            {
                TryDeleteEmptyDirectory(sessionDirectory);
            }

            return new QuarantineOperationResult(succeeded, failed, skipped, bytes);
        }, cancellationToken);
    }

    public Task<QuarantineOperationResult> RestoreAsync(
        IEnumerable<QuarantineItem> items,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        return Task.Run(() =>
        {
            int succeeded = 0;
            int failed = 0;
            int skipped = 0;
            long bytes = 0;

            foreach (IGrouping<string, QuarantineItem> sessionGroup in items
                         .Where(item => item.IsSelected)
                         .GroupBy(item => item.SessionId, StringComparer.OrdinalIgnoreCase))
            {
                cancellationToken.ThrowIfCancellationRequested();
                string sessionDirectory = GetValidatedSessionDirectory(sessionGroup.Key);
                QuarantineManifest? manifest = ReadManifest(sessionDirectory);
                if (manifest is null)
                {
                    failed += sessionGroup.Count();
                    continue;
                }

                foreach (QuarantineItem item in sessionGroup)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    progress?.Report($"استعادة: {item.Name}");

                    try
                    {
                        EnsurePathInsideQuarantine(item.QuarantinedPath);
                        if (!ItemExists(item.QuarantinedPath, item.IsDirectory))
                        {
                            skipped++;
                            continue;
                        }

                        if (Directory.Exists(item.OriginalPath) || File.Exists(item.OriginalPath))
                        {
                            skipped++;
                            continue;
                        }

                        QuarantineEntry? manifestEntry = manifest.Items.FirstOrDefault(entry => PathsEqual(
                            Path.Combine(sessionDirectory, entry.StoredName),
                            item.QuarantinedPath));
                        if (manifestEntry is null)
                        {
                            throw new InvalidOperationException("The quarantine item is not present in its manifest.");
                        }

                        string policy = NormalizePolicy(manifestEntry.SourcePolicy);
                        bool manifestIsDirectory = manifestEntry.IsDirectory ?? item.IsDirectory;
                        if (manifestIsDirectory != item.IsDirectory || !string.Equals(policy, item.SourcePolicy, StringComparison.Ordinal))
                        {
                            throw new InvalidOperationException("The quarantine metadata does not match the selected item.");
                        }

                        if ((IsDirectoryPolicy(policy) && !item.IsDirectory)
                            || (IsFilePolicy(policy) && item.IsDirectory))
                        {
                            throw new InvalidOperationException("The quarantine policy does not allow this item type.");
                        }

                        ValidateOriginalPath(item.OriginalPath, policy);
                        string? parent = Path.GetDirectoryName(item.OriginalPath);
                        if (string.IsNullOrWhiteSpace(parent))
                        {
                            throw new InvalidOperationException("The original parent path is invalid.");
                        }

                        Directory.CreateDirectory(parent);
                        MoveItem(item.QuarantinedPath, item.OriginalPath, item.IsDirectory);

                        manifest.Items.Remove(manifestEntry);
                        try
                        {
                            WriteManifest(sessionDirectory, manifest);
                        }
                        catch
                        {
                            manifest.Items.Add(manifestEntry);
                            if (ItemExists(item.OriginalPath, item.IsDirectory)
                                && !ItemExists(item.QuarantinedPath, item.IsDirectory))
                            {
                                MoveItem(item.OriginalPath, item.QuarantinedPath, item.IsDirectory);
                            }

                            throw;
                        }

                        succeeded++;
                        bytes += item.SizeBytes;
                    }
                    catch (Exception ex)
                    {
                        failed++;
                        AppLogger.Error($"Could not restore quarantine item: {item.QuarantinedPath}", ex);
                    }
                }

                CleanupSessionIfEmpty(sessionDirectory, manifest);
            }

            return new QuarantineOperationResult(succeeded, failed, skipped, bytes);
        }, cancellationToken);
    }

    public Task<QuarantineOperationResult> DeletePermanentlyAsync(
        IEnumerable<QuarantineItem> items,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        return Task.Run(() =>
        {
            int succeeded = 0;
            int failed = 0;
            int skipped = 0;
            long bytes = 0;

            foreach (IGrouping<string, QuarantineItem> sessionGroup in items
                         .Where(item => item.IsSelected)
                         .GroupBy(item => item.SessionId, StringComparer.OrdinalIgnoreCase))
            {
                cancellationToken.ThrowIfCancellationRequested();
                string sessionDirectory = GetValidatedSessionDirectory(sessionGroup.Key);
                QuarantineManifest? manifest = ReadManifest(sessionDirectory);
                if (manifest is null)
                {
                    failed += sessionGroup.Count();
                    continue;
                }

                foreach (QuarantineItem item in sessionGroup)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    progress?.Report($"حذف نهائي من الحجر: {item.Name}");

                    try
                    {
                        EnsurePathInsideQuarantine(item.QuarantinedPath);
                        bool exists = ItemExists(item.QuarantinedPath, item.IsDirectory);
                        if (!exists)
                        {
                            skipped++;
                        }
                        else
                        {
                            DeleteItem(item.QuarantinedPath, item.IsDirectory);
                            succeeded++;
                            bytes += item.SizeBytes;
                        }

                        manifest.Items.RemoveAll(entry => PathsEqual(
                            Path.Combine(sessionDirectory, entry.StoredName),
                            item.QuarantinedPath));
                        WriteManifest(sessionDirectory, manifest);
                    }
                    catch (Exception ex)
                    {
                        failed++;
                        AppLogger.Error($"Could not permanently delete quarantine item: {item.QuarantinedPath}", ex);
                    }
                }

                CleanupSessionIfEmpty(sessionDirectory, manifest);
            }

            return new QuarantineOperationResult(succeeded, failed, skipped, bytes);
        }, cancellationToken);
    }

    private static void EnsureSafeSourcePath(QuarantineSource source)
    {
        string fullPath = Path.GetFullPath(source.Path);
        ValidateOriginalPath(fullPath, source.SourcePolicy);

        FileAttributes attributes = File.GetAttributes(fullPath);
        if ((attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new InvalidOperationException("Reparse points cannot be quarantined.");
        }

        if (source.IsDirectory != attributes.HasFlag(FileAttributes.Directory))
        {
            throw new InvalidOperationException("The selected item type does not match the file system.");
        }
    }

    private static void ValidateOriginalPath(string path, string policy)
    {
        switch (NormalizePolicy(policy))
        {
            case ApplicationDirectoryPolicy:
                EnsureApprovedApplicationPath(path);
                break;
            case DiskFilePolicy:
                EnsureApprovedDiskFilePath(path);
                break;
            case ConfirmedApplicationDirectoryPolicy:
                EnsureApprovedConfirmedApplicationDirectory(path);
                break;
            case ConfirmedApplicationFilePolicy:
                EnsureApprovedConfirmedApplicationFile(path);
                break;
            default:
                throw new InvalidOperationException("The quarantine source policy is invalid.");
        }
    }

    private static string NormalizePolicy(string? policy)
        => string.IsNullOrWhiteSpace(policy) ? ApplicationDirectoryPolicy : policy;

    private static bool IsDirectoryPolicy(string policy)
        => string.Equals(policy, ApplicationDirectoryPolicy, StringComparison.Ordinal)
           || string.Equals(policy, ConfirmedApplicationDirectoryPolicy, StringComparison.Ordinal);

    private static bool IsFilePolicy(string policy)
        => string.Equals(policy, DiskFilePolicy, StringComparison.Ordinal)
           || string.Equals(policy, ConfirmedApplicationFilePolicy, StringComparison.Ordinal);

    private static void EnsureApprovedApplicationPath(string path)
    {
        string fullPath = Path.TrimEndingDirectorySeparator(Path.GetFullPath(path));
        var allowedRoots = new[]
        {
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86)
        }
        .Where(root => !string.IsNullOrWhiteSpace(root))
        .Select(root => Path.TrimEndingDirectorySeparator(Path.GetFullPath(root)))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .ToList();

        bool isDirectChild = allowedRoots.Any(root =>
            string.Equals(Path.GetDirectoryName(fullPath), root, StringComparison.OrdinalIgnoreCase));

        if (!isDirectChild)
        {
            throw new InvalidOperationException("Only direct child folders of approved application-data roots are allowed.");
        }

        string directoryName = Path.GetFileName(fullPath);
        if (string.IsNullOrWhiteSpace(directoryName) || BlockedApplicationDirectoryNames.Contains(directoryName))
        {
            throw new InvalidOperationException("The selected application directory is protected.");
        }
    }

    private static void EnsureApprovedDiskFilePath(string path)
    {
        string fullPath = Path.GetFullPath(path);
        if (PathSafetyService.IsProtectedSystemPath(fullPath))
        {
            throw new InvalidOperationException("The selected file is inside a protected system path.");
        }

        if (fullPath.IndexOf(':', 2) >= 0)
        {
            throw new InvalidOperationException("Alternate data streams are not supported.");
        }

        if (IsPathUnder(fullPath, QuarantineRoot))
        {
            throw new InvalidOperationException("A quarantine item cannot be quarantined again.");
        }

        string fileName = Path.GetFileName(fullPath);
        if (string.IsNullOrWhiteSpace(fileName) || BlockedSystemFileNames.Contains(fileName))
        {
            throw new InvalidOperationException("The selected system file is protected.");
        }

        string extension = Path.GetExtension(fullPath);
        if (extension.Equals(".sys", StringComparison.OrdinalIgnoreCase)
            || extension.Equals(".drv", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Driver files are protected.");
        }

        string windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        string systemDrive = Path.GetPathRoot(windows) ?? string.Empty;
        string itemDrive = Path.GetPathRoot(fullPath) ?? string.Empty;
        if (string.IsNullOrWhiteSpace(itemDrive))
        {
            throw new InvalidOperationException("The selected file drive is invalid.");
        }

        if (string.Equals(systemDrive, itemDrive, StringComparison.OrdinalIgnoreCase))
        {
            string userProfile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            string roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);

            if (string.IsNullOrWhiteSpace(userProfile) || !IsPathUnder(fullPath, userProfile))
            {
                throw new InvalidOperationException("Only personal user files can be quarantined from the Windows drive.");
            }

            if (IsPathUnder(fullPath, roaming) || IsPathUnder(fullPath, local))
            {
                throw new InvalidOperationException("Application data files are protected in the disk analyzer.");
            }
        }
        else
        {
            string relativeToDrive = Path.GetRelativePath(itemDrive, fullPath);
            string firstPart = relativeToDrive.Split(
                new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar },
                StringSplitOptions.RemoveEmptyEntries).FirstOrDefault() ?? string.Empty;
            if (BlockedDiskRootDirectoryNames.Contains(firstPart))
            {
                throw new InvalidOperationException("The selected file is inside a protected system directory.");
            }
        }
    }

    private static void EnsureApprovedConfirmedApplicationDirectory(string path)
    {
        string fullPath = Path.TrimEndingDirectorySeparator(Path.GetFullPath(path));
        string? matchedRoot = GetApprovedApplicationRoots()
            .Concat(GetShortcutRoots())
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault(root => PathSafetyService.IsPathUnder(fullPath, root)
                                    && !string.Equals(fullPath, root, StringComparison.OrdinalIgnoreCase));
        if (string.IsNullOrWhiteSpace(matchedRoot))
        {
            throw new InvalidOperationException("The confirmed application directory is outside approved application roots.");
        }

        string relative = Path.GetRelativePath(matchedRoot, fullPath);
        string[] parts = relative.Split(
            new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar },
            StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length is < 1 or > 4)
        {
            throw new InvalidOperationException("The confirmed application directory depth is not allowed.");
        }

        if (parts.Any(part => BlockedApplicationDirectoryNames.Contains(part)))
        {
            throw new InvalidOperationException("The confirmed application directory contains a protected path component.");
        }
    }

    private static void EnsureApprovedConfirmedApplicationFile(string path)
    {
        string fullPath = Path.GetFullPath(path);
        string fileName = Path.GetFileName(fullPath);
        if (string.IsNullOrWhiteSpace(fileName) || BlockedSystemFileNames.Contains(fileName))
        {
            throw new InvalidOperationException("The confirmed application file is protected.");
        }

        string extension = Path.GetExtension(fullPath);
        if (extension.Equals(".sys", StringComparison.OrdinalIgnoreCase)
            || extension.Equals(".drv", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Driver files are protected.");
        }

        var allowedRoots = GetApprovedApplicationRoots()
            .Concat(GetShortcutRoots())
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
        if (!allowedRoots.Any(root => PathSafetyService.IsPathUnder(fullPath, root)))
        {
            throw new InvalidOperationException("The confirmed application file is outside approved roots.");
        }
    }

    private static IReadOnlyList<string> GetApprovedApplicationRoots()
    {
        var roots = new List<string>
        {
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
            Path.GetTempPath(),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "Temp")
        };

        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string? userProfile = string.IsNullOrWhiteSpace(local) ? null : Directory.GetParent(local)?.Parent?.FullName;
        if (!string.IsNullOrWhiteSpace(userProfile))
        {
            roots.Add(Path.Combine(userProfile, "AppData", "LocalLow"));
        }

        try
        {
            foreach (DriveInfo drive in DriveInfo.GetDrives().Where(drive => drive.DriveType == DriveType.Fixed && drive.IsReady))
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
        }
        catch
        {
            // Fixed-drive discovery is best effort; standard Windows roots remain available.
        }

        return roots
            .Where(root => !string.IsNullOrWhiteSpace(root))
            .Select(root => Path.TrimEndingDirectorySeparator(Path.GetFullPath(root)))
            .Where(Directory.Exists)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderByDescending(root => root.Length)
            .ToList();
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
        .Select(root => Path.TrimEndingDirectorySeparator(Path.GetFullPath(root)))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .OrderByDescending(root => root.Length)
        .ToList();

    private static string GetValidatedSessionDirectory(string sessionId)
    {
        if (string.IsNullOrWhiteSpace(sessionId) || sessionId.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
        {
            throw new InvalidOperationException("Invalid quarantine session identifier.");
        }

        string sessionDirectory = Path.GetFullPath(Path.Combine(QuarantineRoot, sessionId));
        EnsurePathInsideQuarantine(sessionDirectory);
        return sessionDirectory;
    }

    private static void EnsurePathInsideQuarantine(string path)
    {
        string root = Path.TrimEndingDirectorySeparator(Path.GetFullPath(QuarantineRoot)) + Path.DirectorySeparatorChar;
        string fullPath = Path.GetFullPath(path);
        if (!fullPath.StartsWith(root, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("The path is outside the quarantine directory.");
        }
    }

    private static QuarantineManifest? ReadManifest(string sessionDirectory)
    {
        try
        {
            EnsurePathInsideQuarantine(sessionDirectory);
            string manifestPath = Path.Combine(sessionDirectory, ManifestFileName);
            if (!File.Exists(manifestPath))
            {
                return null;
            }

            return JsonSerializer.Deserialize<QuarantineManifest>(File.ReadAllText(manifestPath), JsonOptions);
        }
        catch (Exception ex)
        {
            AppLogger.Error($"Could not read quarantine manifest: {sessionDirectory}", ex);
            return null;
        }
    }

    private static void WriteManifest(string sessionDirectory, QuarantineManifest manifest)
    {
        EnsurePathInsideQuarantine(sessionDirectory);
        string manifestPath = Path.Combine(sessionDirectory, ManifestFileName);
        string tempPath = manifestPath + ".tmp";
        File.WriteAllText(tempPath, JsonSerializer.Serialize(manifest, JsonOptions));
        File.Move(tempPath, manifestPath, true);
    }

    private static void CleanupSessionIfEmpty(string sessionDirectory, QuarantineManifest manifest)
    {
        if (manifest.Items.Count == 0)
        {
            TryDeleteEmptyDirectory(sessionDirectory);
        }
    }

    private static void TryDeleteEmptyDirectory(string path)
    {
        try
        {
            if (Directory.Exists(path))
            {
                Directory.Delete(path, true);
            }
        }
        catch (Exception ex)
        {
            AppLogger.Error($"Could not remove empty quarantine session: {path}", ex);
        }
    }

    private static string CreateStoredName(int index, string name)
    {
        string sanitized = string.Concat(name.Select(character =>
            Path.GetInvalidFileNameChars().Contains(character) ? '_' : character)).Trim();
        if (string.IsNullOrWhiteSpace(sanitized))
        {
            sanitized = "item";
        }

        const int maximumNameLength = 80;
        if (sanitized.Length > maximumNameLength)
        {
            string extension = Path.GetExtension(sanitized);
            if (extension.Length > 20)
            {
                extension = extension[..20];
            }

            string stem = Path.GetFileNameWithoutExtension(sanitized);
            int maximumStemLength = Math.Max(1, maximumNameLength - extension.Length);
            sanitized = stem[..Math.Min(maximumStemLength, stem.Length)] + extension;
        }

        string suffix = Guid.NewGuid().ToString("N")[..8];
        return $"{index:D3}-{sanitized}-{suffix}";
    }

    private static bool ItemExists(string path, bool isDirectory)
        => isDirectory ? Directory.Exists(path) : File.Exists(path);

    private static void MoveItem(string source, string destination, bool isDirectory)
    {
        if (isDirectory)
        {
            FileSystem.MoveDirectory(source, destination, overwrite: false);
        }
        else
        {
            FileSystem.MoveFile(source, destination, overwrite: false);
        }
    }

    private static void DeleteItem(string path, bool isDirectory)
    {
        if (isDirectory)
        {
            Directory.Delete(path, recursive: true);
        }
        else
        {
            File.Delete(path);
        }
    }

    private static bool IsPathUnder(string path, string root)
    {
        if (string.IsNullOrWhiteSpace(path) || string.IsNullOrWhiteSpace(root))
        {
            return false;
        }

        string fullRoot = Path.TrimEndingDirectorySeparator(Path.GetFullPath(root)) + Path.DirectorySeparatorChar;
        string fullPath = Path.GetFullPath(path);
        return fullPath.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase);
    }

    private static bool PathsEqual(string left, string right)
        => string.Equals(
            Path.TrimEndingDirectorySeparator(Path.GetFullPath(left)),
            Path.TrimEndingDirectorySeparator(Path.GetFullPath(right)),
            StringComparison.OrdinalIgnoreCase);

    private sealed class QuarantineManifest
    {
        public string SessionId { get; set; } = string.Empty;
        public DateTimeOffset CreatedAt { get; set; }
        public List<QuarantineEntry> Items { get; set; } = [];
    }

    private sealed class QuarantineEntry
    {
        public string Name { get; set; } = string.Empty;
        public string OriginalPath { get; set; } = string.Empty;
        public string StoredName { get; set; } = string.Empty;
        public DateTimeOffset QuarantinedAt { get; set; }
        public long SizeBytes { get; set; }
        public bool? IsDirectory { get; set; }
        public string SourcePolicy { get; set; } = ApplicationDirectoryPolicy;
    }

    private sealed record QuarantineSource(
        string Name,
        string Path,
        long SizeBytes,
        bool IsDirectory,
        string SourcePolicy);
}

public sealed record QuarantineOperationResult(
    int SucceededItems,
    int FailedItems,
    int SkippedItems,
    long BytesProcessed);
