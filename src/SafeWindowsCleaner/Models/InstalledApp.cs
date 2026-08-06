using SafeWindowsCleaner.Helpers;

namespace SafeWindowsCleaner.Models;

public sealed class InstalledApp
{
    public required string DisplayName { get; init; }
    public string Publisher { get; init; } = "";
    public string Version { get; init; } = "";
    public string InstallLocation { get; init; } = "";
    public string UninstallString { get; init; } = "";
    public string QuietUninstallString { get; init; } = "";
    public long EstimatedSizeBytes { get; init; }

    // Stable registry identity used to verify that the official uninstaller completed
    // and to remove only this application's stale uninstall record.
    public string RegistryHiveName { get; init; } = "";
    public string RegistryViewName { get; init; } = "";
    public string RegistryKeyPath { get; init; } = "";
    public string RegistrySubKeyName { get; init; } = "";
    public string ProductCode { get; init; } = "";

    public string SizeText => EstimatedSizeBytes > 0 ? SizeFormatter.Format(EstimatedSizeBytes) : "—";
}
