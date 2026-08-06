using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Services;

namespace SafeWindowsCleaner.Models;

public enum StartupItemKind
{
    Registry,
    StartupFolder,
    ScheduledTask,
    Service
}

public sealed class StartupItem : ObservableObject
{
    private bool _isSelected;

    public required string Id { get; init; }
    public required string Name { get; init; }
    public required StartupItemKind Kind { get; init; }
    public required string Category { get; init; }
    public required string Command { get; init; }
    public required string Location { get; init; }
    public string Publisher { get; init; } = "@Unknown";
    public string SignatureStatus { get; init; } = "@Unknown";
    public string ExecutablePath { get; init; } = string.Empty;
    public bool IsEnabled { get; init; }
    public bool CanToggle { get; init; } = true;
    public string ProtectionReason { get; init; } = string.Empty;

    // Internal identifiers used by StartupManagerService.
    public string SourceA { get; init; } = string.Empty;
    public string SourceB { get; init; } = string.Empty;
    public string SourceC { get; init; } = string.Empty;
    public string SourceD { get; init; } = string.Empty;

    public string CategoryText => LocalizationService.Translate(Category);
    public string PublisherText => Publisher.StartsWith("@", StringComparison.Ordinal)
        ? LocalizationService.T(Publisher)
        : Publisher;
    public string SignatureStatusText => LocalizationService.Translate(SignatureStatus);
    public string StateText => LocalizationService.T(IsEnabled ? "@Enabled" : "@Disabled");
    public string SafetyText => LocalizationService.T(CanToggle ? "@CanChange" : "@Protected");
    public string DetailsText => string.IsNullOrWhiteSpace(ProtectionReason)
        ? SafetyText
        : LocalizationService.Translate(ProtectionReason);

    public bool HasMissingExecutable => !string.IsNullOrWhiteSpace(ExecutablePath) && !File.Exists(ExecutablePath);

    public string RecommendationText => LocalizationService.T(HasMissingExecutable
        ? "@StartupMissingExecutable"
        : !CanToggle ? "@StartupProtectedItem"
        : "@StartupValidItem");

    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            if (!CanToggle && value)
            {
                value = false;
            }

            SetProperty(ref _isSelected, value);
        }
    }
}

public sealed class StartupOperationResult
{
    public int SucceededItems { get; set; }
    public int SkippedItems { get; set; }
    public int FailedItems { get; set; }
}
