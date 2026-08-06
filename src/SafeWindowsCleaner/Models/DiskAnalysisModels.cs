using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner.Models;

public sealed class DiskFileItem : ObservableObject
{
    private bool _isSelected;

    public required string Name { get; init; }
    public required string Path { get; init; }
    public required long SizeBytes { get; init; }
    public required DateTime LastModified { get; init; }
    public required string Category { get; init; }
    public string Extension { get; init; } = string.Empty;
    public bool IsSafeToQuarantine { get; init; }
    public string ProtectionReason { get; init; } = string.Empty;
    public string ScanRoot { get; init; } = string.Empty;
    public string DuplicateGroup { get; init; } = string.Empty;
    public string HashShort { get; init; } = string.Empty;
    public bool IsPreferredCopy { get; init; }

    public string CategoryText => LocalizationService.Translate(Category);
    public string ProtectionReasonText => LocalizationService.Translate(ProtectionReason);
    public string SizeText => SizeFormatter.Format(SizeBytes);
    public string LastModifiedText => LastModified.ToString("yyyy/MM/dd HH:mm", LocalizationService.CultureFor(LocalizationService.ActiveLanguageCode));
    public string SafetyText => LocalizationService.T(IsSafeToQuarantine ? "@DiskMovable" : "@Protected");
    public string CopyStatus => string.IsNullOrWhiteSpace(DuplicateGroup)
        ? string.Empty
        : LocalizationService.T(IsPreferredCopy ? "@ReferenceCopy" : "@AdditionalCopy");

    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            if (!IsSafeToQuarantine && value)
            {
                value = false;
            }

            SetProperty(ref _isSelected, value);
        }
    }
}

public sealed class DiskFolderSummary
{
    public required string Name { get; init; }
    public required string Path { get; init; }
    public required long SizeBytes { get; init; }
    public required int FileCount { get; init; }

    public string SizeText => SizeFormatter.Format(SizeBytes);
}

public sealed class DiskCategorySummary
{
    public required string Category { get; init; }
    public required long SizeBytes { get; init; }
    public required int FileCount { get; init; }
    public required double Percentage { get; init; }

    public string CategoryText => LocalizationService.Translate(Category);
    public string SizeText => SizeFormatter.Format(SizeBytes);
    public string PercentageText => $"{Percentage:0.#}%";
}

public sealed class DiskAnalysisResult
{
    public required string RootPath { get; init; }
    public required long TotalBytes { get; init; }
    public required long DuplicateWasteBytes { get; init; }
    public required int FileCount { get; init; }
    public required int SkippedEntries { get; init; }
    public required bool DuplicateAnalysisPerformed { get; init; }
    public required bool DuplicateCandidateLimitReached { get; init; }
    public required bool DuplicateResultLimitReached { get; init; }
    public required List<DiskFileItem> LargestFiles { get; init; }
    public required List<DiskFileItem> DuplicateFiles { get; init; }
    public required List<DiskFolderSummary> FolderSummaries { get; init; }
    public required List<DiskCategorySummary> CategorySummaries { get; init; }
}

public sealed record DiskScanProgress(string Message, int FilesScanned, long BytesScanned);
