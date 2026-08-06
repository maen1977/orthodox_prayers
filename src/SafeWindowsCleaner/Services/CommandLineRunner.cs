using System.Text.Json;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed record CommandLineRunResult(string ReportPath, bool Succeeded);

public static class CommandLineRunner
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    public static bool IsCommandLineMode(IEnumerable<string> arguments)
        => arguments.Any(argument => argument.Equals("--scan", StringComparison.OrdinalIgnoreCase)
                                     || argument.Equals("--clean", StringComparison.OrdinalIgnoreCase)
                                     || argument.Equals("--list-apps", StringComparison.OrdinalIgnoreCase)
                                     || argument.Equals("--scheduled-clean", StringComparison.OrdinalIgnoreCase)
                                     || argument.Equals("--restore-virtual-memory", StringComparison.OrdinalIgnoreCase)
                                     || argument.StartsWith("--analyze-disk", StringComparison.OrdinalIgnoreCase));

    public static async Task<CommandLineRunResult> RunAsync(IReadOnlyList<string> arguments, AppSettings settings, CancellationToken cancellationToken = default)
    {
        bool scheduledRun = arguments.Any(argument => argument.Equals("--scheduled-clean", StringComparison.OrdinalIgnoreCase));
        string profileId = ReadValue(arguments, "--profile") ?? settings.DefaultCleanupProfile;
        if (scheduledRun)
        {
            profileId = CleanupProfileService.NormalizeForAutomatic(profileId);
        }
        string? requestedOutput = ReadValue(arguments, "--output");
        string outputPath = ResolveOutputPath(requestedOutput);
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);

        var report = new Dictionary<string, object?>
        {
            ["application"] = "Safe Windows Cleaner Lite",
            ["version"] = BuildInfo.DisplayVersion,
            ["startedAtUtc"] = DateTimeOffset.UtcNow,
            ["profile"] = CleanupProfileService.Normalize(profileId),
            ["isAdministrator"] = ElevationService.IsAdministrator
        };

        bool succeeded = false;
        try
        {
            if (arguments.Any(argument => argument.Equals("--restore-virtual-memory", StringComparison.OrdinalIgnoreCase)))
            {
                bool restored = await new VirtualMemoryService().RestorePreviousIfAvailableAsync(cancellationToken);
                report["operation"] = "restore-virtual-memory";
                report["restored"] = restored;
                report["restartRequired"] = restored;
            }
            else if (arguments.Any(argument => argument.Equals("--list-apps", StringComparison.OrdinalIgnoreCase)))
            {
                List<InstalledApp> apps = await new InstalledAppsService().GetInstalledAppsAsync(cancellationToken);
                report["operation"] = "list-apps";
                report["applications"] = apps.Select(app => new
                {
                    app.DisplayName,
                    app.Publisher,
                    app.Version,
                    app.InstallLocation,
                    app.EstimatedSizeBytes
                }).ToList();
            }
            else if (arguments.Any(argument => argument.StartsWith("--analyze-disk", StringComparison.OrdinalIgnoreCase)))
            {
                string path = ReadValue(arguments, "--analyze-disk")
                              ?? Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
                var options = new DiskAnalyzerOptions
                {
                    LargestFileLimit = settings.LowResourceMode ? Math.Min(settings.LargestFilesLimit, 200) : settings.LargestFilesLimit,
                    MinimumDuplicateSizeBytes = checked((long)settings.MinimumDuplicateSizeMb * 1024L * 1024L),
                    CalculateDuplicates = false,
                };
                DiskAnalysisResult result = await new DiskAnalyzerService().AnalyzeAsync(path, options, progress: null, cancellationToken: cancellationToken);
                report["operation"] = "analyze-disk";
                report["path"] = path;
                report["totalFiles"] = result.FileCount;
                report["totalBytes"] = result.TotalBytes;
                report["largestFiles"] = result.LargestFiles.Take(200).Select(item => new { item.Path, item.SizeBytes }).ToList();
            }
            else
            {
                var cleanupService = new CleanupService();
                List<CleanupTarget> targets = await cleanupService.ScanAsync(progress: null, cancellationToken: cancellationToken);
                var profileService = new CleanupProfileService();
                profileService.Apply(profileId, targets);
                foreach (CleanupTarget target in targets.Where(target => target.RequiresAdministrator && !ElevationService.IsAdministrator))
                {
                    target.IsSelected = false;
                }

                report["operation"] = arguments.Any(argument => argument.Equals("--clean", StringComparison.OrdinalIgnoreCase)) || scheduledRun
                    ? "clean"
                    : "scan";
                report["targets"] = targets.Select(target => new
                {
                    target.Id,
                    target.Name,
                    target.Group,
                    safety = target.SafetyTier.ToString(),
                    target.IsSelected,
                    target.FileCount,
                    target.SizeBytes,
                    target.ScanTruncated,
                    target.RequiresAdministrator
                }).ToList();

                if (string.Equals(report["operation"]?.ToString(), "clean", StringComparison.OrdinalIgnoreCase))
                {
                    CleanupResult result = await cleanupService.CleanAsync(targets, progress: null, cancellationToken: cancellationToken);
                    report["result"] = new
                    {
                        result.DeletedFiles,
                        result.FailedFiles,
                        result.SkippedFiles,
                        result.FreedBytes,
                        result.RequiresElevation
                    };
                }
            }

            report["status"] = "success";
            succeeded = true;
        }
        catch (Exception ex)
        {
            report["status"] = "failed";
            report["error"] = ex.Message;
            AppLogger.Error("Command-line operation failed.", ex);
        }

        report["completedAtUtc"] = DateTimeOffset.UtcNow;
        await File.WriteAllTextAsync(outputPath, JsonSerializer.Serialize(report, JsonOptions), cancellationToken);
        return new CommandLineRunResult(outputPath, succeeded);
    }

    private static string ResolveOutputPath(string? requested)
    {
        if (!string.IsNullOrWhiteSpace(requested))
        {
            string expanded = Environment.ExpandEnvironmentVariables(requested.Trim().Trim('"'));
            return Path.GetFullPath(expanded);
        }

        string directory = Path.Combine(SettingsService.DataDirectory, "CommandLineReports");
        return Path.Combine(directory, $"run-{DateTime.UtcNow:yyyyMMdd-HHmmss}.json");
    }

    private static string? ReadValue(IEnumerable<string> arguments, string name)
    {
        foreach (string argument in arguments)
        {
            if (argument.StartsWith(name + "=", StringComparison.OrdinalIgnoreCase))
            {
                return argument[(name.Length + 1)..].Trim().Trim('"');
            }
        }

        return null;
    }
}
