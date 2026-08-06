using System.Text.Json;
using System.Text.Json.Serialization;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class CleanerRuleService
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = true,
        Converters = { new JsonStringEnumConverter() }
    };

    private static readonly string[] AllowedTokens =
    [
        "%TEMP%", "%LOCALAPPDATA%", "%APPDATA%", "%PROGRAMDATA%", "%WINDIR%", "%USERPROFILE%"
    ];

    public IReadOnlyList<CleanupTarget> LoadTargets()
    {
        string cleanerDirectory = Path.Combine(AppContext.BaseDirectory, "Cleaners");
        if (!Directory.Exists(cleanerDirectory))
        {
            return [];
        }

        var targets = new List<CleanupTarget>();
        foreach (string file in Directory.EnumerateFiles(cleanerDirectory, "*.json", SearchOption.TopDirectoryOnly)
                     .OrderBy(path => path, StringComparer.OrdinalIgnoreCase))
        {
            try
            {
                string json = File.ReadAllText(file);
                List<CleanerRuleDefinition>? rules = JsonSerializer.Deserialize<List<CleanerRuleDefinition>>(json, JsonOptions);
                if (rules is null)
                {
                    continue;
                }

                foreach (CleanerRuleDefinition rule in rules.Take(200))
                {
                    if (TryCreateTarget(rule, out CleanupTarget? target) && target is not null)
                    {
                        targets.Add(target);
                    }
                }
            }
            catch (Exception ex)
            {
                AppLogger.Error($"Could not load cleaner rule file: {file}", ex);
            }
        }

        return targets
            .DistinctBy(target => target.RootPath + "|" + string.Join(';', target.SearchPatterns), StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    public static bool TryCreateTarget(CleanerRuleDefinition rule, out CleanupTarget? target)
    {
        target = null;
        if (string.IsNullOrWhiteSpace(rule.Id)
            || string.IsNullOrWhiteSpace(rule.Name)
            || string.IsNullOrWhiteSpace(rule.RootPath)
            || rule.SearchPatterns is null
            || rule.SearchPatterns.Length == 0)
        {
            return false;
        }

        string? root = ResolveRoot(rule.RootPath);
        if (string.IsNullOrWhiteSpace(root) || !IsSafeRuleRoot(root, rule.RootPath))
        {
            AppLogger.Info($"Rejected unsafe cleaner rule root: {rule.Id} -> {rule.RootPath}");
            return false;
        }

        string[] patterns = rule.SearchPatterns
            .Where(IsSafePattern)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(12)
            .ToArray();
        if (patterns.Length == 0)
        {
            return false;
        }

        target = new CleanupTarget
        {
            Id = rule.Id.Trim(),
            Name = rule.Name.Trim(),
            Description = rule.Description.Trim(),
            Group = string.IsNullOrWhiteSpace(rule.Group) ? "Other" : rule.Group.Trim(),
            RootPath = root,
            SearchPatterns = patterns,
            Recursive = rule.Recursive,
            MinimumAge = TimeSpan.FromHours(Math.Clamp(rule.MinimumAgeHours, 0, 24 * 3650)),
            RequiresAdministrator = rule.RequiresAdministrator,
            EnabledByDefault = rule.EnabledByDefault,
            SafetyTier = rule.SafetyTier,
            IsSelected = rule.EnabledByDefault && rule.SafetyTier == CleanupSafetyTier.Safe
        };
        return true;
    }

    private static string? ResolveRoot(string template)
    {
        string value = template.Trim();
        var replacements = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["%TEMP%"] = Path.GetTempPath(),
            ["%LOCALAPPDATA%"] = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            ["%APPDATA%"] = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            ["%PROGRAMDATA%"] = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            ["%WINDIR%"] = Environment.GetFolderPath(Environment.SpecialFolder.Windows),
            ["%USERPROFILE%"] = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile)
        };

        string? token = AllowedTokens.FirstOrDefault(candidate => value.StartsWith(candidate, StringComparison.OrdinalIgnoreCase));
        if (token is null || string.IsNullOrWhiteSpace(replacements[token]))
        {
            return null;
        }

        string suffix = value[token.Length..].TrimStart('\\', '/');
        string root = string.IsNullOrWhiteSpace(suffix)
            ? replacements[token]
            : Path.Combine(replacements[token], suffix.Replace('/', Path.DirectorySeparatorChar));
        return Path.GetFullPath(root);
    }

    private static bool IsSafeRuleRoot(string resolvedRoot, string template)
    {
        string normalized = Path.TrimEndingDirectorySeparator(Path.GetFullPath(resolvedRoot));
        foreach (string token in AllowedTokens)
        {
            if (!template.StartsWith(token, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            string basePath = token.ToUpperInvariant() switch
            {
                "%TEMP%" => Path.GetTempPath(),
                "%LOCALAPPDATA%" => Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "%APPDATA%" => Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "%PROGRAMDATA%" => Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
                "%WINDIR%" => Environment.GetFolderPath(Environment.SpecialFolder.Windows),
                "%USERPROFILE%" => Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                _ => string.Empty
            };
            if (string.IsNullOrWhiteSpace(basePath) || !PathSafetyService.IsPathUnder(normalized, basePath))
            {
                return false;
            }

            string baseNormalized = Path.TrimEndingDirectorySeparator(Path.GetFullPath(basePath));
            if (string.Equals(normalized, baseNormalized, StringComparison.OrdinalIgnoreCase)
                && !token.Equals("%TEMP%", StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            if (token.Equals("%WINDIR%", StringComparison.OrdinalIgnoreCase))
            {
                string windowsTemp = Path.Combine(baseNormalized, "Temp");
                return PathSafetyService.IsPathUnder(normalized, windowsTemp);
            }

            if (token.Equals("%TEMP%", StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            if (token.Equals("%USERPROFILE%", StringComparison.OrdinalIgnoreCase)
                && StartsWithProtectedUserDataFolder(Path.GetRelativePath(baseNormalized, normalized)))
            {
                return false;
            }

            return ContainsDisposableSegment(Path.GetRelativePath(baseNormalized, normalized));
        }

        return false;
    }

    private static bool ContainsDisposableSegment(string relativePath)
    {
        string[] disposableNames =
        [
            "temp", "tmp", "cache", ".cache", "caches", "cache2", "cache_data", "code cache", "gpucache",
            "d3dscache", "crashdumps", "crash reports", "logs", "log", "webcache", "htmlcache",
            "media cache files", "shadercache", "shader cache"
        ];

        return relativePath.Split([Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar], StringSplitOptions.RemoveEmptyEntries)
            .Any(segment =>
            {
                string name = segment.Trim();
                return disposableNames.Contains(name, StringComparer.OrdinalIgnoreCase)
                       || name.StartsWith("webcache_", StringComparison.OrdinalIgnoreCase)
                       // Product-specific folders commonly use names such as TestCache,
                       // GPUCache, InstallerTemp, or UpdateLogs. Keep the suffix match
                       // case-sensitive so ordinary names such as Catalog or Dialog are
                       // not accidentally classified as disposable folders.
                       || name.EndsWith("Cache", StringComparison.Ordinal)
                       || name.EndsWith("Caches", StringComparison.Ordinal)
                       || name.EndsWith("Temp", StringComparison.Ordinal)
                       || name.EndsWith("Logs", StringComparison.Ordinal);
            });
    }

    private static bool StartsWithProtectedUserDataFolder(string relativePath)
    {
        string? firstSegment = relativePath
            .Split([Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar], StringSplitOptions.RemoveEmptyEntries)
            .FirstOrDefault();
        if (string.IsNullOrWhiteSpace(firstSegment))
        {
            return true;
        }

        string[] protectedFolders =
        [
            "Desktop", "Documents", "Downloads", "Favorites", "Links", "Music",
            "OneDrive", "Pictures", "Saved Games", "Searches", "Videos"
        ];

        string name = firstSegment.Trim();
        return protectedFolders.Contains(name, StringComparer.OrdinalIgnoreCase)
               || name.StartsWith("OneDrive - ", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsSafePattern(string? pattern)
    {
        if (string.IsNullOrWhiteSpace(pattern) || pattern.Length > 80)
        {
            return false;
        }

        return pattern.IndexOfAny([Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar, ':']) < 0
               && !pattern.Contains("..", StringComparison.Ordinal);
    }
}
