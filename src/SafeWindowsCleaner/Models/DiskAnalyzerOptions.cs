namespace SafeWindowsCleaner.Models;

public sealed class DiskAnalyzerOptions
{
    public int LargestFileLimit { get; init; } = 200;
    public long MinimumDuplicateSizeBytes { get; init; } = 50L * 1024L * 1024L;
    public bool CalculateDuplicates { get; init; }
    public int DuplicateCandidateLimit { get; init; } = 20_000;
    public int DuplicateResultFileLimit { get; init; } = 1_000;
    public int ProgressInterval { get; init; } = 1_000;
    public int HashBufferSizeBytes { get; init; } = 128 * 1024;
    public int ScanThrottleMilliseconds { get; init; } = 1;
}
