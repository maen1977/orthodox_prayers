namespace SafeWindowsCleaner.Models;

public sealed class UpdateInfo
{
    public required string TagName { get; init; }
    public required Version Version { get; init; }
    public required string ReleasePageUrl { get; init; }
    public required string ReleaseNotes { get; init; }
    public required DateTimeOffset? PublishedAt { get; init; }
    public required UpdateAsset SetupAsset { get; init; }
    public required UpdateAsset ChecksumAsset { get; init; }
}

public sealed class UpdateAsset
{
    public required string Name { get; init; }
    public required Uri DownloadUri { get; init; }
    public required long SizeBytes { get; init; }
}

public sealed record UpdateDownloadProgress(string Message, long BytesReceived, long? TotalBytes);

public sealed record PreparedUpdate(string InstallerPath, string VersionTag);
