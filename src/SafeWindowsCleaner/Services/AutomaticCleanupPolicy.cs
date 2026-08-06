using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public static class AutomaticCleanupPolicy
{
    public static bool ShouldQuarantineOrphan(LeftoverItem item, DateTime utcNow)
    {
        if (!item.IsQuarantinable || item.ConfidenceScore < 90)
        {
            return false;
        }

        if (item.LastModifiedUtc == default)
        {
            return false;
        }

        return utcNow - item.LastModifiedUtc >= TimeSpan.FromDays(60);
    }

    public static bool ShouldDisableBrokenStartup(StartupItem item)
    {
        if (!item.IsEnabled || !item.CanToggle || !item.HasMissingExecutable)
        {
            return false;
        }

        // Services may use system-hosted commands that do not map cleanly to one executable.
        return item.Kind != StartupItemKind.Service;
    }
}
