using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner.Models;

public sealed class QuarantineItem : ObservableObject
{
    private bool _isSelected;

    public required string SessionId { get; init; }
    public required string Name { get; init; }
    public required string OriginalPath { get; init; }
    public required string QuarantinedPath { get; init; }
    public required DateTimeOffset QuarantinedAt { get; init; }
    public required long SizeBytes { get; init; }
    public bool IsDirectory { get; init; } = true;
    public string SourcePolicy { get; init; } = "ApplicationDirectory";
    public int RetentionWarningDays { get; set; } = 30;

    public string SizeText => SizeFormatter.Format(SizeBytes);
    public string ItemTypeText => LocalizationService.T(IsDirectory ? "@Directory" : "@File");
    public string QuarantinedAtText => QuarantinedAt.LocalDateTime.ToString(
        "yyyy/MM/dd HH:mm",
        LocalizationService.CultureFor(LocalizationService.ActiveLanguageCode));
    public int AgeDays => Math.Max(0, (int)(DateTimeOffset.UtcNow - QuarantinedAt).TotalDays);
    public string RetentionText => LocalizationService.Format(
        AgeDays >= RetentionWarningDays ? "@OldDaysCount" : "@DaysCount",
        LocalizationService.ActiveLanguageCode,
        AgeDays);

    public bool IsSelected
    {
        get => _isSelected;
        set => SetProperty(ref _isSelected, value);
    }
}
