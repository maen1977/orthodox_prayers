using System.Text.Json.Serialization;
using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner.Models;

public enum InstallMonitorStatus
{
    Monitoring,
    Completed,
    Cancelled,
    Interrupted,
    Failed
}

public enum InstallChangeCategory
{
    FileSystem,
    Registry,
    Service,
    ScheduledTask,
    InstalledApplication
}

public enum InstallChangeKind
{
    Added,
    Modified,
    Removed,
    Renamed,
    Information
}

public sealed class InstallMonitorSessionSummary
{
    public required string SessionId { get; init; }
    public required string InstallerName { get; init; }
    public string InstallerPath { get; init; } = string.Empty;
    public string InstallerSha256 { get; init; } = string.Empty;
    public DateTimeOffset StartedAt { get; init; }
    public DateTimeOffset? CompletedAt { get; init; }
    public InstallMonitorStatus Status { get; init; }
    public int ChangeCount { get; init; }
    public string DetectedApplicationName { get; init; } = string.Empty;
    public string ReportPath { get; init; } = string.Empty;
    public string UninstallString { get; init; } = string.Empty;
    public string StatusText => LocalizationService.T(Status switch
    {
        InstallMonitorStatus.Monitoring => "@MonitorStatusMonitoring",
        InstallMonitorStatus.Completed => "@MonitorStatusCompleted",
        InstallMonitorStatus.Cancelled => "@MonitorStatusCancelled",
        InstallMonitorStatus.Interrupted => "@MonitorStatusInterrupted",
        InstallMonitorStatus.Failed => "@MonitorStatusFailed",
        _ => "@Unknown"
    });
    public string StartedAtText => StartedAt.LocalDateTime.ToString(
        "yyyy/MM/dd HH:mm",
        LocalizationService.CultureFor(LocalizationService.ActiveLanguageCode));
    public string CompletedAtText => CompletedAt?.LocalDateTime.ToString(
        "yyyy/MM/dd HH:mm",
        LocalizationService.CultureFor(LocalizationService.ActiveLanguageCode)) ?? "—";
    public string ApplicationText => string.IsNullOrWhiteSpace(DetectedApplicationName) ? "—" : DetectedApplicationName;
}

public sealed class InstallChangeItem : ObservableObject
{
    private bool _isSelected;

    public string Id { get; init; } = Guid.NewGuid().ToString("N");
    public InstallChangeCategory Category { get; init; }
    public InstallChangeKind Kind { get; init; }
    public string Name { get; init; } = string.Empty;
    public string Location { get; init; } = string.Empty;
    public string Details { get; init; } = string.Empty;
    public string Confidence { get; init; } = "@ConfidenceMedium";
    public long SizeBytes { get; init; }
    public bool IsDirectory { get; init; }
    public bool IsSafeToQuarantine { get; init; }
    [JsonIgnore]
    public bool ExistsNow { get; set; }

    [JsonIgnore]
    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            if (IsSafeToQuarantine)
            {
                SetProperty(ref _isSelected, value);
            }
        }
    }

    [JsonIgnore]
    public string CategoryText => LocalizationService.T(Category switch
    {
        InstallChangeCategory.FileSystem => "@Files",
        InstallChangeCategory.Registry => "@Registry",
        InstallChangeCategory.Service => "@Service",
        InstallChangeCategory.ScheduledTask => "@ScheduledTask",
        InstallChangeCategory.InstalledApplication => "@InstalledApplication",
        _ => "@Unknown"
    });

    [JsonIgnore]
    public string KindText => LocalizationService.T(Kind switch
    {
        InstallChangeKind.Added => "@ChangeAdded",
        InstallChangeKind.Modified => "@ChangeModified",
        InstallChangeKind.Removed => "@ChangeRemoved",
        InstallChangeKind.Renamed => "@ChangeRenamed",
        InstallChangeKind.Information => "@Information",
        _ => "@Unknown"
    });

    [JsonIgnore]
    public string ConfidenceText => LocalizationService.Translate(Confidence);

    [JsonIgnore]
    public string LocationText => LocalizationService.Translate(Location);

    [JsonIgnore]
    public string DetailsText => LocalizationService.Translate(Details);

    [JsonIgnore]
    public string SizeText => SizeBytes > 0 ? SizeFormatter.Format(SizeBytes) : "—";
    [JsonIgnore]
    public string CurrentStateText => LocalizationService.T(ExistsNow ? "@ExistsNow" : "@NotPresent");
    [JsonIgnore]
    public string SelectionSafetyText => LocalizationService.T(IsSafeToQuarantine ? "@CanQuarantine" : "@ReviewOnly");
}

