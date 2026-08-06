using SafeWindowsCleaner.Helpers;

namespace SafeWindowsCleaner.Models;

public sealed class AutomaticCleanupResult
{
    public DateTimeOffset StartedAt { get; init; }
    public DateTimeOffset CompletedAt { get; set; }
    public bool Cancelled { get; set; }
    public bool PreviewOnly { get; set; }
    public string LanguageCode { get; set; } = "en";

    public int TemporaryDeletedFiles { get; set; }
    public int TemporaryFailedFiles { get; set; }
    public long TemporaryFreedBytes { get; set; }

    public int OrphanCandidatesFound { get; set; }
    public int OrphansQuarantined { get; set; }
    public int OrphansFailed { get; set; }
    public int OrphansSkipped { get; set; }
    public long OrphanBytesQuarantined { get; set; }

    public int BrokenRegistryEntriesFound { get; set; }
    public int BrokenRegistryEntriesDisabled { get; set; }
    public int BrokenStartupItemsFound { get; set; }
    public int BrokenStartupItemsDisabled { get; set; }
    public int StartupItemsFailed { get; set; }

    public bool RestorePointAttempted { get; set; }
    public bool RestorePointCreated { get; set; }
    public long RestorePointSequence { get; set; }
    public string RestorePointMessage { get; set; } = string.Empty;

    public string HtmlReportPath { get; set; } = string.Empty;
    public string JsonReportPath { get; set; } = string.Empty;
    public List<string> Actions { get; } = [];
    public List<string> Warnings { get; } = [];
    public List<string> SkippedItems { get; } = [];

    public long TotalDiskBytesFreed => TemporaryFreedBytes;
    public long TotalDiskBytesProcessed => TemporaryFreedBytes + OrphanBytesQuarantined;
    public int TotalChangedItems => TemporaryDeletedFiles
                                    + OrphansQuarantined
                                    + BrokenRegistryEntriesDisabled
                                    + BrokenStartupItemsDisabled;

    public string DiskFreedText => SizeFormatter.Format(TotalDiskBytesFreed, LanguageCode);
    public string DiskProcessedText => SizeFormatter.Format(TotalDiskBytesProcessed, LanguageCode);
}

public sealed record AutomaticCleanupReportResult(string HtmlPath, string JsonPath);
