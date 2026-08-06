namespace SafeWindowsCleaner.Models;

public sealed class MonitoredUninstallCleanupResult
{
    public int DirectoriesQuarantined { get; set; }
    public int FilesQuarantined { get; set; }
    public long BytesQuarantined { get; set; }
    public int RegistryItemsRemoved { get; set; }
    public int ServicesRemoved { get; set; }
    public int ScheduledTasksRemoved { get; set; }
    public int FailedItems { get; set; }
    public int SkippedItems { get; set; }
    public List<string> Actions { get; } = [];
    public List<string> Warnings { get; } = [];

    public int TotalRemovedItems => DirectoriesQuarantined + FilesQuarantined + RegistryItemsRemoved + ServicesRemoved + ScheduledTasksRemoved;
}
