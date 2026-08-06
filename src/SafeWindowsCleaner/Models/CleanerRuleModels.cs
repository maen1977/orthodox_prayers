using SafeWindowsCleaner.Helpers;

namespace SafeWindowsCleaner.Models;

public enum CleanupSafetyTier
{
    Safe,
    Review,
    Advanced
}

public sealed class CleanerRuleDefinition
{
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public string Group { get; set; } = "Other";
    public string RootPath { get; set; } = string.Empty;
    public string[] SearchPatterns { get; set; } = ["*"];
    public bool Recursive { get; set; } = true;
    public double MinimumAgeHours { get; set; } = 24;
    public bool RequiresAdministrator { get; set; }
    public bool EnabledByDefault { get; set; } = true;
    public CleanupSafetyTier SafetyTier { get; set; } = CleanupSafetyTier.Safe;
}

public sealed class CleanupProfileOption
{
    public required string Id { get; init; }
    public required string Name { get; init; }
    public required string Description { get; init; }
    public override string ToString() => Name;
}

public sealed class CleanupSessionSummary
{
    public DateTimeOffset StartedAtUtc { get; init; }
    public DateTimeOffset CompletedAtUtc { get; init; }
    public string ProfileId { get; init; } = "safe";
    public int ScannedTargets { get; init; }
    public int DeletedFiles { get; init; }
    public int FailedFiles { get; init; }
    public int SkippedFiles { get; init; }
    public long FreedBytes { get; init; }
    public bool RequiredElevation { get; init; }
    public string FreedText => SizeFormatter.Format(FreedBytes);
}
