using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using Microsoft.Win32;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class InstallMonitorService : IDisposable
{
    private const string ManifestFileName = "manifest.json";
    private const string BeforeSnapshotFileName = "before-snapshot.json";
    private const string AfterSnapshotFileName = "after-snapshot.json";
    private const string EventJournalFileName = "file-events.ndjson";
    private const int MaximumRegistryEntries = 40_000;
    private const int MaximumFileChangeItems = 5_000;
    private const int MaximumRegistryChangeItems = 7_500;
    private const int MaximumDistinctFileEvents = 75_000;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping
    };

    private static readonly JsonSerializerOptions CompactJsonOptions = new()
    {
        WriteIndented = false,
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping
    };

    private readonly InstalledAppsService _installedAppsService = new();
    private readonly object _activeLock = new();
    private ActiveInstallSession? _active;
    private bool _disposed;

    public static string MonitorRoot { get; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "SafeWindowsCleaner",
        "InstallMonitor");

    public bool HasActiveSession
    {
        get
        {
            lock (_activeLock)
            {
                return _active is not null;
            }
        }
    }

    public string ActiveSessionId
    {
        get
        {
            lock (_activeLock)
            {
                return _active?.Manifest.SessionId ?? string.Empty;
            }
        }
    }

    public async Task<InstallMonitorStartResult> BeginAndLaunchAsync(
        string installerPath,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        ThrowIfDisposed();
        installerPath = Path.GetFullPath(Environment.ExpandEnvironmentVariables(installerPath.Trim()));
        ValidateInstaller(installerPath);

        lock (_activeLock)
        {
            if (_active is not null)
            {
                throw new InvalidOperationException("There is already an active monitored installation session.");
            }
        }

        string sessionId = $"{DateTime.UtcNow:yyyyMMdd-HHmmss}-{Guid.NewGuid():N}";
        string sessionDirectory = GetSessionDirectory(sessionId);
        Directory.CreateDirectory(sessionDirectory);

        var manifest = new InstallMonitorManifest
        {
            SessionId = sessionId,
            InstallerName = Path.GetFileName(installerPath),
            InstallerPath = installerPath,
            InstallerSha256 = await ComputeFileHashAsync(installerPath, cancellationToken),
            StartedAt = DateTimeOffset.UtcNow,
            Status = InstallMonitorStatus.Monitoring,
            MonitoredRoots = GetMonitoredRoots()
        };

        progress?.Report("التقاط لقطة النظام قبل التثبيت...");
        InstallSystemSnapshot before = await CaptureSystemSnapshotAsync(progress, cancellationToken);
        manifest.Warnings.AddRange(before.Warnings);
        await WriteJsonAtomicAsync(Path.Combine(sessionDirectory, BeforeSnapshotFileName), before, cancellationToken);
        await WriteJsonAtomicAsync(Path.Combine(sessionDirectory, ManifestFileName), manifest, cancellationToken);

        ActiveInstallSession active;
        try
        {
            active = new ActiveInstallSession(manifest, sessionDirectory, RecordFileSystemEvent);
            active.StartWatchers();
            lock (_activeLock)
            {
                _active = active;
            }

            progress?.Report("تشغيل ملف التثبيت بصلاحية المسؤول...");
            Process? process = Process.Start(CreateInstallerStartInfo(installerPath));
            if (process is null)
            {
                throw new InvalidOperationException("The installer process did not start.");
            }

            manifest.InstallerProcessId = process.Id;
            await WriteJsonAtomicAsync(Path.Combine(sessionDirectory, ManifestFileName), manifest, cancellationToken);
            AppLogger.Info($"Monitored install started: {sessionId} | {installerPath} | PID {process.Id}");

            return new InstallMonitorStartResult(ToSummary(manifest), process.Id, manifest.Warnings);
        }
        catch
        {
            lock (_activeLock)
            {
                _active?.Dispose();
                _active = null;
            }

            manifest.Status = InstallMonitorStatus.Failed;
            manifest.CompletedAt = DateTimeOffset.UtcNow;
            await WriteJsonAtomicAsync(Path.Combine(sessionDirectory, ManifestFileName), manifest, CancellationToken.None);
            throw;
        }
    }

    public async Task<InstallMonitorCompletionResult> CompleteActiveSessionAsync(
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        ThrowIfDisposed();
        ActiveInstallSession active = TakeActiveSession();
        active.StopWatchers();

        InstallMonitorManifest manifest = active.Manifest;
        string sessionDirectory = active.SessionDirectory;

        try
        {
            progress?.Report("التقاط لقطة النظام بعد التثبيت...");
            InstallSystemSnapshot after = await CaptureSystemSnapshotAsync(progress, cancellationToken);
            manifest.Warnings.AddRange(after.Warnings);
            await WriteJsonAtomicAsync(Path.Combine(sessionDirectory, AfterSnapshotFileName), after, cancellationToken);

            progress?.Report("مقارنة التغييرات وإنشاء سجل البرنامج...");
            InstallSystemSnapshot before = await ReadJsonAsync<InstallSystemSnapshot>(
                Path.Combine(sessionDirectory, BeforeSnapshotFileName), cancellationToken)
                ?? throw new InvalidOperationException("The pre-install snapshot is missing.");

            List<InstallChangeItem> changes = BuildChanges(active.GetFileEvents(), before, after, manifest.MonitoredRoots, manifest.Warnings);
            DetectInstalledApplication(manifest, before, after);
            manifest.Changes = changes;
            manifest.CompletedAt = DateTimeOffset.UtcNow;
            manifest.Status = InstallMonitorStatus.Completed;
            manifest.ReportPath = await CreateReportAsync(manifest, sessionDirectory, cancellationToken);
            await WriteJsonAtomicAsync(Path.Combine(sessionDirectory, ManifestFileName), manifest, cancellationToken);

            AppLogger.Info($"Monitored install completed: {manifest.SessionId} | {changes.Count} changes");
            return new InstallMonitorCompletionResult(ToSummary(manifest), changes, manifest.Warnings);
        }
        catch (OperationCanceledException)
        {
            manifest.Status = InstallMonitorStatus.Interrupted;
            manifest.CompletedAt = DateTimeOffset.UtcNow;
            await WriteJsonAtomicAsync(Path.Combine(sessionDirectory, ManifestFileName), manifest, CancellationToken.None);
            throw;
        }
        catch (Exception ex)
        {
            manifest.Status = InstallMonitorStatus.Failed;
            manifest.CompletedAt = DateTimeOffset.UtcNow;
            manifest.Warnings.Add(ex.Message);
            await WriteJsonAtomicAsync(Path.Combine(sessionDirectory, ManifestFileName), manifest, CancellationToken.None);
            throw;
        }
        finally
        {
            active.Dispose();
        }
    }

    public void CancelActiveSessionOnShutdown()
    {
        ThrowIfDisposed();
        ActiveInstallSession active = TakeActiveSession();
        try
        {
            active.StopWatchers();
            active.Manifest.Status = InstallMonitorStatus.Cancelled;
            active.Manifest.CompletedAt = DateTimeOffset.UtcNow;
            string manifestPath = Path.Combine(active.SessionDirectory, ManifestFileName);
            string tempPath = manifestPath + ".tmp";
            File.WriteAllText(tempPath, JsonSerializer.Serialize(active.Manifest, JsonOptions), new UTF8Encoding(false));
            File.Move(tempPath, manifestPath, overwrite: true);
            AppLogger.Info($"Monitored install cancelled during application shutdown: {active.Manifest.SessionId}");
        }
        finally
        {
            active.Dispose();
        }
    }

    public async Task CancelActiveSessionAsync(CancellationToken cancellationToken = default)
    {
        ThrowIfDisposed();
        ActiveInstallSession active = TakeActiveSession();
        try
        {
            active.StopWatchers();
            active.Manifest.Status = InstallMonitorStatus.Cancelled;
            active.Manifest.CompletedAt = DateTimeOffset.UtcNow;
            await WriteJsonAtomicAsync(
                Path.Combine(active.SessionDirectory, ManifestFileName),
                active.Manifest,
                cancellationToken);
            AppLogger.Info($"Monitored install cancelled: {active.Manifest.SessionId}");
        }
        finally
        {
            active.Dispose();
        }
    }

    public async Task<List<InstallMonitorSessionSummary>> GetSessionsAsync(
        CancellationToken cancellationToken = default)
    {
        ThrowIfDisposed();
        return await Task.Run(() =>
        {
            Directory.CreateDirectory(MonitorRoot);
            var sessions = new List<InstallMonitorSessionSummary>();
            foreach (string directory in Directory.EnumerateDirectories(MonitorRoot, "*", SearchOption.TopDirectoryOnly))
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    if (IsReparsePoint(directory))
                    {
                        AppLogger.Error($"Ignored reparse-point install-monitor session directory: {directory}");
                        continue;
                    }
                    InstallMonitorManifest? manifest = ReadJson<InstallMonitorManifest>(Path.Combine(directory, ManifestFileName));
                    if (manifest is null || !string.Equals(manifest.SessionId, Path.GetFileName(directory), StringComparison.OrdinalIgnoreCase))
                    {
                        continue;
                    }

                    if (manifest.Status == InstallMonitorStatus.Monitoring
                        && !string.Equals(manifest.SessionId, ActiveSessionId, StringComparison.OrdinalIgnoreCase))
                    {
                        manifest.Status = InstallMonitorStatus.Interrupted;
                        manifest.CompletedAt ??= DateTimeOffset.UtcNow;
                        string manifestPath = Path.Combine(directory, ManifestFileName);
                        string tempPath = manifestPath + ".tmp";
                        File.WriteAllText(tempPath, JsonSerializer.Serialize(manifest, JsonOptions), new UTF8Encoding(false));
                        File.Move(tempPath, manifestPath, overwrite: true);
                    }

                    sessions.Add(ToSummary(manifest));
                }
                catch (Exception ex)
                {
                    AppLogger.Error($"Could not read install-monitor session: {directory}", ex);
                }
            }

            return sessions
                .OrderByDescending(session => session.StartedAt)
                .ToList();
        }, cancellationToken);
    }

    public async Task<List<InstallChangeItem>> GetChangesAsync(
        string sessionId,
        CancellationToken cancellationToken = default)
    {
        ThrowIfDisposed();
        InstallMonitorManifest manifest = await LoadManifestAsync(sessionId, cancellationToken);
        HashSet<string> currentApplicationNames = (await _installedAppsService.GetInstalledAppsAsync(cancellationToken))
            .Select(app => app.DisplayName)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        foreach (InstallChangeItem change in manifest.Changes)
        {
            change.ExistsNow = CheckExistsNow(change, currentApplicationNames);
            change.IsSelected = false;
        }

        return manifest.Changes
            .OrderBy(change => change.Category)
            .ThenBy(change => change.Kind)
            .ThenBy(change => change.Location, StringComparer.CurrentCultureIgnoreCase)
            .ToList();
    }

    public async Task<InstallMonitorManifest> GetManifestAsync(
        string sessionId,
        CancellationToken cancellationToken = default)
        => await LoadManifestAsync(sessionId, cancellationToken);

    public async Task<MonitoredResidualAnalysisResult> AnalyzeResidualsAsync(
        string sessionId,
        CancellationToken cancellationToken = default)
    {
        InstallMonitorManifest manifest = await LoadManifestAsync(sessionId, cancellationToken);
        HashSet<string> currentApplicationNames = (await _installedAppsService.GetInstalledAppsAsync(cancellationToken))
            .Select(app => app.DisplayName)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var changes = new List<InstallChangeItem>(manifest.Changes.Count);
        int files = 0;
        int services = 0;
        int tasks = 0;
        int registry = 0;

        foreach (InstallChangeItem original in manifest.Changes)
        {
            cancellationToken.ThrowIfCancellationRequested();
            bool exists = CheckExistsNow(original, currentApplicationNames);
            var copy = CloneChange(original, exists);
            changes.Add(copy);
            if (!exists || original.Kind != InstallChangeKind.Added)
            {
                continue;
            }

            switch (original.Category)
            {
                case InstallChangeCategory.FileSystem:
                    files++;
                    break;
                case InstallChangeCategory.Service:
                    services++;
                    break;
                case InstallChangeCategory.ScheduledTask:
                    tasks++;
                    break;
                case InstallChangeCategory.Registry:
                    registry++;
                    break;
            }
        }

        return new MonitoredResidualAnalysisResult(files, services, tasks, registry, changes);
    }

    public async Task DeleteSessionAsync(string sessionId, CancellationToken cancellationToken = default)
    {
        ThrowIfDisposed();
        if (string.Equals(sessionId, ActiveSessionId, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("The active monitoring session cannot be deleted.");
        }

        string directory = GetSessionDirectory(sessionId);
        await Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (Directory.Exists(directory))
            {
                Directory.Delete(directory, recursive: true);
            }
        }, cancellationToken);
    }

    public static ProcessStartInfo CreateUninstallStartInfo(string commandLine)
    {
        string command = Environment.ExpandEnvironmentVariables(commandLine.Trim());
        if (string.IsNullOrWhiteSpace(command))
        {
            throw new InvalidOperationException("The uninstall command is empty.");
        }

        string fileName;
        string arguments;
        if (command.StartsWith('"'))
        {
            int closingQuote = command.IndexOf('"', 1);
            if (closingQuote <= 1)
            {
                throw new InvalidOperationException("The uninstall command contains invalid quotes.");
            }

            fileName = command[1..closingQuote];
            arguments = command[(closingQuote + 1)..].TrimStart();
        }
        else
        {
            int executableEnd = command.IndexOf(".exe", StringComparison.OrdinalIgnoreCase);
            if (executableEnd >= 0)
            {
                executableEnd += 4;
                fileName = command[..executableEnd].Trim();
                arguments = command[executableEnd..].TrimStart();
            }
            else
            {
                int firstSpace = command.IndexOf(' ');
                fileName = firstSpace < 0 ? command : command[..firstSpace];
                arguments = firstSpace < 0 ? string.Empty : command[(firstSpace + 1)..].TrimStart();
            }
        }

        if (Path.GetFileName(fileName).Equals("msiexec.exe", StringComparison.OrdinalIgnoreCase)
            || Path.GetFileName(fileName).Equals("msiexec", StringComparison.OrdinalIgnoreCase))
        {
            arguments = NormalizeMsiUninstallArguments(arguments);
        }

        return new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            UseShellExecute = true,
            Verb = "runas"
        };
    }

    public static bool IsSafeMonitoredApplicationDirectory(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || !Directory.Exists(path))
        {
            return false;
        }

        string full = Path.TrimEndingDirectorySeparator(Path.GetFullPath(path));
        string[] roots =
        [
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)
        ];

        bool directChild = roots
            .Where(root => !string.IsNullOrWhiteSpace(root))
            .Select(root => Path.TrimEndingDirectorySeparator(Path.GetFullPath(root)))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Any(root => string.Equals(Path.GetDirectoryName(full), root, StringComparison.OrdinalIgnoreCase));
        if (!directChild)
        {
            return false;
        }

        string name = Path.GetFileName(full);
        return !string.IsNullOrWhiteSpace(name)
               && !ProtectedApplicationDirectoryNames.Contains(name)
               && !IsReparsePoint(full);
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        lock (_activeLock)
        {
            _active?.Dispose();
            _active = null;
        }

        _disposed = true;
        GC.SuppressFinalize(this);
    }

    private static readonly HashSet<string> ProtectedApplicationDirectoryNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "Microsoft", "Windows", "Packages", "Programs", "Common Files", "Temp",
        "System32", "WindowsApps", "ModifiableWindowsApps", "Users", "ProgramData"
    };

    private ActiveInstallSession TakeActiveSession()
    {
        lock (_activeLock)
        {
            ActiveInstallSession active = _active
                ?? throw new InvalidOperationException("There is no active monitored installation session.");
            _active = null;
            return active;
        }
    }

    private void RecordFileSystemEvent(ActiveInstallSession active, string eventType, string path, string? oldPath)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return;
            }

            string fullPath = Path.GetFullPath(path);
            if (PathSafetyService.IsPathUnder(fullPath, SettingsService.DataDirectory)
                || IsNoisePath(fullPath))
            {
                return;
            }

            if (!active.FileEvents.ContainsKey(fullPath) && active.FileEvents.Count >= MaximumDistinctFileEvents)
            {
                lock (active.Manifest.Warnings)
                {
                    const string warning = "وصلت مراقبة الملفات إلى الحد الأقصى لعدد المسارات، وقد تكون بعض التغييرات اللاحقة غير مسجلة.";
                    if (!active.Manifest.Warnings.Contains(warning, StringComparer.Ordinal))
                    {
                        active.Manifest.Warnings.Add(warning);
                    }
                }
                return;
            }

            DateTimeOffset now = DateTimeOffset.UtcNow;
            active.FileEvents.AddOrUpdate(
                fullPath,
                _ => new InstallFileEventRecord
                {
                    Path = fullPath,
                    OldPath = oldPath is null ? string.Empty : Path.GetFullPath(oldPath),
                    EventTypes = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { eventType },
                    FirstSeenUtc = now,
                    LastSeenUtc = now
                },
                (_, existing) =>
                {
                    lock (existing)
                    {
                        existing.EventTypes.Add(eventType);
                        if (!string.IsNullOrWhiteSpace(oldPath))
                        {
                            existing.OldPath = Path.GetFullPath(oldPath);
                        }
                        existing.LastSeenUtc = now;
                        return existing;
                    }
                });

            active.AppendJournal(new
            {
                timestampUtc = now,
                type = eventType,
                path = fullPath,
                oldPath
            });
        }
        catch (Exception ex)
        {
            AppLogger.Error("Could not record install-monitor file event.", ex);
        }
    }

    private async Task<InstallSystemSnapshot> CaptureSystemSnapshotAsync(
        IProgress<string>? progress,
        CancellationToken cancellationToken)
    {
        return await Task.Run(async () =>
        {
            var snapshot = new InstallSystemSnapshot { CapturedAt = DateTimeOffset.UtcNow };

            progress?.Report("قراءة مناطق الريجستري المدعومة...");
            CaptureRegistry(snapshot, cancellationToken);

            progress?.Report("قراءة الخدمات...");
            CaptureServices(snapshot, cancellationToken);

            progress?.Report("قراءة المهام المجدولة...");
            CaptureScheduledTasks(snapshot, cancellationToken);

            progress?.Report("قراءة قائمة البرامج المثبتة...");
            List<InstalledApp> apps = await _installedAppsService.GetInstalledAppsAsync(cancellationToken);
            foreach (InstalledApp app in apps)
            {
                string id = BuildInstalledAppId(app.DisplayName, app.Publisher, app.Version);
                snapshot.InstalledApplications[id] = new InstalledAppSnapshotEntry
                {
                    Id = id,
                    DisplayName = app.DisplayName,
                    Publisher = app.Publisher,
                    Version = app.Version,
                    InstallLocation = app.InstallLocation,
                    UninstallString = app.UninstallString,
                    EstimatedSizeBytes = app.EstimatedSizeBytes,
                    Fingerprint = ComputeTextHash($"{app.DisplayName}|{app.Publisher}|{app.Version}|{app.InstallLocation}|{app.UninstallString}|{app.EstimatedSizeBytes}")
                };
            }

            return snapshot;
        }, cancellationToken);
    }

    private static void CaptureRegistry(InstallSystemSnapshot snapshot, CancellationToken cancellationToken)
    {
        RegistryCaptureRoot[] roots =
        [
            new(RegistryHive.CurrentUser, RegistryView.Default, @"Software\Microsoft\Windows\CurrentVersion\Run", 1),
            new(RegistryHive.CurrentUser, RegistryView.Default, @"Software\Microsoft\Windows\CurrentVersion\RunOnce", 1),
            new(RegistryHive.LocalMachine, RegistryView.Registry64, @"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", 1),
            new(RegistryHive.LocalMachine, RegistryView.Registry32, @"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", 1),
            new(RegistryHive.LocalMachine, RegistryView.Registry64, @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 2),
            new(RegistryHive.LocalMachine, RegistryView.Registry32, @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 2),
            new(RegistryHive.CurrentUser, RegistryView.Default, @"Software\Microsoft\Windows\CurrentVersion\Uninstall", 2),
            new(RegistryHive.CurrentUser, RegistryView.Default, @"Software", 2),
            new(RegistryHive.LocalMachine, RegistryView.Registry64, @"SOFTWARE", 2),
            new(RegistryHive.LocalMachine, RegistryView.Registry32, @"SOFTWARE", 2)
        ];

        foreach (RegistryCaptureRoot root in roots)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (snapshot.Registry.Count >= MaximumRegistryEntries)
            {
                snapshot.Warnings.Add($"توقفت لقطة الريجستري عند {MaximumRegistryEntries:N0} عنصر لتجنب استهلاك الذاكرة.");
                break;
            }

            try
            {
                using RegistryKey baseKey = RegistryKey.OpenBaseKey(root.Hive, root.View);
                using RegistryKey? key = baseKey.OpenSubKey(root.Path, writable: false);
                if (key is null)
                {
                    continue;
                }

                CaptureRegistryKey(snapshot.Registry, root, key, root.Path, 0, cancellationToken);
            }
            catch (Exception ex)
            {
                snapshot.Warnings.Add($"تعذر قراءة {root.Hive}\\{root.Path}: {ex.Message}");
            }
        }
    }

    private static void CaptureRegistryKey(
        IDictionary<string, RegistrySnapshotEntry> destination,
        RegistryCaptureRoot root,
        RegistryKey key,
        string keyPath,
        int depth,
        CancellationToken cancellationToken)
    {
        if (destination.Count >= MaximumRegistryEntries)
        {
            return;
        }

        cancellationToken.ThrowIfCancellationRequested();
        string keyId = BuildRegistryEntryId(root.Hive, root.View, keyPath, "$KEY");
        destination.TryAdd(keyId, new RegistrySnapshotEntry
        {
            Id = keyId,
            Hive = root.Hive.ToString(),
            View = root.View.ToString(),
            KeyPath = keyPath,
            ValueName = "$KEY",
            ValueKind = "Key",
            ValueHash = ComputeTextHash(keyPath)
        });

        string[] valueNames;
        try
        {
            valueNames = key.GetValueNames();
        }
        catch
        {
            valueNames = [];
        }

        foreach (string valueName in valueNames)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (destination.Count >= MaximumRegistryEntries)
            {
                return;
            }

            try
            {
                RegistryValueKind kind = key.GetValueKind(valueName);
                object? value = key.GetValue(valueName, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
                string id = BuildRegistryEntryId(root.Hive, root.View, keyPath, valueName);
                destination[id] = new RegistrySnapshotEntry
                {
                    Id = id,
                    Hive = root.Hive.ToString(),
                    View = root.View.ToString(),
                    KeyPath = keyPath,
                    ValueName = valueName,
                    ValueKind = kind.ToString(),
                    ValueHash = ComputeRegistryValueHash(kind, value)
                };
            }
            catch
            {
                // Individual inaccessible values are intentionally skipped.
            }
        }

        if (depth >= root.MaximumDepth)
        {
            return;
        }

        string[] subKeyNames;
        try
        {
            subKeyNames = key.GetSubKeyNames();
        }
        catch
        {
            return;
        }

        foreach (string subKeyName in subKeyNames)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (destination.Count >= MaximumRegistryEntries)
            {
                return;
            }

            try
            {
                using RegistryKey? child = key.OpenSubKey(subKeyName, writable: false);
                if (child is not null)
                {
                    CaptureRegistryKey(destination, root, child, $"{keyPath}\\{subKeyName}", depth + 1, cancellationToken);
                }
            }
            catch
            {
                // Individual inaccessible keys are intentionally skipped.
            }
        }
    }

    private static void CaptureServices(InstallSystemSnapshot snapshot, CancellationToken cancellationToken)
    {
        try
        {
            using RegistryKey baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64);
            using RegistryKey? services = baseKey.OpenSubKey(@"SYSTEM\CurrentControlSet\Services", writable: false);
            if (services is null)
            {
                return;
            }

            foreach (string serviceName in services.GetSubKeyNames())
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    using RegistryKey? key = services.OpenSubKey(serviceName, writable: false);
                    if (key is null)
                    {
                        continue;
                    }

                    string displayName = key.GetValue("DisplayName")?.ToString() ?? serviceName;
                    string imagePath = key.GetValue("ImagePath", string.Empty, RegistryValueOptions.DoNotExpandEnvironmentNames)?.ToString() ?? string.Empty;
                    int start = ConvertRegistryInt(key.GetValue("Start"));
                    int type = ConvertRegistryInt(key.GetValue("Type"));
                    snapshot.Services[serviceName] = new ServiceSnapshotEntry
                    {
                        Name = serviceName,
                        DisplayName = displayName,
                        ImagePath = imagePath,
                        StartMode = start,
                        ServiceType = type,
                        Fingerprint = ComputeTextHash($"{displayName}|{imagePath}|{start}|{type}")
                    };
                }
                catch
                {
                    // Individual inaccessible services are intentionally skipped.
                }
            }
        }
        catch (Exception ex)
        {
            snapshot.Warnings.Add($"تعذر قراءة الخدمات: {ex.Message}");
        }
    }

    private static void CaptureScheduledTasks(InstallSystemSnapshot snapshot, CancellationToken cancellationToken)
    {
        string windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        string tasksRoot = Path.Combine(windows, "System32", "Tasks");
        if (!Directory.Exists(tasksRoot))
        {
            return;
        }

        try
        {
            foreach (string file in EnumerateFilesSafe(tasksRoot, cancellationToken))
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    var info = new FileInfo(file);
                    string relative = Path.GetRelativePath(tasksRoot, file);
                    snapshot.ScheduledTasks[relative] = new TaskSnapshotEntry
                    {
                        RelativePath = relative,
                        Length = info.Length,
                        LastWriteTimeUtc = info.LastWriteTimeUtc,
                        Fingerprint = ComputeTextHash($"{info.Length}|{info.LastWriteTimeUtc.Ticks}")
                    };
                }
                catch
                {
                    // Individual inaccessible task files are intentionally skipped.
                }
            }
        }
        catch (Exception ex)
        {
            snapshot.Warnings.Add($"تعذر قراءة بعض المهام المجدولة: {ex.Message}");
        }
    }

    private static List<InstallChangeItem> BuildChanges(
        IReadOnlyCollection<InstallFileEventRecord> fileEvents,
        InstallSystemSnapshot before,
        InstallSystemSnapshot after,
        IReadOnlyCollection<string> monitoredRoots,
        IList<string> warnings)
    {
        List<InstallChangeItem> fileChanges = BuildFileChanges(fileEvents, monitoredRoots).ToList();
        if (fileChanges.Count > MaximumFileChangeItems)
        {
            warnings.Add($"عُرض أول {MaximumFileChangeItems:N0} تغيير ملفات فقط من أصل {fileChanges.Count:N0} لتجنب تجميد الواجهة.");
            fileChanges = fileChanges.Take(MaximumFileChangeItems).ToList();
        }

        List<InstallChangeItem> registryChanges = BuildRegistryChanges(before.Registry, after.Registry).ToList();
        if (registryChanges.Count > MaximumRegistryChangeItems)
        {
            warnings.Add($"عُرض أول {MaximumRegistryChangeItems:N0} تغيير ريجستري فقط من أصل {registryChanges.Count:N0} لتجنب استهلاك الذاكرة.");
            registryChanges = registryChanges.Take(MaximumRegistryChangeItems).ToList();
        }

        var changes = new List<InstallChangeItem>(
            fileChanges.Count + registryChanges.Count + before.Services.Count + before.ScheduledTasks.Count + 100);
        changes.AddRange(fileChanges);
        changes.AddRange(registryChanges);
        changes.AddRange(BuildServiceChanges(before.Services, after.Services));
        changes.AddRange(BuildTaskChanges(before.ScheduledTasks, after.ScheduledTasks));
        changes.AddRange(BuildInstalledAppChanges(before.InstalledApplications, after.InstalledApplications));
        return changes
            .GroupBy(change => $"{change.Category}|{change.Kind}|{change.Location}", StringComparer.OrdinalIgnoreCase)
            .Select(group => group.First())
            .OrderBy(change => change.Category)
            .ThenBy(change => change.Kind)
            .ThenBy(change => change.Location, StringComparer.CurrentCultureIgnoreCase)
            .ToList();
    }

    private static IEnumerable<InstallChangeItem> BuildFileChanges(
        IReadOnlyCollection<InstallFileEventRecord> fileEvents,
        IReadOnlyCollection<string> monitoredRoots)
    {
        List<InstallFileEventRecord> records = fileEvents
            .Where(record => monitoredRoots.Any(root => PathSafetyService.IsPathUnder(record.Path, root)))
            .OrderBy(record => record.Path.Count(character => character is '\\' or '/'))
            .ThenBy(record => record.Path, StringComparer.OrdinalIgnoreCase)
            .ToList();

        var createdDirectories = records
            .Where(record => record.EventTypes.Contains("Created") && Directory.Exists(record.Path))
            .Select(record => Path.TrimEndingDirectorySeparator(Path.GetFullPath(record.Path)))
            .Where(IsSafeMonitoredApplicationDirectory)
            .ToList();

        var emittedDirectoryRoots = new List<string>();
        foreach (string directory in createdDirectories)
        {
            if (emittedDirectoryRoots.Any(root => PathSafetyService.IsPathUnder(directory, root)))
            {
                continue;
            }

            emittedDirectoryRoots.Add(directory);
            yield return new InstallChangeItem
            {
                Category = InstallChangeCategory.FileSystem,
                Kind = InstallChangeKind.Added,
                Name = Path.GetFileName(directory),
                Location = directory,
                Details = "مجلد تطبيق جديد على مستوى جذر معتمد. يمكن نقله إلى الحجر بعد إزالة البرنامج ومراجعة محتواه.",
                Confidence = "عالية",
                SizeBytes = CalculateDirectorySize(directory),
                IsDirectory = true,
                IsSafeToQuarantine = true,
                ExistsNow = true
            };
        }

        foreach (InstallFileEventRecord record in records)
        {
            if (emittedDirectoryRoots.Any(root => PathSafetyService.IsPathUnder(record.Path, root)))
            {
                continue;
            }

            bool existsFile = File.Exists(record.Path);
            bool existsDirectory = Directory.Exists(record.Path);
            bool exists = existsFile || existsDirectory;
            InstallChangeKind kind = ResolveFileChangeKind(record, exists);
            if (kind == InstallChangeKind.Information && !exists)
            {
                continue;
            }

            string eventList = string.Join("، ", record.EventTypes.OrderBy(value => value));
            long size = existsFile ? SafeFileLength(record.Path) : 0;
            yield return new InstallChangeItem
            {
                Category = InstallChangeCategory.FileSystem,
                Kind = kind,
                Name = Path.GetFileName(record.Path),
                Location = record.Path,
                Details = string.IsNullOrWhiteSpace(record.OldPath)
                    ? $"أحداث المراقبة: {eventList}."
                    : $"أحداث المراقبة: {eventList}. المسار السابق: {record.OldPath}",
                Confidence = kind == InstallChangeKind.Added ? "متوسطة" : "منخفضة",
                SizeBytes = size,
                IsDirectory = existsDirectory,
                IsSafeToQuarantine = false,
                ExistsNow = exists
            };
        }
    }

    private static IEnumerable<InstallChangeItem> BuildRegistryChanges(
        IReadOnlyDictionary<string, RegistrySnapshotEntry> before,
        IReadOnlyDictionary<string, RegistrySnapshotEntry> after)
    {
        foreach ((string id, RegistrySnapshotEntry current) in after)
        {
            if (!before.TryGetValue(id, out RegistrySnapshotEntry? previous))
            {
                yield return RegistryChange(current, InstallChangeKind.Added, "مفتاح أو قيمة جديدة. لا تُحذف تلقائيًا.");
            }
            else if (!string.Equals(previous.ValueHash, current.ValueHash, StringComparison.Ordinal))
            {
                yield return RegistryChange(current, InstallChangeKind.Modified, "تغيرت قيمة الريجستري. لا تُحذف أو تُستعاد تلقائيًا.");
            }
        }

        foreach ((string id, RegistrySnapshotEntry previous) in before)
        {
            if (!after.ContainsKey(id))
            {
                yield return RegistryChange(previous, InstallChangeKind.Removed, "أزيل مفتاح أو قيمة أثناء جلسة التثبيت.");
            }
        }
    }

    private static InstallChangeItem RegistryChange(RegistrySnapshotEntry entry, InstallChangeKind kind, string details)
    {
        string name = entry.ValueName == "$KEY" ? Path.GetFileName(entry.KeyPath) : entry.ValueName;
        string location = $"{entry.Hive} ({entry.View})\\{entry.KeyPath}"
                          + (entry.ValueName == "$KEY" ? string.Empty : $" — {entry.ValueName}");
        return new InstallChangeItem
        {
            Category = InstallChangeCategory.Registry,
            Kind = kind,
            Name = string.IsNullOrWhiteSpace(name) ? "(افتراضي)" : name,
            Location = location,
            Details = $"{details} النوع: {entry.ValueKind}.",
            Confidence = "متوسطة",
            IsSafeToQuarantine = false,
            ExistsNow = kind != InstallChangeKind.Removed
        };
    }

    private static IEnumerable<InstallChangeItem> BuildServiceChanges(
        IReadOnlyDictionary<string, ServiceSnapshotEntry> before,
        IReadOnlyDictionary<string, ServiceSnapshotEntry> after)
    {
        foreach ((string id, ServiceSnapshotEntry current) in after)
        {
            if (!before.TryGetValue(id, out ServiceSnapshotEntry? previous))
            {
                yield return new InstallChangeItem
                {
                    Category = InstallChangeCategory.Service,
                    Kind = InstallChangeKind.Added,
                    Name = current.DisplayName,
                    Location = current.Name,
                    Details = $"خدمة جديدة. مسار التشغيل: {current.ImagePath}",
                    Confidence = "عالية",
                    ExistsNow = true
                };
            }
            else if (!string.Equals(previous.Fingerprint, current.Fingerprint, StringComparison.Ordinal))
            {
                yield return new InstallChangeItem
                {
                    Category = InstallChangeCategory.Service,
                    Kind = InstallChangeKind.Modified,
                    Name = current.DisplayName,
                    Location = current.Name,
                    Details = "تغيرت خصائص الخدمة أثناء التثبيت.",
                    Confidence = "متوسطة",
                    ExistsNow = true
                };
            }
        }

        foreach ((string id, ServiceSnapshotEntry previous) in before)
        {
            if (!after.ContainsKey(id))
            {
                yield return new InstallChangeItem
                {
                    Category = InstallChangeCategory.Service,
                    Kind = InstallChangeKind.Removed,
                    Name = previous.DisplayName,
                    Location = previous.Name,
                    Details = "أزيلت الخدمة أثناء جلسة التثبيت.",
                    Confidence = "منخفضة",
                    ExistsNow = false
                };
            }
        }
    }

    private static IEnumerable<InstallChangeItem> BuildTaskChanges(
        IReadOnlyDictionary<string, TaskSnapshotEntry> before,
        IReadOnlyDictionary<string, TaskSnapshotEntry> after)
    {
        foreach ((string id, TaskSnapshotEntry current) in after)
        {
            if (!before.TryGetValue(id, out TaskSnapshotEntry? previous))
            {
                yield return new InstallChangeItem
                {
                    Category = InstallChangeCategory.ScheduledTask,
                    Kind = InstallChangeKind.Added,
                    Name = Path.GetFileName(current.RelativePath),
                    Location = current.RelativePath,
                    Details = "مهمة مجدولة جديدة. تُعرض للمراجعة فقط.",
                    Confidence = "عالية",
                    ExistsNow = true
                };
            }
            else if (!string.Equals(previous.Fingerprint, current.Fingerprint, StringComparison.Ordinal))
            {
                yield return new InstallChangeItem
                {
                    Category = InstallChangeCategory.ScheduledTask,
                    Kind = InstallChangeKind.Modified,
                    Name = Path.GetFileName(current.RelativePath),
                    Location = current.RelativePath,
                    Details = "تغير ملف المهمة المجدولة أثناء التثبيت.",
                    Confidence = "متوسطة",
                    ExistsNow = true
                };
            }
        }

        foreach ((string id, TaskSnapshotEntry previous) in before)
        {
            if (!after.ContainsKey(id))
            {
                yield return new InstallChangeItem
                {
                    Category = InstallChangeCategory.ScheduledTask,
                    Kind = InstallChangeKind.Removed,
                    Name = Path.GetFileName(previous.RelativePath),
                    Location = previous.RelativePath,
                    Details = "أزيلت مهمة مجدولة أثناء جلسة التثبيت.",
                    Confidence = "منخفضة",
                    ExistsNow = false
                };
            }
        }
    }

    private static IEnumerable<InstallChangeItem> BuildInstalledAppChanges(
        IReadOnlyDictionary<string, InstalledAppSnapshotEntry> before,
        IReadOnlyDictionary<string, InstalledAppSnapshotEntry> after)
    {
        foreach ((string id, InstalledAppSnapshotEntry current) in after)
        {
            if (!before.TryGetValue(id, out InstalledAppSnapshotEntry? previous))
            {
                yield return new InstallChangeItem
                {
                    Category = InstallChangeCategory.InstalledApplication,
                    Kind = InstallChangeKind.Added,
                    Name = current.DisplayName,
                    Location = string.IsNullOrWhiteSpace(current.InstallLocation) ? current.Publisher : current.InstallLocation,
                    Details = $"برنامج جديد ظهر في قائمة الإزالة. الإصدار: {current.Version}",
                    Confidence = "عالية",
                    SizeBytes = current.EstimatedSizeBytes,
                    ExistsNow = true
                };
            }
            else if (!string.Equals(previous.Fingerprint, current.Fingerprint, StringComparison.Ordinal))
            {
                yield return new InstallChangeItem
                {
                    Category = InstallChangeCategory.InstalledApplication,
                    Kind = InstallChangeKind.Modified,
                    Name = current.DisplayName,
                    Location = string.IsNullOrWhiteSpace(current.InstallLocation) ? current.Publisher : current.InstallLocation,
                    Details = $"تغير سجل البرنامج المثبت. الإصدار الحالي: {current.Version}",
                    Confidence = "متوسطة",
                    SizeBytes = current.EstimatedSizeBytes,
                    ExistsNow = true
                };
            }
        }
    }

    private static void DetectInstalledApplication(
        InstallMonitorManifest manifest,
        InstallSystemSnapshot before,
        InstallSystemSnapshot after)
    {
        List<InstalledAppSnapshotEntry> additions = after.InstalledApplications
            .Where(pair => !before.InstalledApplications.ContainsKey(pair.Key))
            .Select(pair => pair.Value)
            .OrderByDescending(app => ScoreDetectedApplication(app, manifest.InstallerName))
            .ThenByDescending(app => app.EstimatedSizeBytes)
            .ToList();

        InstalledAppSnapshotEntry? detected = additions.Count == 1
            ? additions[0]
            : additions.FirstOrDefault(app => ScoreDetectedApplication(app, manifest.InstallerName) > 0);
        if (detected is null)
        {
            List<InstalledAppSnapshotEntry> modified = after.InstalledApplications
                .Where(pair => before.InstalledApplications.TryGetValue(pair.Key, out InstalledAppSnapshotEntry? previous)
                               && !string.Equals(previous.Fingerprint, pair.Value.Fingerprint, StringComparison.Ordinal))
                .Select(pair => pair.Value)
                .OrderByDescending(app => ScoreDetectedApplication(app, manifest.InstallerName))
                .ThenByDescending(app => app.EstimatedSizeBytes)
                .ToList();
            detected = modified.Count == 1
                ? modified[0]
                : modified.FirstOrDefault(app => ScoreDetectedApplication(app, manifest.InstallerName) > 0);
        }

        if (detected is null)
        {
            return;
        }

        manifest.DetectedApplicationName = detected.DisplayName;
        manifest.DetectedPublisher = detected.Publisher;
        manifest.DetectedVersion = detected.Version;
        manifest.DetectedInstallLocation = detected.InstallLocation;
        manifest.DetectedUninstallString = detected.UninstallString;
    }

    private static int ScoreDetectedApplication(InstalledAppSnapshotEntry app, string installerName)
    {
        string installerToken = NormalizeToken(Path.GetFileNameWithoutExtension(installerName));
        string appToken = NormalizeToken(app.DisplayName);
        if (string.IsNullOrWhiteSpace(installerToken) || string.IsNullOrWhiteSpace(appToken))
        {
            return 0;
        }

        if (appToken.Contains(installerToken, StringComparison.OrdinalIgnoreCase)
            || installerToken.Contains(appToken, StringComparison.OrdinalIgnoreCase))
        {
            return 100;
        }

        string[] installerParts = installerToken.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return installerParts.Count(part => part.Length >= 3 && appToken.Contains(part, StringComparison.OrdinalIgnoreCase)) * 10;
    }

    private static bool CheckExistsNow(InstallChangeItem change, ISet<string>? currentApplicationNames = null)
    {
        try
        {
            return change.Category switch
            {
                InstallChangeCategory.FileSystem => File.Exists(change.Location) || Directory.Exists(change.Location),
                InstallChangeCategory.Service => ServiceExists(change.Location),
                InstallChangeCategory.ScheduledTask => TaskExists(change.Location),
                InstallChangeCategory.Registry => RegistryEntryExists(change.Location),
                InstallChangeCategory.InstalledApplication => currentApplicationNames?.Contains(change.Name) ?? true,
                _ => false
            };
        }
        catch
        {
            return false;
        }
    }

    private static bool ServiceExists(string serviceName)
    {
        using RegistryKey baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64);
        using RegistryKey? key = baseKey.OpenSubKey($@"SYSTEM\CurrentControlSet\Services\{serviceName}");
        return key is not null;
    }

    private static bool TaskExists(string relativePath)
    {
        string windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        return File.Exists(Path.Combine(windows, "System32", "Tasks", relativePath));
    }

    private static bool RegistryEntryExists(string displayLocation)
    {
        // The display location intentionally omits raw values. A conservative parser checks key existence only.
        int separator = displayLocation.IndexOf("\\", StringComparison.Ordinal);
        if (separator <= 0)
        {
            return false;
        }

        string prefix = displayLocation[..separator];
        string keyAndValue = displayLocation[(separator + 1)..];
        int valueSeparator = keyAndValue.LastIndexOf(" — ", StringComparison.Ordinal);
        string keyPath = valueSeparator >= 0 ? keyAndValue[..valueSeparator] : keyAndValue;
        string valueName = valueSeparator >= 0 ? keyAndValue[(valueSeparator + 3)..] : "$KEY";

        RegistryHive hive = prefix.StartsWith(nameof(RegistryHive.CurrentUser), StringComparison.Ordinal)
            ? RegistryHive.CurrentUser
            : RegistryHive.LocalMachine;
        RegistryView view = prefix.Contains(nameof(RegistryView.Registry32), StringComparison.Ordinal)
            ? RegistryView.Registry32
            : prefix.Contains(nameof(RegistryView.Registry64), StringComparison.Ordinal)
                ? RegistryView.Registry64
                : RegistryView.Default;

        using RegistryKey baseKey = RegistryKey.OpenBaseKey(hive, view);
        using RegistryKey? key = baseKey.OpenSubKey(keyPath, writable: false);
        if (key is null)
        {
            return false;
        }

        return valueName == "$KEY" || key.GetValueNames().Contains(valueName, StringComparer.OrdinalIgnoreCase);
    }

    private static InstallChangeItem CloneChange(InstallChangeItem source, bool existsNow)
        => new()
        {
            Id = source.Id,
            Category = source.Category,
            Kind = source.Kind,
            Name = source.Name,
            Location = source.Location,
            Details = source.Details,
            Confidence = source.Confidence,
            SizeBytes = source.SizeBytes,
            IsDirectory = source.IsDirectory,
            IsSafeToQuarantine = source.IsSafeToQuarantine,
            ExistsNow = existsNow
        };

    private static ProcessStartInfo CreateInstallerStartInfo(string installerPath)
    {
        string extension = Path.GetExtension(installerPath);
        if (extension.Equals(".msi", StringComparison.OrdinalIgnoreCase))
        {
            return new ProcessStartInfo
            {
                FileName = "msiexec.exe",
                Arguments = $"/i \"{installerPath}\"",
                UseShellExecute = true,
                Verb = "runas"
            };
        }

        return new ProcessStartInfo
        {
            FileName = installerPath,
            UseShellExecute = true,
            Verb = "runas",
            WorkingDirectory = Path.GetDirectoryName(installerPath) ?? Environment.CurrentDirectory
        };
    }

    private static string NormalizeMsiUninstallArguments(string arguments)
    {
        string normalized = arguments.Trim();
        if (normalized.StartsWith("/I", StringComparison.OrdinalIgnoreCase))
        {
            normalized = "/X" + normalized[2..];
        }
        return normalized;
    }

    private static void ValidateInstaller(string installerPath)
    {
        if (!File.Exists(installerPath))
        {
            throw new FileNotFoundException("Installer file was not found.", installerPath);
        }

        string extension = Path.GetExtension(installerPath);
        if (!extension.Equals(".exe", StringComparison.OrdinalIgnoreCase)
            && !extension.Equals(".msi", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Only EXE and MSI installer files are supported.");
        }

        FileAttributes attributes = File.GetAttributes(installerPath);
        if (attributes.HasFlag(FileAttributes.ReparsePoint))
        {
            throw new InvalidOperationException("Installer symbolic links are not supported.");
        }
    }

    private static List<string> GetMonitoredRoots()
    {
        string[] candidates =
        [
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.Programs),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonPrograms),
            Environment.GetFolderPath(Environment.SpecialFolder.Startup),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonStartup),
            Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonDesktopDirectory)
        ];

        return candidates
            .Where(path => !string.IsNullOrWhiteSpace(path) && Directory.Exists(path))
            .Select(path => Path.TrimEndingDirectorySeparator(Path.GetFullPath(path)))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(path => path.Length)
            .ToList();
    }

    private static bool IsNoisePath(string path)
    {
        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string roaming = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        string[] noiseRoots =
        [
            Path.Combine(local, "Temp"),
            Path.Combine(local, "Microsoft", "Windows", "INetCache"),
            Path.Combine(local, "Microsoft", "Windows", "WebCache"),
            Path.Combine(local, "CrashDumps"),
            Path.Combine(roaming, "Microsoft", "Windows", "Recent")
        ];

        return noiseRoots
            .Where(root => !string.IsNullOrWhiteSpace(root))
            .Any(root => PathSafetyService.IsPathUnder(path, root));
    }

    private static InstallChangeKind ResolveFileChangeKind(InstallFileEventRecord record, bool exists)
    {
        if (record.EventTypes.Contains("Renamed"))
        {
            return InstallChangeKind.Renamed;
        }
        if (record.EventTypes.Contains("Created") && exists)
        {
            return InstallChangeKind.Added;
        }
        if (record.EventTypes.Contains("Deleted") && !exists)
        {
            return InstallChangeKind.Removed;
        }
        if (record.EventTypes.Contains("Changed") && exists)
        {
            return InstallChangeKind.Modified;
        }
        return InstallChangeKind.Information;
    }

    private static long CalculateDirectorySize(string directory)
    {
        long total = 0;
        try
        {
            foreach (string file in EnumerateFilesSafe(directory, CancellationToken.None))
            {
                try
                {
                    total = checked(total + new FileInfo(file).Length);
                }
                catch
                {
                    // Ignore inaccessible files and arithmetic overflow.
                }
            }
        }
        catch
        {
            // A missing or inaccessible directory is reported as zero bytes.
        }
        return total;
    }

    private static IEnumerable<string> EnumerateFilesSafe(string root, CancellationToken cancellationToken)
    {
        var pending = new Stack<string>();
        pending.Push(root);
        while (pending.Count > 0)
        {
            cancellationToken.ThrowIfCancellationRequested();
            string current = pending.Pop();

            IEnumerable<string> files;
            try
            {
                files = Directory.EnumerateFiles(current, "*", SearchOption.TopDirectoryOnly).ToList();
            }
            catch
            {
                files = [];
            }

            foreach (string file in files)
            {
                cancellationToken.ThrowIfCancellationRequested();
                yield return file;
            }

            IEnumerable<string> directories;
            try
            {
                directories = Directory.EnumerateDirectories(current, "*", SearchOption.TopDirectoryOnly).ToList();
            }
            catch
            {
                directories = [];
            }

            foreach (string directory in directories)
            {
                try
                {
                    if (!File.GetAttributes(directory).HasFlag(FileAttributes.ReparsePoint))
                    {
                        pending.Push(directory);
                    }
                }
                catch
                {
                    // Ignore inaccessible directory metadata.
                }
            }
        }
    }

    private static bool IsReparsePoint(string path)
    {
        try
        {
            return File.GetAttributes(path).HasFlag(FileAttributes.ReparsePoint);
        }
        catch
        {
            return true;
        }
    }

    private static long SafeFileLength(string path)
    {
        try
        {
            return new FileInfo(path).Length;
        }
        catch
        {
            return 0;
        }
    }

    private static int ConvertRegistryInt(object? value)
        => value switch
        {
            int intValue => intValue,
            long longValue when longValue is >= int.MinValue and <= int.MaxValue => (int)longValue,
            _ when int.TryParse(value?.ToString(), out int parsed) => parsed,
            _ => 0
        };

    private static string ComputeRegistryValueHash(RegistryValueKind kind, object? value)
    {
        string canonical = value switch
        {
            null => string.Empty,
            byte[] bytes => Convert.ToHexString(bytes),
            string[] strings => string.Join("\u001F", strings),
            _ => value.ToString() ?? string.Empty
        };
        return ComputeTextHash($"{kind}|{canonical}");
    }

    private static string BuildRegistryEntryId(RegistryHive hive, RegistryView view, string keyPath, string valueName)
        => $"{hive}|{view}|{keyPath}|{valueName}";

    private static string BuildInstalledAppId(string name, string publisher, string version)
        => $"{name.Trim()}|{publisher.Trim()}|{version.Trim()}";

    private static string ComputeTextHash(string value)
        => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();

    private static async Task<string> ComputeFileHashAsync(string path, CancellationToken cancellationToken)
    {
        await using FileStream stream = new(path, FileMode.Open, FileAccess.Read, FileShare.Read, 1024 * 128, useAsync: true);
        byte[] hash = await SHA256.HashDataAsync(stream, cancellationToken);
        return Convert.ToHexString(hash).ToLowerInvariant();
    }

    private static string NormalizeToken(string value)
    {
        var builder = new StringBuilder(value.Length);
        foreach (char character in value.ToLowerInvariant())
        {
            builder.Append(char.IsLetterOrDigit(character) ? character : ' ');
        }
        return string.Join(' ', builder.ToString().Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }

    private static async Task<string> CreateReportAsync(
        InstallMonitorManifest manifest,
        string sessionDirectory,
        CancellationToken cancellationToken)
    {
        string reportPath = Path.Combine(sessionDirectory, "installation-report.html");
        string code = LocalizationService.ActiveLanguageCode;
        bool rtl = code == "ar";
        IFormatProvider culture = LocalizationService.CultureFor(code);
        string T(string key) => LocalizationService.T(key, code);
        string L(string? value) => LocalizationService.Translate(value, code);
        static string H(string? value) => System.Net.WebUtility.HtmlEncode(value ?? string.Empty);

        var html = new StringBuilder();
        html.AppendLine($"<!doctype html><html lang=\"{H(code)}\" dir=\"{(rtl ? "rtl" : "ltr")}\"><head><meta charset=\"utf-8\">");
        html.AppendLine("<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">");
        html.AppendLine($"<title>{H(T("@InstallMonitorReport"))}</title><style>");
        html.AppendLine("body{font-family:Segoe UI,Tahoma,sans-serif;background:#f4f7fb;color:#172033;margin:0;padding:28px}main{max-width:1200px;margin:auto;background:white;border:1px solid #d9e1ec;border-radius:16px;padding:24px}h1,h2{margin-top:0}.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;margin:18px 0}.box{background:#f7f9fc;border:1px solid #e9eef5;border-radius:10px;padding:12px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid #e9eef5;padding:9px;text-align:start;vertical-align:top}th{background:#f7f9fc}.warn{background:#fff7ed;border:1px solid #fed7aa;padding:12px;border-radius:10px}.muted{color:#667085}</style></head><body><main>");
        html.AppendLine($"<h1>{H(T("@InstallMonitorReport"))}</h1>");
        html.AppendLine($"<p class=\"muted\">{H(T("@Publisher"))}: {H(PublisherInfo.GetDisplayName(code))} — {H(PublisherInfo.Phone)}</p>");
        html.AppendLine("<div class=\"meta\">");
        html.AppendLine($"<div class=\"box\"><b>{H(L("ملف التثبيت"))}</b><br>{H(manifest.InstallerName)}</div>");
        html.AppendLine($"<div class=\"box\"><b>{H(T("@SessionStarted"))}</b><br>{H(manifest.StartedAt.LocalDateTime.ToString("G", culture))}</div>");
        html.AppendLine($"<div class=\"box\"><b>{H(L("البرنامج المكتشف"))}</b><br>{H(string.IsNullOrWhiteSpace(manifest.DetectedApplicationName) ? "—" : manifest.DetectedApplicationName)}</div>");
        html.AppendLine($"<div class=\"box\"><b>{H(T("@ChangeCount"))}</b><br>{manifest.Changes.Count.ToString("N0", culture)}</div>");
        html.AppendLine("</div>");
        html.AppendLine($"<p><b>SHA-256:</b> <code>{H(manifest.InstallerSha256)}</code></p>");
        if (manifest.Warnings.Count > 0)
        {
            html.AppendLine($"<div class=\"warn\"><b>{H(T("@Alerts"))}:</b><ul>");
            foreach (string warning in manifest.Warnings.Distinct())
            {
                html.AppendLine($"<li>{H(L(warning))}</li>");
            }
            html.AppendLine("</ul></div>");
        }

        html.AppendLine($"<h2>{H(T("@ObservedChanges"))}</h2><table><thead><tr><th>{H(L("الفئة"))}</th><th>{H(L("التغيير"))}</th><th>{H(L("العنصر"))}</th><th>{H(L("الموقع"))}</th><th>{H(L("الثقة"))}</th><th>{H(L("التفاصيل"))}</th></tr></thead><tbody>");
        foreach (InstallChangeItem change in manifest.Changes)
        {
            html.AppendLine($"<tr><td>{H(L(change.CategoryText))}</td><td>{H(L(change.KindText))}</td><td>{H(change.Name)}</td><td>{H(change.Location)}</td><td>{H(L(change.Confidence))}</td><td>{H(L(change.Details))}</td></tr>");
        }
        html.AppendLine("</tbody></table>");
        html.AppendLine($"<p class=\"muted\">{H(T("@MonitoringNote"))}</p>");
        html.AppendLine("</main></body></html>");

        await File.WriteAllTextAsync(reportPath, html.ToString(), new UTF8Encoding(false), cancellationToken);
        return reportPath;
    }

    private static string GetSessionDirectory(string sessionId)
    {
        if (string.IsNullOrWhiteSpace(sessionId)
            || sessionId.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0
            || sessionId.Contains(Path.DirectorySeparatorChar)
            || sessionId.Contains(Path.AltDirectorySeparatorChar))
        {
            throw new InvalidOperationException("Invalid installation monitoring session identifier.");
        }

        Directory.CreateDirectory(MonitorRoot);
        string root = Path.TrimEndingDirectorySeparator(Path.GetFullPath(MonitorRoot)) + Path.DirectorySeparatorChar;
        string directory = Path.GetFullPath(Path.Combine(MonitorRoot, sessionId));
        if (!directory.StartsWith(root, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("The monitoring session path is outside the approved root.");
        }
        if (Directory.Exists(directory) && IsReparsePoint(directory))
        {
            throw new InvalidOperationException("Reparse-point monitoring session directories are not allowed.");
        }
        return directory;
    }

    private static async Task<InstallMonitorManifest> LoadManifestAsync(
        string sessionId,
        CancellationToken cancellationToken)
    {
        string path = Path.Combine(GetSessionDirectory(sessionId), ManifestFileName);
        InstallMonitorManifest? manifest = await ReadJsonAsync<InstallMonitorManifest>(path, cancellationToken);
        if (manifest is null || !string.Equals(manifest.SessionId, sessionId, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("The monitoring session manifest is missing or invalid.");
        }
        return manifest;
    }

    private static InstallMonitorSessionSummary ToSummary(InstallMonitorManifest manifest)
        => new()
        {
            SessionId = manifest.SessionId,
            InstallerName = manifest.InstallerName,
            InstallerPath = manifest.InstallerPath,
            InstallerSha256 = manifest.InstallerSha256,
            StartedAt = manifest.StartedAt,
            CompletedAt = manifest.CompletedAt,
            Status = manifest.Status,
            ChangeCount = manifest.Changes.Count,
            DetectedApplicationName = manifest.DetectedApplicationName,
            ReportPath = manifest.ReportPath,
            UninstallString = manifest.DetectedUninstallString
        };

    private static T? ReadJson<T>(string path)
    {
        if (!File.Exists(path))
        {
            return default;
        }
        return JsonSerializer.Deserialize<T>(File.ReadAllText(path), JsonOptions);
    }

    private static async Task<T?> ReadJsonAsync<T>(string path, CancellationToken cancellationToken)
    {
        if (!File.Exists(path))
        {
            return default;
        }
        await using FileStream stream = new(path, FileMode.Open, FileAccess.Read, FileShare.Read, 64 * 1024, useAsync: true);
        return await JsonSerializer.DeserializeAsync<T>(stream, JsonOptions, cancellationToken);
    }

    private static async Task WriteJsonAtomicAsync<T>(string path, T value, CancellationToken cancellationToken)
    {
        string? parent = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(parent))
        {
            Directory.CreateDirectory(parent);
        }
        string temp = path + ".tmp";
        await using (FileStream stream = new(temp, FileMode.Create, FileAccess.Write, FileShare.None, 64 * 1024, useAsync: true))
        {
            await JsonSerializer.SerializeAsync(stream, value, JsonOptions, cancellationToken);
            await stream.FlushAsync(cancellationToken);
        }
        File.Move(temp, path, overwrite: true);
    }

    private static void ThrowIfDisposedStatic(bool disposed)
    {
        if (disposed)
        {
            throw new ObjectDisposedException(nameof(InstallMonitorService));
        }
    }

    private void ThrowIfDisposed() => ThrowIfDisposedStatic(_disposed);

    private sealed record RegistryCaptureRoot(
        RegistryHive Hive,
        RegistryView View,
        string Path,
        int MaximumDepth);

    private sealed class ActiveInstallSession : IDisposable
    {
        private readonly Action<ActiveInstallSession, string, string, string?> _onEvent;
        private readonly List<FileSystemWatcher> _watchers = [];
        private readonly object _journalLock = new();
        private readonly StreamWriter _journalWriter;
        private bool _stopped;
        private bool _disposed;

        public ActiveInstallSession(
            InstallMonitorManifest manifest,
            string sessionDirectory,
            Action<ActiveInstallSession, string, string, string?> onEvent)
        {
            Manifest = manifest;
            SessionDirectory = sessionDirectory;
            _onEvent = onEvent;
            string journalPath = Path.Combine(sessionDirectory, EventJournalFileName);
            _journalWriter = new StreamWriter(new FileStream(journalPath, FileMode.Append, FileAccess.Write, FileShare.Read), new UTF8Encoding(false))
            {
                AutoFlush = true
            };
        }

        public InstallMonitorManifest Manifest { get; }
        public string SessionDirectory { get; }
        public ConcurrentDictionary<string, InstallFileEventRecord> FileEvents { get; } = new(StringComparer.OrdinalIgnoreCase);

        public void StartWatchers()
        {
            foreach (string root in Manifest.MonitoredRoots)
            {
                try
                {
                    var watcher = new FileSystemWatcher(root)
                    {
                        IncludeSubdirectories = true,
                        NotifyFilter = NotifyFilters.FileName
                                       | NotifyFilters.DirectoryName
                                       | NotifyFilters.CreationTime
                                       | NotifyFilters.LastWrite
                                       | NotifyFilters.Size,
                        InternalBufferSize = 64 * 1024,
                        EnableRaisingEvents = false
                    };
                    watcher.Created += (_, args) => _onEvent(this, "Created", args.FullPath, null);
                    watcher.Changed += (_, args) => _onEvent(this, "Changed", args.FullPath, null);
                    watcher.Deleted += (_, args) => _onEvent(this, "Deleted", args.FullPath, null);
                    watcher.Renamed += (_, args) => _onEvent(this, "Renamed", args.FullPath, args.OldFullPath);
                    watcher.Error += (_, args) =>
                    {
                        string warning = $"امتلأ مخزن مراقبة الملفات أو حدث خطأ داخل {root}: {args.GetException().Message}";
                        lock (Manifest.Warnings)
                        {
                            Manifest.Warnings.Add(warning);
                        }
                        AppLogger.Error(warning, args.GetException());
                    };
                    watcher.EnableRaisingEvents = true;
                    _watchers.Add(watcher);
                }
                catch (Exception ex)
                {
                    Manifest.Warnings.Add($"تعذر مراقبة {root}: {ex.Message}");
                }
            }
        }

        public void StopWatchers()
        {
            if (_stopped)
            {
                return;
            }
            foreach (FileSystemWatcher watcher in _watchers)
            {
                try
                {
                    watcher.EnableRaisingEvents = false;
                }
                catch
                {
                    // Best effort.
                }
            }
            _stopped = true;
        }

        public IReadOnlyCollection<InstallFileEventRecord> GetFileEvents()
            => FileEvents.Values.Select(record => new InstallFileEventRecord
            {
                Path = record.Path,
                OldPath = record.OldPath,
                EventTypes = new HashSet<string>(record.EventTypes, StringComparer.OrdinalIgnoreCase),
                FirstSeenUtc = record.FirstSeenUtc,
                LastSeenUtc = record.LastSeenUtc
            }).ToList();

        public void AppendJournal(object record)
        {
            lock (_journalLock)
            {
                if (_disposed)
                {
                    return;
                }
                _journalWriter.WriteLine(JsonSerializer.Serialize(record, CompactJsonOptions));
            }
        }

        public void Dispose()
        {
            if (_disposed)
            {
                return;
            }
            StopWatchers();
            foreach (FileSystemWatcher watcher in _watchers)
            {
                watcher.Dispose();
            }
            lock (_journalLock)
            {
                _journalWriter.Dispose();
            }
            _disposed = true;
        }
    }
}
