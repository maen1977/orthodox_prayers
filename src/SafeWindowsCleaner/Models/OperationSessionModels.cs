using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner.Models;

public enum OperationSessionStatus
{
    Planned,
    PreviewOnly,
    Approved,
    ElevationRequested,
    Completed,
    CompletedWithWarnings,
    Failed,
    Cancelled
}

public sealed class OperationSessionRecord
{
    public Guid SessionId { get; set; } = Guid.NewGuid();
    public DateTimeOffset CreatedAtUtc { get; set; } = DateTimeOffset.UtcNow;
    public DateTimeOffset UpdatedAtUtc { get; set; } = DateTimeOffset.UtcNow;
    public string Operation { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public int PlannedItemCount { get; set; }
    public long EstimatedBytes { get; set; }
    public bool RequiresAdministrator { get; set; }
    public bool Recoverable { get; set; }
    public OperationSessionStatus Status { get; set; } = OperationSessionStatus.Planned;
    public string Summary { get; set; } = string.Empty;
    public List<OperationPreviewItem> Items { get; set; } = [];

    public string OperationText => LocalizationService.Translate(Operation);
    public string SummaryText => LocalizationService.Translate(Summary);
    public string UpdatedAtText => UpdatedAtUtc.ToLocalTime().ToString(
        "yyyy-MM-dd HH:mm",
        LocalizationService.CultureFor(LocalizationService.ActiveLanguageCode));
    public string RecoverableText => LocalizationService.T(
        Recoverable ? "@PartiallyRecoverable" : "@AuditPlanRecord");
    public string StatusText => LocalizationService.T(Status switch
    {
        OperationSessionStatus.Planned => "@SessionPlanned",
        OperationSessionStatus.PreviewOnly => "@SessionPreviewOnly",
        OperationSessionStatus.Approved => "@SessionApproved",
        OperationSessionStatus.ElevationRequested => "@SessionElevationRequested",
        OperationSessionStatus.Completed => "@SessionCompleted",
        OperationSessionStatus.CompletedWithWarnings => "@SessionCompletedWarnings",
        OperationSessionStatus.Failed => "@SessionFailed",
        _ => "@SessionCancelled"
    });
}
