using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner.Models;

public sealed class ActivityLogEntry
{
    public long Sequence { get; set; }
    public DateTimeOffset TimestampUtc { get; set; }
    public string Operation { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public string Summary { get; set; } = string.Empty;
    public int ItemCount { get; set; }
    public long BytesAffected { get; set; }
    public long RestorePointSequence { get; set; }
    public string PreviousHash { get; set; } = string.Empty;
    public string Hash { get; set; } = string.Empty;

    public string OperationText => LocalizationService.Translate(Operation);
    public string StatusText => LocalizationService.Translate(Status);
    public string SummaryText => LocalizationService.Translate(Summary);
    public string TimestampText => TimestampUtc.LocalDateTime.ToString(
        "yyyy/MM/dd HH:mm:ss",
        LocalizationService.CultureFor(LocalizationService.ActiveLanguageCode));
    public string BytesText => SizeFormatter.Format(BytesAffected);
    public string RestorePointText => RestorePointSequence > 0 ? RestorePointSequence.ToString() : "—";
}

public sealed record ActivityLogVerificationResult(bool IsValid, int EntryCount, string Message);
