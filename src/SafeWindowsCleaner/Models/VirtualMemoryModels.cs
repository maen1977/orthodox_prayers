namespace SafeWindowsCleaner.Models;

public sealed record PagingFileConfiguration(
    string Path,
    int InitialSizeMb,
    int MaximumSizeMb);

public sealed record VirtualMemoryStatus(
    string SystemDrive,
    long FreeBytes,
    bool AutomaticManagedPagefile,
    IReadOnlyList<string> RawPagingFileEntries,
    PagingFileConfiguration? SystemDriveConfiguration,
    bool BackupAvailable,
    bool RestartRequired);

public sealed record GpuMemoryInfo(
    string Name,
    long? DedicatedMemoryBytes);

internal sealed class VirtualMemoryBackup
{
    public DateTimeOffset CreatedAtUtc { get; set; }
    public bool AutomaticManagedPagefile { get; set; }
    public bool PagingFilesValueExisted { get; set; }
    public string[] PagingFiles { get; set; } = [];
}
