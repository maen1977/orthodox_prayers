using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class CleanupService
{
    private const int MaximumTrackedFilesPerTarget = 30_000;
    private readonly CleanerRuleService _ruleService = new();

    public IReadOnlyList<CleanupTarget> CreateDefaultTargets()
    {
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var targets = _ruleService.LoadTargets().ToList();

        AddChromiumCacheTargets(targets, Path.Combine(localAppData, "Google", "Chrome", "User Data"), "Google Chrome");
        AddChromiumCacheTargets(targets, Path.Combine(localAppData, "Microsoft", "Edge", "User Data"), "Microsoft Edge");
        AddChromiumCacheTargets(targets, Path.Combine(localAppData, "BraveSoftware", "Brave-Browser", "User Data"), "Brave");
        AddChromiumCacheTargets(targets, Path.Combine(localAppData, "Vivaldi", "User Data"), "Vivaldi");
        AddSingleChromiumProfileCacheTargets(targets, Path.Combine(localAppData, "Opera Software", "Opera Stable"), "Opera");
        AddSingleChromiumProfileCacheTargets(targets, Path.Combine(localAppData, "Opera Software", "Opera GX Stable"), "Opera GX");
        AddFirefoxCacheTargets(targets, Path.Combine(localAppData, "Mozilla", "Firefox", "Profiles"));

        return targets
            .Where(target => !string.IsNullOrWhiteSpace(target.RootPath))
            .DistinctBy(target => target.RootPath + "|" + string.Join(';', target.SearchPatterns), StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private static void AddChromiumCacheTargets(List<CleanupTarget> targets, string userDataRoot, string browserName)
    {
        if (!Directory.Exists(userDataRoot))
        {
            return;
        }

        IEnumerable<string> profiles;
        try
        {
            profiles = Directory.EnumerateDirectories(userDataRoot, "*", SearchOption.TopDirectoryOnly)
                .Where(path =>
                {
                    string name = Path.GetFileName(path);
                    return name.Equals("Default", StringComparison.OrdinalIgnoreCase)
                           || name.StartsWith("Profile ", StringComparison.OrdinalIgnoreCase);
                })
                .Take(12)
                .ToList();
        }
        catch
        {
            return;
        }

        foreach (string profile in profiles)
        {
            string profileName = Path.GetFileName(profile);
            string[] cacheFolders =
            [
                Path.Combine(profile, "Cache", "Cache_Data"),
                Path.Combine(profile, "Code Cache"),
                Path.Combine(profile, "GPUCache")
            ];

            foreach (string cacheFolder in cacheFolders)
            {
                targets.Add(new CleanupTarget
                {
                    Id = $"browser-{browserName}-{profileName}-{Path.GetFileName(cacheFolder)}".Replace(' ', '-').ToLowerInvariant(),
                    Name = $"كاش {browserName} — {profileName}",
                    Description = "كاش تصفح فقط؛ لا يحذف كلمات المرور أو السجل أو ملفات تعريف الارتباط.",
                    Group = "Browser",
                    SafetyTier = CleanupSafetyTier.Safe,
                    EnabledByDefault = true,
                    RootPath = cacheFolder,
                    SearchPatterns = ["*"],
                    Recursive = true,
                    MinimumAge = TimeSpan.FromDays(2)
                });
            }
        }
    }

    private static void AddSingleChromiumProfileCacheTargets(List<CleanupTarget> targets, string profileRoot, string browserName)
    {
        if (!Directory.Exists(profileRoot))
        {
            return;
        }

        string[] cacheFolders =
        [
            Path.Combine(profileRoot, "Cache", "Cache_Data"),
            Path.Combine(profileRoot, "Code Cache"),
            Path.Combine(profileRoot, "GPUCache")
        ];
        foreach (string cacheFolder in cacheFolders)
        {
            targets.Add(new CleanupTarget
            {
                Id = $"browser-{browserName}-{Path.GetFileName(cacheFolder)}".Replace(' ', '-').ToLowerInvariant(),
                Name = $"كاش {browserName}",
                Description = "كاش تصفح فقط؛ لا يحذف كلمات المرور أو السجل أو ملفات تعريف الارتباط.",
                Group = "Browser",
                SafetyTier = CleanupSafetyTier.Safe,
                EnabledByDefault = true,
                RootPath = cacheFolder,
                SearchPatterns = ["*"],
                Recursive = true,
                MinimumAge = TimeSpan.FromDays(2)
            });
        }
    }

    private static void AddFirefoxCacheTargets(List<CleanupTarget> targets, string profilesRoot)
    {
        if (!Directory.Exists(profilesRoot))
        {
            return;
        }

        IEnumerable<string> profiles;
        try
        {
            profiles = Directory.EnumerateDirectories(profilesRoot, "*", SearchOption.TopDirectoryOnly)
                .Take(12)
                .ToList();
        }
        catch
        {
            return;
        }

        foreach (string profile in profiles)
        {
            targets.Add(new CleanupTarget
            {
                Id = $"browser-firefox-{Path.GetFileName(profile)}".ToLowerInvariant(),
                Name = $"كاش Mozilla Firefox — {Path.GetFileName(profile)}",
                Description = "مجلد cache2 فقط؛ لا يحذف كلمات المرور أو السجل أو ملفات تعريف الارتباط.",
                Group = "Browser",
                SafetyTier = CleanupSafetyTier.Safe,
                EnabledByDefault = true,
                RootPath = Path.Combine(profile, "cache2"),
                SearchPatterns = ["*"],
                Recursive = true,
                MinimumAge = TimeSpan.FromDays(2)
            });
        }
    }

    public Task<List<CleanupTarget>> ScanAsync(
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        return Task.Run(() =>
        {
            var results = new List<CleanupTarget>();

            foreach (CleanupTarget target in CreateDefaultTargets())
            {
                cancellationToken.ThrowIfCancellationRequested();
                progress?.Report($"فحص: {target.Name}");
                ScanTarget(target, cancellationToken);
                results.Add(target);
            }

            return results;
        }, cancellationToken);
    }

    public Task<CleanupResult> CleanAsync(
        IEnumerable<CleanupTarget> targets,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        return Task.Run(() =>
        {
            long freedBytes = 0;
            int deletedFiles = 0;
            int failedFiles = 0;
            int skippedFiles = 0;
            bool requiresElevation = false;

            foreach (CleanupTarget target in targets.Where(t => t.IsSelected))
            {
                cancellationToken.ThrowIfCancellationRequested();
                progress?.Report($"تنظيف: {target.Name}");

                foreach (string file in target.Files)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    try
                    {
                        if (!PathSafetyService.IsPathUnder(file, target.RootPath))
                        {
                            skippedFiles++;
                            AppLogger.Info($"Skipped cleanup item outside its rule root: {file}");
                            continue;
                        }

                        if (!File.Exists(file))
                        {
                            continue;
                        }

                        long length = 0;
                        try
                        {
                            length = new FileInfo(file).Length;
                        }
                        catch
                        {
                            // Ignore size read failures.
                        }

                        File.SetAttributes(file, FileAttributes.Normal);
                        File.Delete(file);
                        freedBytes += length;
                        deletedFiles++;
                    }
                    catch (UnauthorizedAccessException ex)
                    {
                        failedFiles++;
                        requiresElevation |= target.RequiresAdministrator;
                        AppLogger.Error($"Could not delete protected file: {file}", ex);
                    }
                    catch (Exception ex)
                    {
                        failedFiles++;
                        AppLogger.Error($"Could not delete file: {file}", ex);
                    }
                }

                TryRemoveEmptyDirectories(target.RootPath);
            }

            return new CleanupResult(freedBytes, deletedFiles, failedFiles, skippedFiles, requiresElevation);
        }, cancellationToken);
    }

    private static void ScanTarget(CleanupTarget target, CancellationToken cancellationToken)
    {
        target.Files.Clear();
        target.SizeBytes = 0;
        target.FileCount = 0;
        target.ScanTruncated = false;

        if (string.IsNullOrWhiteSpace(target.RootPath) || !Directory.Exists(target.RootPath))
        {
            return;
        }

        var uniqueFiles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        DateTime newestAllowed = DateTime.UtcNow - target.MinimumAge;

        var options = new EnumerationOptions
        {
            RecurseSubdirectories = target.Recursive,
            IgnoreInaccessible = true,
            ReturnSpecialDirectories = false,
            AttributesToSkip = FileAttributes.ReparsePoint
        };

        foreach (string pattern in target.SearchPatterns)
        {
            IEnumerable<string> files;
            try
            {
                files = Directory.EnumerateFiles(target.RootPath, pattern, options);
            }
            catch (Exception ex)
            {
                AppLogger.Error($"Could not enumerate cleanup target: {target.RootPath}", ex);
                continue;
            }

            try
            {
                foreach (string file in files)
                {
                    cancellationToken.ThrowIfCancellationRequested();

                    if (!uniqueFiles.Add(file))
                    {
                        continue;
                    }

                    if (uniqueFiles.Count > MaximumTrackedFilesPerTarget)
                    {
                        target.ScanTruncated = true;
                        break;
                    }

                    try
                    {
                        var info = new FileInfo(file);
                        if (target.MinimumAge > TimeSpan.Zero && info.LastWriteTimeUtc > newestAllowed)
                        {
                            continue;
                        }

                        target.Files.Add(file);
                        target.SizeBytes += info.Length;
                    }
                    catch (Exception ex)
                    {
                        AppLogger.Error($"Could not inspect file: {file}", ex);
                    }
                }
            }
            catch (Exception ex)
            {
                AppLogger.Error($"Enumeration interrupted for target: {target.RootPath}", ex);
            }

            if (target.ScanTruncated)
            {
                break;
            }
        }

        target.FileCount = target.Files.Count;
    }

    private static void TryRemoveEmptyDirectories(string rootPath)
    {
        if (!Directory.Exists(rootPath))
        {
            return;
        }

        try
        {
            var directories = Directory.EnumerateDirectories(rootPath, "*", new EnumerationOptions
            {
                RecurseSubdirectories = true,
                IgnoreInaccessible = true,
                AttributesToSkip = FileAttributes.ReparsePoint
            })
            .OrderByDescending(path => path.Length)
            .ToList();

            foreach (string directory in directories)
            {
                try
                {
                    if (!Directory.EnumerateFileSystemEntries(directory).Any())
                    {
                        Directory.Delete(directory, false);
                    }
                }
                catch
                {
                    // Empty directory cleanup is best-effort only.
                }
            }
        }
        catch
        {
            // Best-effort only.
        }
    }
}

public sealed record CleanupResult(long FreedBytes, int DeletedFiles, int FailedFiles, int SkippedFiles = 0, bool RequiresElevation = false);
