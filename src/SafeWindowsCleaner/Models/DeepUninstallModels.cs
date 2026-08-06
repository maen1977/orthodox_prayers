using SafeWindowsCleaner.Helpers;

namespace SafeWindowsCleaner.Models;

public enum DeepUninstallArtifactKind
{
    Directory,
    File,
    RegistryKey,
    RegistryValue,
    Service,
    ScheduledTask,
    Process,
    PendingDelete
}

public sealed class DeepUninstallArtifact
{
    public DeepUninstallArtifactKind Kind { get; init; }
    public string Name { get; init; } = string.Empty;
    public string Location { get; init; } = string.Empty;
    public string Reason { get; init; } = string.Empty;
    public int ConfidenceScore { get; init; }
    public long SizeBytes { get; init; }
    public bool Removed { get; set; }
    public bool RequiresRestart { get; set; }
    public string Error { get; set; } = string.Empty;

    public string SizeText => SizeBytes > 0 ? SizeFormatter.Format(SizeBytes) : "—";
}

public sealed class DeepUninstallResult
{
    public string ApplicationName { get; init; } = string.Empty;
    public string Publisher { get; init; } = string.Empty;
    public string LanguageCode { get; init; } = "en";
    public DateTimeOffset StartedAt { get; init; } = DateTimeOffset.UtcNow;
    public DateTimeOffset CompletedAt { get; set; }

    public int ProcessesStopped { get; set; }
    public int DirectoriesQuarantined { get; set; }
    public int FilesQuarantined { get; set; }
    public long BytesQuarantined { get; set; }
    public int RegistryKeysRemoved { get; set; }
    public int RegistryValuesRemoved { get; set; }
    public int ServicesRemoved { get; set; }
    public int ScheduledTasksRemoved { get; set; }
    public int PendingDeleteItems { get; set; }
    public int FailedItems { get; set; }
    public int SkippedItems { get; set; }
    public bool RestartRequired { get; set; }

    public string BackupDirectory { get; set; } = string.Empty;
    public string HtmlReportPath { get; set; } = string.Empty;
    public string JsonReportPath { get; set; } = string.Empty;
    public List<DeepUninstallArtifact> Artifacts { get; } = [];
    public List<string> Warnings { get; } = [];

    public int TotalRemovedItems => ProcessesStopped
                                    + DirectoriesQuarantined
                                    + FilesQuarantined
                                    + RegistryKeysRemoved
                                    + RegistryValuesRemoved
                                    + ServicesRemoved
                                    + ScheduledTasksRemoved
                                    + PendingDeleteItems;
}

public sealed record DeepUninstallReportResult(string HtmlPath, string JsonPath);
