namespace SafeWindowsCleaner.Models;

public sealed class OperationPreview
{
    public string Operation { get; init; } = string.Empty;
    public string Description { get; init; } = string.Empty;
    public DateTimeOffset CreatedAtUtc { get; init; } = DateTimeOffset.UtcNow;
    public int ItemCount { get; init; }
    public long EstimatedBytes { get; init; }
    public bool RequiresAdministrator { get; init; }
    public string RiskLevel { get; init; } = "@RiskLow";
    public List<OperationPreviewItem> Items { get; init; } = [];
}

public sealed class OperationPreviewItem
{
    public string Name { get; init; } = string.Empty;
    public string Location { get; init; } = string.Empty;
    public string Action { get; init; } = string.Empty;
    public string Safety { get; init; } = string.Empty;
    public long SizeBytes { get; init; }
}

public sealed record PreviewReportResult(string JsonPath, string HtmlPath);
