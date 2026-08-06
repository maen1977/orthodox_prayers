using System.Diagnostics;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class ProcessService
{
    private const long RecommendationThresholdBytes = 90L * 1024L * 1024L;

    private static readonly HashSet<string> ProtectedProcessNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "Idle", "System", "Registry", "Secure System", "Memory Compression",
        "smss", "csrss", "wininit", "services", "lsass", "svchost", "winlogon",
        "fontdrvhost", "dwm", "sihost", "taskhostw", "explorer", "audiodg",
        "MsMpEng", "SecurityHealthService", "SearchHost", "StartMenuExperienceHost",
        "ShellExperienceHost", "RuntimeBroker", "ApplicationFrameHost", "ctfmon"
    };

    private static readonly string[] OptionalProcessHints =
    [
        "teams", "discord", "spotify", "steam", "epicgameslauncher", "onedrive",
        "dropbox", "googledrivefs", "adobe", "creative cloud", "skype", "zoom",
        "telegram", "whatsapp", "utorrent", "qbittorrent",
        "launcher", "updater", "update", "helper", "tray"
    ];

    public Task<List<ProcessInfoItem>> GetProcessesAsync(CancellationToken cancellationToken = default)
    {
        return Task.Run(() =>
        {
            var items = new List<ProcessInfoItem>();
            using Process current = Process.GetCurrentProcess();
            int currentSessionId = current.SessionId;
            string windowsRoot = Environment.GetFolderPath(Environment.SpecialFolder.Windows);

            foreach (Process process in Process.GetProcesses())
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    string name = process.ProcessName;
                    string executablePath = TryGetExecutablePath(process);
                    string windowTitle = TryGetWindowTitle(process);
                    DateTime startTimeUtc = TryGetStartTimeUtc(process);
                    bool sameSession = TryGetSessionId(process) == currentSessionId;
                    bool systemPath = !string.IsNullOrWhiteSpace(executablePath)
                                      && !string.IsNullOrWhiteSpace(windowsRoot)
                                      && PathSafetyService.IsPathUnder(executablePath, windowsRoot);
                    bool protectedProcess = process.Id <= 4
                                            || process.Id == Environment.ProcessId
                                            || ProtectedProcessNames.Contains(name)
                                            || systemPath
                                            || !sameSession;
                    bool canClose = !protectedProcess;
                    long workingSet = process.WorkingSet64;
                    bool recommended = canClose
                                       && workingSet >= RecommendationThresholdBytes
                                       && (windowTitle.Length > 0 || ContainsOptionalHint(name, executablePath));

                    items.Add(new ProcessInfoItem
                    {
                        Name = name,
                        ProcessId = process.Id,
                        WorkingSetBytes = workingSet,
                        PrivateMemoryBytes = process.PrivateMemorySize64,
                        ExecutablePath = executablePath,
                        WindowTitle = windowTitle,
                        StartTimeUtc = startTimeUtc,
                        IsCurrentUserSession = sameSession,
                        IsSystemProtected = protectedProcess,
                        CanClose = canClose,
                        IsRecommended = recommended,
                        RecommendationText = BuildRecommendationText(protectedProcess, recommended, windowTitle, workingSet)
                    });
                }
                catch
                {
                    // Some protected processes cannot be inspected.
                }
                finally
                {
                    process.Dispose();
                }
            }

            return items
                .OrderByDescending(item => item.IsRecommended)
                .ThenByDescending(item => item.WorkingSetBytes)
                .ToList();
        }, cancellationToken);
    }

    public Task EndProcessAsync(int processId, CancellationToken cancellationToken = default)
        => EndProcessesAsync([processId], cancellationToken);

    public Task EndProcessesAsync(IEnumerable<int> processIds, CancellationToken cancellationToken = default)
    {
        int[] ids = processIds.Distinct().ToArray();
        return Task.Run(() =>
        {
            using Process current = Process.GetCurrentProcess();
            int currentSessionId = current.SessionId;
            string windowsRoot = Environment.GetFolderPath(Environment.SpecialFolder.Windows);

            foreach (int processId in ids)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (processId == Environment.ProcessId)
                {
                    continue;
                }

                using Process process = Process.GetProcessById(processId);
                if (!IsSafeUserProcess(process, currentSessionId, windowsRoot))
                {
                    continue;
                }

                process.Kill(entireProcessTree: true);
                process.WaitForExit(5000);
            }
        }, cancellationToken);
    }

    public Task<ProcessOperationResult> EndSelectedAsync(
        IEnumerable<ProcessInfoItem> items,
        CancellationToken cancellationToken = default)
    {
        ProcessInfoItem[] selected = items.DistinctBy(item => item.ProcessId).ToArray();
        return Task.Run(() =>
        {
            var result = new ProcessOperationResult();
            using Process current = Process.GetCurrentProcess();
            int currentSessionId = current.SessionId;
            string windowsRoot = Environment.GetFolderPath(Environment.SpecialFolder.Windows);

            foreach (ProcessInfoItem item in selected)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (!item.CanClose || item.ProcessId == Environment.ProcessId)
                {
                    result.SkippedItems++;
                    continue;
                }

                try
                {
                    using Process process = Process.GetProcessById(item.ProcessId);
                    if (!ProcessMatchesSafeSnapshot(process, item, currentSessionId, windowsRoot))
                    {
                        result.SkippedItems++;
                        continue;
                    }

                    long before = Math.Max(0, process.WorkingSet64);
                    process.Kill(entireProcessTree: true);
                    if (!process.WaitForExit(5000))
                    {
                        result.FailedItems++;
                        continue;
                    }
                    result.SucceededItems++;
                    result.EstimatedBytesAffected += before;
                    result.Actions.Add(new ProcessMemoryAction(
                        item.Name,
                        item.ProcessId,
                        "Closed",
                        before,
                        0));
                }
                catch (ArgumentException)
                {
                    // The process already exited or the PID no longer exists. Do not claim memory savings.
                    result.SkippedItems++;
                }
                catch (Exception ex)
                {
                    result.FailedItems++;
                    AppLogger.Error($"Could not close process {item.Name} ({item.ProcessId}).", ex);
                }
            }

            return result;
        }, cancellationToken);
    }

    private static bool ProcessMatchesSafeSnapshot(
        Process process,
        ProcessInfoItem snapshot,
        int currentSessionId,
        string windowsRoot)
    {
        string currentName;
        try
        {
            currentName = process.ProcessName;
        }
        catch
        {
            return false;
        }

        if (!string.Equals(currentName, snapshot.Name, StringComparison.OrdinalIgnoreCase)
            || !IsSafeUserProcess(process, currentSessionId, windowsRoot))
        {
            return false;
        }

        string currentPath = TryGetExecutablePath(process);
        return string.IsNullOrWhiteSpace(snapshot.ExecutablePath)
               || string.Equals(currentPath, snapshot.ExecutablePath, StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsSafeUserProcess(Process process, int currentSessionId, string windowsRoot)
    {
        try
        {
            if (process.Id <= 4
                || process.Id == Environment.ProcessId
                || process.SessionId != currentSessionId
                || ProtectedProcessNames.Contains(process.ProcessName))
            {
                return false;
            }

            string executablePath = TryGetExecutablePath(process);
            if (string.IsNullOrWhiteSpace(executablePath))
            {
                return false;
            }

            return string.IsNullOrWhiteSpace(windowsRoot)
                   || !PathSafetyService.IsPathUnder(executablePath, windowsRoot);
        }
        catch
        {
            return false;
        }
    }

    private static bool ContainsOptionalHint(string name, string path)
    {
        string value = $"{name} {path}";
        return OptionalProcessHints.Any(hint => value.Contains(hint, StringComparison.OrdinalIgnoreCase));
    }

    private static string BuildRecommendationText(bool protectedProcess, bool recommended, string windowTitle, long workingSet)
    {
        if (protectedProcess)
        {
            return "@ProcessProtectedRecommendation";
        }

        if (recommended)
        {
            return windowTitle.Length > 0
                ? "@ProcessVisibleHighMemory"
                : "@ProcessBackgroundHighMemory";
        }

        if (workingSet < 32L * 1024L * 1024L)
        {
            return "@ProcessLowMemory";
        }

        return "@ProcessReviewBeforeClose";
    }

    private static string TryGetExecutablePath(Process process)
    {
        try
        {
            return process.MainModule?.FileName ?? string.Empty;
        }
        catch
        {
            return string.Empty;
        }
    }

    private static string TryGetWindowTitle(Process process)
    {
        try
        {
            return process.MainWindowTitle?.Trim() ?? string.Empty;
        }
        catch
        {
            return string.Empty;
        }
    }

    private static DateTime TryGetStartTimeUtc(Process process)
    {
        try
        {
            return process.StartTime.ToUniversalTime();
        }
        catch
        {
            return default;
        }
    }

    private static int TryGetSessionId(Process process)
    {
        try
        {
            return process.SessionId;
        }
        catch
        {
            return -1;
        }
    }
}
