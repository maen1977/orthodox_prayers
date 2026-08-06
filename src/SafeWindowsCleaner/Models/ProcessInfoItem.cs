using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner.Models;

public sealed class ProcessInfoItem
{
    public required string Name { get; init; }
    public required int ProcessId { get; init; }
    public required long WorkingSetBytes { get; init; }
    public required long PrivateMemoryBytes { get; init; }
    public string ExecutablePath { get; init; } = string.Empty;
    public string WindowTitle { get; init; } = string.Empty;
    public DateTime StartTimeUtc { get; init; }
    public bool IsCurrentUserSession { get; init; }
    public bool IsSystemProtected { get; init; }
    public bool CanClose { get; init; }
    public bool IsRecommended { get; init; }
    public string RecommendationText { get; init; } = "@ProcessReviewBeforeClose";

    public string WorkingSetText => SizeFormatter.Format(WorkingSetBytes);
    public string PrivateMemoryText => SizeFormatter.Format(PrivateMemoryBytes);
    public string RecommendationDisplayText => LocalizationService.Translate(RecommendationText);
    public string SafetyText => LocalizationService.T(IsSystemProtected
        ? "@Protected"
        : CanClose ? "@UserApplication" : "@SafetyReview");
    public string ProcessTypeText => LocalizationService.T(IsSystemProtected
        ? "@MemoryProcessProtected"
        : !string.IsNullOrWhiteSpace(WindowTitle)
            ? "@MemoryProcessVisible"
            : "@MemoryProcessBackground");
    public string WindowDisplayText => string.IsNullOrWhiteSpace(WindowTitle)
        ? LocalizationService.T("@NoVisibleWindow")
        : WindowTitle;
}

public sealed record ProcessMemoryAction(
    string ProcessName,
    int ProcessId,
    string Action,
    long BeforeBytes,
    long AfterBytes)
{
    public long FreedBytes => Math.Max(0, BeforeBytes - AfterBytes);
}

public sealed class ProcessOperationResult
{
    public int SucceededItems { get; set; }
    public int FailedItems { get; set; }
    public int SkippedItems { get; set; }
    public long EstimatedBytesAffected { get; set; }
    public List<ProcessMemoryAction> Actions { get; } = [];
}
