using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner.Models;

public sealed class QuickTuneSummary
{
    public int TemporaryFileCount { get; init; }
    public long TemporaryBytes { get; init; }
    public int OrphanCandidateCount { get; init; }
    public int HighConfidenceOrphanCount { get; init; }
    public long OrphanBytes { get; init; }
    public int RecommendedProcessCount { get; init; }
    public long RecommendedProcessBytes { get; init; }
    public int RecommendedStartupCount { get; init; }

    public string TemporaryText => LocalizationService.Format(
        "@FilesAndSize", LocalizationService.ActiveLanguageCode,
        TemporaryFileCount, SizeFormatter.Format(TemporaryBytes));
    public string OrphanText => LocalizationService.Format(
        "@ResultsAndSize", LocalizationService.ActiveLanguageCode,
        OrphanCandidateCount, SizeFormatter.Format(OrphanBytes));
    public string MemoryText => LocalizationService.Format(
        "@ProgramsAndSize", LocalizationService.ActiveLanguageCode,
        RecommendedProcessCount, SizeFormatter.Format(RecommendedProcessBytes));
    public string StartupText => LocalizationService.Format(
        "@StartupReviewCount", LocalizationService.ActiveLanguageCode,
        RecommendedStartupCount);
}