public sealed class InstallMonitorManifest
{
    public string SchemaVersion { get; set; } = "1.0";
    public string SessionId { get; set; } = string.Empty;
    public string InstallerName { get; set; } = string.Empty;
    public string InstallerPath { get; set; } = string.Empty;
    public string InstallerSha256 { get; set; } = string.Empty;
    public DateTimeOffset StartedAt { get; set; }
    public DateTimeOffset? CompletedAt { get; set; }
    public InstallMonitorStatus Status { get; set; }
    public int InstallerProcessId { get; set; }
    public string DetectedApplicationName { get; set; } = string.Empty;
    public string DetectedPublisher { get; set; } = string.Empty;
    public string DetectedVersion { get; set; } = string.Empty;
    public string DetectedInstallLocation { get; set; } = string.Empty;
    public string DetectedUninstallString { get; set; } = string.Empty;
    public string ReportPath { get; set; } = string.Empty;
    public List<string> MonitoredRoots { get; set; } = [];
    public List<string> Warnings { get; set; } = [];
    public List<InstallChangeItem> Changes { get; set; } = [];
}

public sealed class InstallSystemSnapshot
{
    public DateTimeOffset CapturedAt { get; set; }
    public Dictionary<string, RegistrySnapshotEntry> Registry { get; set; } = new(StringComparer.OrdinalIgnoreCase);
    public Dictionary<string, ServiceSnapshotEntry> Services { get; set; } = new(StringComparer.OrdinalIgnoreCase);
    public Dictionary<string, TaskSnapshotEntry> ScheduledTasks { get; set; } = new(StringComparer.OrdinalIgnoreCase);
    public Dictionary<string, InstalledAppSnapshotEntry> InstalledApplications { get; set; } = new(StringComparer.OrdinalIgnoreCase);
    public List<string> Warnings { get; set; } = [];
}

public sealed class RegistrySnapshotEntry
{
    public string Id { get; set; } = string.Empty;
    public string Hive { get; set; } = string.Empty;
    public string View { get; set; } = string.Empty;
    public string KeyPath { get; set; } = string.Empty;
    public string ValueName { get; set; } = string.Empty;
    public string ValueKind { get; set; } = string.Empty;
    public string ValueHash { get; set; } = string.Empty;
}

public sealed class ServiceSnapshotEntry
{
    public string Name { get; set; } = string.Empty;
    public string DisplayName { get; set; } = string.Empty;
    public string ImagePath { get; set; } = string.Empty;
    public int StartMode { get; set; }
    public int ServiceType { get; set; }
    public string Fingerprint { get; set; } = string.Empty;
}

public sealed class TaskSnapshotEntry
{
    public string RelativePath { get; set; } = string.Empty;
    public long Length { get; set; }
    public DateTimeOffset LastWriteTimeUtc { get; set; }
    public string Fingerprint { get; set; } = string.Empty;
}

public sealed class InstalledAppSnapshotEntry
{
    public string Id { get; set; } = string.Empty;
    public string DisplayName { get; set; } = string.Empty;
    public string Publisher { get; set; } = string.Empty;
    public string Version { get; set; } = string.Empty;
    public string InstallLocation { get; set; } = string.Empty;
    public string UninstallString { get; set; } = string.Empty;
    public long EstimatedSizeBytes { get; set; }
    public string Fingerprint { get; set; } = string.Empty;
}

public sealed class InstallFileEventRecord
{
    public string Path { get; set; } = string.Empty;
    public string OldPath { get; set; } = string.Empty;
    public HashSet<string> EventTypes { get; set; } = new(StringComparer.OrdinalIgnoreCase);
    public DateTimeOffset FirstSeenUtc { get; set; }
    public DateTimeOffset LastSeenUtc { get; set; }
}

public sealed record InstallMonitorStartResult(
    InstallMonitorSessionSummary Session,
    int InstallerProcessId,
    IReadOnlyList<string> Warnings);

public sealed record InstallMonitorCompletionResult(
    InstallMonitorSessionSummary Session,
    IReadOnlyList<InstallChangeItem> Changes,
    IReadOnlyList<string> Warnings);

public sealed record MonitoredResidualAnalysisResult(
    int ExistingFileSystemItems,
    int ExistingServices,
    int ExistingScheduledTasks,
    int ExistingRegistryItems,
    IReadOnlyList<InstallChangeItem> Changes);
