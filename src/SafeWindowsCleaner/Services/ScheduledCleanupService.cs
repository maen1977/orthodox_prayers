using System.Diagnostics;

namespace SafeWindowsCleaner.Services;

public sealed class ScheduledCleanupService
{
    public const string TaskName = "SafeWindowsCleaner Lite Weekly Cleanup";

    public async Task ConfigureAsync(bool enabled, string day, int hour, string profileId, CancellationToken cancellationToken = default)
    {
        if (!OperatingSystem.IsWindows())
        {
            return;
        }

        if (!enabled)
        {
            await RunSchtasksAsync(["/Delete", "/TN", TaskName, "/F"], allowMissing: true, cancellationToken: cancellationToken);
            return;
        }

        string executable = Environment.ProcessPath
                            ?? throw new InvalidOperationException("The application executable path is unavailable.");
        string normalizedDay = SettingsService.NormalizeScheduleDay(day).Substring(0, 3).ToUpperInvariant();
        string time = $"{Math.Clamp(hour, 0, 23):00}:00";
        string command = $"\"{executable}\" --scheduled-clean --profile={CleanupProfileService.NormalizeForAutomatic(profileId)} --report";

        await RunSchtasksAsync(
        [
            "/Create",
            "/TN", TaskName,
            "/TR", command,
            "/SC", "WEEKLY",
            "/D", normalizedDay,
            "/ST", time,
            "/RL", "HIGHEST",
            "/F"
        ], allowMissing: false, cancellationToken: cancellationToken);
    }

    public async Task<bool> ExistsAsync(CancellationToken cancellationToken = default)
    {
        if (!OperatingSystem.IsWindows())
        {
            return false;
        }

        try
        {
            int exitCode = await RunSchtasksAsync(["/Query", "/TN", TaskName], allowMissing: true, cancellationToken: cancellationToken);
            return exitCode == 0;
        }
        catch
        {
            return false;
        }
    }

    private static async Task<int> RunSchtasksAsync(
        IReadOnlyList<string> arguments,
        bool allowMissing,
        CancellationToken cancellationToken)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = "schtasks.exe",
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true
        };
        foreach (string argument in arguments)
        {
            startInfo.ArgumentList.Add(argument);
        }

        using var process = new Process { StartInfo = startInfo };
        process.Start();
        string output = await process.StandardOutput.ReadToEndAsync(cancellationToken);
        string error = await process.StandardError.ReadToEndAsync(cancellationToken);
        await process.WaitForExitAsync(cancellationToken);
        if (process.ExitCode != 0 && !allowMissing)
        {
            throw new InvalidOperationException(string.IsNullOrWhiteSpace(error) ? output : error);
        }

        return process.ExitCode;
    }
}
