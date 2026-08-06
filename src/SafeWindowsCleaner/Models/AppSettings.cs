namespace SafeWindowsCleaner.Models;

public sealed class AppSettings
{
    public int SettingsSchemaVersion { get; set; } = 5;
    public string LanguageCode { get; set; } = string.Empty;
    public string Theme { get; set; } = "Light";
    public bool CheckForUpdatesOnStartup { get; set; }
    public int QuarantineRetentionDays { get; set; } = 30;
    public int MinimumDuplicateSizeMb { get; set; } = 50;
    public int LargestFilesLimit { get; set; } = 200;
    public bool CalculateDuplicatesDuringDiskScan { get; set; }
    public bool LowResourceMode { get; set; } = true;
    public bool ConfirmDangerousOperations { get; set; } = true;
    public bool PreviewOnlyMode { get; set; }
    public bool CreateRestorePointBeforeDeepChanges { get; set; } = true;
    public string DefaultCleanupProfile { get; set; } = "safe";
    public bool EnableTemporaryMemoryRelease { get; set; }
    public bool RequireSignedUpdates { get; set; } = true;
    public string TrustedPublisherThumbprint { get; set; } = string.Empty;
    public bool ScheduledCleanupEnabled { get; set; }
    public string ScheduledCleanupDay { get; set; } = "Sunday";
    public int ScheduledCleanupHour { get; set; } = 10;
    public bool SimpleNavigation { get; set; } = true;
    public string GitHubRepository { get; set; } = string.Empty;

    public AppSettings Clone() => new()
    {
        SettingsSchemaVersion = SettingsSchemaVersion,
        LanguageCode = LanguageCode,
        Theme = Theme,
        CheckForUpdatesOnStartup = CheckForUpdatesOnStartup,
        QuarantineRetentionDays = QuarantineRetentionDays,
        MinimumDuplicateSizeMb = MinimumDuplicateSizeMb,
        LargestFilesLimit = LargestFilesLimit,
        CalculateDuplicatesDuringDiskScan = CalculateDuplicatesDuringDiskScan,
        LowResourceMode = LowResourceMode,
        ConfirmDangerousOperations = ConfirmDangerousOperations,
        PreviewOnlyMode = PreviewOnlyMode,
        CreateRestorePointBeforeDeepChanges = CreateRestorePointBeforeDeepChanges,
        DefaultCleanupProfile = DefaultCleanupProfile,
        EnableTemporaryMemoryRelease = EnableTemporaryMemoryRelease,
        RequireSignedUpdates = RequireSignedUpdates,
        TrustedPublisherThumbprint = TrustedPublisherThumbprint,
        ScheduledCleanupEnabled = ScheduledCleanupEnabled,
        ScheduledCleanupDay = ScheduledCleanupDay,
        ScheduledCleanupHour = ScheduledCleanupHour,
        SimpleNavigation = SimpleNavigation,
        GitHubRepository = GitHubRepository
    };
}
