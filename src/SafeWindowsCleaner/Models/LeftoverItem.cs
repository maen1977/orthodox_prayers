using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner.Models;

public sealed class LeftoverItem : ObservableObject
{
    private bool _isSelected;

    public required string Name { get; init; }
    public required string Path { get; init; }
    public required string Location { get; init; }
    public required long SizeBytes { get; init; }
    public string ItemType { get; init; } = "@Directory";
    public int ConfidenceScore { get; init; }
    public string MatchReason { get; init; } = "@NameMatch";
    public bool IsQuarantinable { get; init; } = true;
    public bool SizeIsEstimated { get; init; }
    public DateTime LastModifiedUtc { get; init; }

    public string LocationText => LocalizationService.Translate(Location);
    public string ItemTypeText => LocalizationService.Translate(ItemType);
    public string MatchReasonText => LocalizationService.Translate(MatchReason);
    public string SizeText => (SizeIsEstimated ? "~ " : string.Empty) + SizeFormatter.Format(SizeBytes);
    public string LastModifiedText => LastModifiedUtc == default
        ? "—"
        : LastModifiedUtc.ToLocalTime().ToString(
            "yyyy-MM-dd",
            LocalizationService.CultureFor(LocalizationService.ActiveLanguageCode));
    public string ConfidenceText => LocalizationService.T(ConfidenceScore switch
    {
        >= 90 => "@ConfidenceVeryHigh",
        >= 80 => "@ConfidenceHigh",
        >= 55 => "@ConfidenceMedium",
        _ => "@ConfidenceLow"
    });

    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            if (!IsQuarantinable && value)
            {
                value = false;
            }

            SetProperty(ref _isSelected, value);
        }
    }
}
