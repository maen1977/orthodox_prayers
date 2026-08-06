using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner.Models;

public sealed class CleanupTarget : ObservableObject
{
    private bool _isSelected = true;
    private long _sizeBytes;
    private int _fileCount;

    public string Id { get; init; } = Guid.NewGuid().ToString("N");
    public required string Name { get; init; }
    public required string Description { get; init; }
    public string Group { get; init; } = "Other";
    public CleanupSafetyTier SafetyTier { get; init; } = CleanupSafetyTier.Safe;
    public bool RequiresAdministrator { get; init; }
    public bool EnabledByDefault { get; init; } = true;
    public required string RootPath { get; init; }
    public required string[] SearchPatterns { get; init; }
    public bool Recursive { get; init; }
    public TimeSpan MinimumAge { get; init; } = TimeSpan.FromDays(1);
    public List<string> Files { get; } = [];
    public bool ScanTruncated { get; set; }

    public string DisplayName => LocalizationService.Translate(Name);
    public string DisplayDescription => LocalizationService.Translate(Description);
    public string DisplayGroup => LocalizationService.Translate(Group);

    public bool IsSelected
    {
        get => _isSelected;
        set => SetProperty(ref _isSelected, value);
    }

    public long SizeBytes
    {
        get => _sizeBytes;
        set
        {
            if (SetProperty(ref _sizeBytes, value))
            {
                OnPropertyChanged(nameof(SizeText));
            }
        }
    }

    public int FileCount
    {
        get => _fileCount;
        set => SetProperty(ref _fileCount, value);
    }

    public string SafetyText => LocalizationService.T(SafetyTier switch
    {
        CleanupSafetyTier.Safe => "@SafetySafe",
        CleanupSafetyTier.Review => "@SafetyReview",
        _ => "@SafetyAdvanced"
    });

    public string SizeText => SizeFormatter.Format(SizeBytes);
}
