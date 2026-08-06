using System.Diagnostics;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class LeftoverService
{
    private const int MaximumSizeFiles = 15_000;

    private static readonly HashSet<string> BlockedDirectoryNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "Microsoft", "Windows", "Packages", "Programs", "Common Files", "Temp",
        "System32", "WindowsApps", "ModifiableWindowsApps", "Users", "ProgramData",
        "Application Data", "Local Settings", "Start Menu", "SendTo", "Templates"
    };

    private static readonly HashSet<string> IgnoredTokens = new(StringComparer.OrdinalIgnoreCase)
    {
        "app", "apps", "application", "applications", "desktop", "client", "setup",
        "installer", "install", "software", "program", "programs", "tool", "tools",
        "service", "services", "update", "updater", "launcher", "windows", "microsoft",
        "company", "corporation", "corp", "inc", "limited", "ltd", "llc", "group",
        "برنامج", "تطبيق", "شركة"
    };

    private static readonly HashSet<string> ConfigurationExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".config", ".json", ".xml", ".ini", ".db", ".sqlite", ".dat", ".log"
    };

    public Task<List<LeftoverItem>> SearchAsync(
        string programName,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
        => SearchAsync(programName, string.Empty, string.Empty, progress, cancellationToken);

    public Task<List<LeftoverItem>> SearchAsync(
        string programName,
        string publisher,
        string installLocation,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        return Task.Run(() =>
        {
            string normalizedQuery = Normalize(programName);
            if (normalizedQuery.Length < 3)
            {
                return [];
            }

            string normalizedPublisher = Normalize(publisher);
            string normalizedInstallLocation = NormalizePath(installLocation);
            List<string> nameTokens = ExtractSignificantTokens(programName);
            List<string> publisherTokens = ExtractSignificantTokens(publisher);
            var results = new List<LeftoverItem>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            foreach ((string location, string root) in GetRoots())
            {
                cancellationToken.ThrowIfCancellationRequested();
                progress?.Report($"البحث داخل: {location}");
                if (!Directory.Exists(root))
                {
                    continue;
                }

                foreach (string directory in EnumerateDirectDirectories(root))
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    string name = Path.GetFileName(directory);
                    if (!IsCandidateDirectory(directory, name) || !seen.Add(directory))
                    {
                        continue;
                    }

                    MatchEvaluation match = EvaluateMatch(
                        directory,
                        name,
                        normalizedQuery,
                        normalizedPublisher,
                        normalizedInstallLocation,
                        nameTokens,
                        publisherTokens);
                    if (match.Score < 35)
                    {
                        continue;
                    }

                    DirectorySizeEstimate size = EstimateDirectorySize(directory, cancellationToken, MaximumSizeFiles);
                    results.Add(new LeftoverItem
                    {
                        Name = name,
                        Path = directory,
                        Location = location,
                        SizeBytes = size.SizeBytes,
                        SizeIsEstimated = size.Truncated,
                        ConfidenceScore = match.Score,
                        MatchReason = match.Reason,
                        IsQuarantinable = PathSafetyService.IsDirectChildOf(directory, root),
                        LastModifiedUtc = TryGetDirectoryLastWriteUtc(directory)
                    });
                }
            }

            return OrderResults(results);
        }, cancellationToken);
    }

    public Task<List<LeftoverItem>> SearchOrphanedProgramsAsync(
        IReadOnlyCollection<InstalledApp> installedApps,
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        return Task.Run(() =>
        {
            List<InstalledSignature> signatures = installedApps
                .Select(InstalledSignature.Create)
                .Where(signature => signature.IsLikelyCurrent)
                .ToList();
            var results = new List<LeftoverItem>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            int inspected = 0;

            foreach ((string location, string root) in GetRoots())
            {
                cancellationToken.ThrowIfCancellationRequested();
                progress?.Report($"فحص بقايا البرامج داخل: {location}");
                if (!Directory.Exists(root))
                {
                    continue;
                }

                foreach (string directory in EnumerateDirectDirectories(root))
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    inspected++;
                    if (inspected % 20 == 0)
                    {
                        progress?.Report($"تمت مراجعة {inspected:N0} مجلد برنامج...");
                    }

                    string name = Path.GetFileName(directory);
                    if (!IsCandidateDirectory(directory, name) || !seen.Add(directory))
                    {
                        continue;
                    }

                    DirectoryEvidence evidence = InspectDirectoryEvidence(directory, cancellationToken);
                    if (!evidence.HasApplicationEvidence || evidence.IsMicrosoftOwned)
                    {
                        continue;
                    }

                    if (MatchesInstalledApplication(directory, name, evidence, signatures))
                    {
                        continue;
                    }

                    int score = 35;
                    var reasons = new List<string> { "لا يوجد له تسجيل تثبيت حالي مطابق" };

                    if (evidence.ExecutableCount > 0)
                    {
                        score += 18;
                        reasons.Add($"يحتوي {evidence.ExecutableCount:N0} ملفًا تنفيذيًا أو مكتبة");
                    }

                    if (evidence.HasUninstallerRemnant)
                    {
                        score += 20;
                        reasons.Add("يحتوي بقايا أداة إزالة أو سجل تثبيت");
                    }

                    if (evidence.LaunchableExecutableCount > 0)
                    {
                        reasons.Add("يحتوي ملف تشغيل فعليًا — لن يُنقل تلقائيًا للحماية");
                    }

                    if (!string.IsNullOrWhiteSpace(evidence.ProductName))
                    {
                        score += 10;
                        reasons.Add($"بيانات الملفات تشير إلى {evidence.ProductName}");
                    }

                    TimeSpan age = evidence.LastWriteUtc == default
                        ? TimeSpan.Zero
                        : DateTime.UtcNow - evidence.LastWriteUtc;
                    if (age >= TimeSpan.FromDays(180))
                    {
                        score += 20;
                        reasons.Add("لم يتغير منذ أكثر من 180 يومًا");
                    }
                    else if (age >= TimeSpan.FromDays(90))
                    {
                        score += 15;
                        reasons.Add("لم يتغير منذ أكثر من 90 يومًا");
                    }
                    else if (age >= TimeSpan.FromDays(60))
                    {
                        score += 10;
                        reasons.Add("قديم لأكثر من 60 يومًا");
                    }
                    else if (age > TimeSpan.Zero && age < TimeSpan.FromDays(14))
                    {
                        score -= 20;
                        reasons.Add("حديث التعديل — تم خفض الثقة");
                    }

                    if (evidence.LooksSharedVendorFolder)
                    {
                        score -= 30;
                        reasons.Add("قد يكون مجلد شركة مشتركًا");
                    }

                    score = Math.Clamp(score, 35, 99);
                    bool directChild = PathSafetyService.IsDirectChildOf(directory, root);
                    bool quarantinable = directChild
                                         && score >= 90
                                         && age >= TimeSpan.FromDays(60)
                                         && evidence.HasUninstallerRemnant
                                         && evidence.LaunchableExecutableCount == 0
                                         && !evidence.LooksSharedVendorFolder;
                    DirectorySizeEstimate size = EstimateDirectorySize(directory, cancellationToken, MaximumSizeFiles);

                    results.Add(new LeftoverItem
                    {
                        Name = name,
                        Path = directory,
                        Location = location,
                        SizeBytes = size.SizeBytes,
                        SizeIsEstimated = size.Truncated,
                        ItemType = "@PossibleApplicationLeftover",
                        ConfidenceScore = score,
                        MatchReason = string.Join("، ", reasons.Distinct()),
                        IsQuarantinable = quarantinable,
                        LastModifiedUtc = evidence.LastWriteUtc
                    });
                }
            }

            return OrderResults(results);
        }, cancellationToken);
    }

    private static bool MatchesInstalledApplication(
        string directory,
        string directoryName,
        DirectoryEvidence evidence,
        IReadOnlyCollection<InstalledSignature> signatures)
    {
        string normalizedDirectory = NormalizePath(directory);
        string normalizedName = Normalize(directoryName);
        string normalizedProduct = Normalize(evidence.ProductName);
        string normalizedCompany = Normalize(evidence.CompanyName);

        foreach (InstalledSignature signature in signatures)
        {
            if (!string.IsNullOrWhiteSpace(signature.InstallLocation)
                && (PathSafetyService.IsPathUnder(normalizedDirectory, signature.InstallLocation)
                    || PathSafetyService.IsPathUnder(signature.InstallLocation, normalizedDirectory)))
            {
                return true;
            }

            if (!string.IsNullOrWhiteSpace(signature.UninstallDirectory)
                && (PathSafetyService.IsPathUnder(signature.UninstallDirectory, normalizedDirectory)
                    || PathSafetyService.IsPathUnder(normalizedDirectory, signature.UninstallDirectory)))
            {
                return true;
            }

            int requiredNameTokens = Math.Min(2, signature.NameTokens.Count);
            if (requiredNameTokens > 0
                && signature.NameTokens.Count(token => normalizedName.Contains(token, StringComparison.OrdinalIgnoreCase)) >= requiredNameTokens)
            {
                return true;
            }

            if (!string.IsNullOrWhiteSpace(normalizedProduct)
                && signature.NameTokens.Any(token => normalizedProduct.Contains(token, StringComparison.OrdinalIgnoreCase)))
            {
                return true;
            }

            if (!string.IsNullOrWhiteSpace(normalizedCompany)
                && signature.PublisherTokens.Any(token => normalizedCompany.Contains(token, StringComparison.OrdinalIgnoreCase)))
            {
                return true;
            }
        }

        return false;
    }

    private static DirectoryEvidence InspectDirectoryEvidence(string directory, CancellationToken cancellationToken)
    {
        int executableCount = 0;
        int launchableExecutableCount = 0;
        int configurationCount = 0;
        int directSubdirectories = 0;
        bool hasUninstaller = false;
        string productName = string.Empty;
        string companyName = string.Empty;
        DateTime lastWriteUtc = TryGetDirectoryLastWriteUtc(directory);

        try
        {
            directSubdirectories = Directory.EnumerateDirectories(directory, "*", SearchOption.TopDirectoryOnly)
                .Take(12)
                .Count();
        }
        catch
        {
            // Optional evidence only.
        }

        var candidateFiles = new List<string>();
        try
        {
            candidateFiles.AddRange(Directory.EnumerateFiles(directory, "*", SearchOption.TopDirectoryOnly).Take(60));
            foreach (string child in Directory.EnumerateDirectories(directory, "*", SearchOption.TopDirectoryOnly).Take(4))
            {
                cancellationToken.ThrowIfCancellationRequested();
                candidateFiles.AddRange(Directory.EnumerateFiles(child, "*", SearchOption.TopDirectoryOnly).Take(15));
            }
        }
        catch
        {
            // Use the files already collected.
        }

        foreach (string file in candidateFiles.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            cancellationToken.ThrowIfCancellationRequested();
            string extension = Path.GetExtension(file);
            string fileName = Path.GetFileName(file);

            if (extension.Equals(".exe", StringComparison.OrdinalIgnoreCase)
                || extension.Equals(".dll", StringComparison.OrdinalIgnoreCase))
            {
                executableCount++;
                bool isUninstallerExecutable = extension.Equals(".exe", StringComparison.OrdinalIgnoreCase)
                                              && (fileName.StartsWith("unins", StringComparison.OrdinalIgnoreCase)
                                                  || fileName.Contains("uninstall", StringComparison.OrdinalIgnoreCase)
                                                  || fileName.Contains("remove", StringComparison.OrdinalIgnoreCase));
                if (extension.Equals(".exe", StringComparison.OrdinalIgnoreCase) && !isUninstallerExecutable)
                {
                    launchableExecutableCount++;
                }

                if ((string.IsNullOrWhiteSpace(productName) || string.IsNullOrWhiteSpace(companyName)) && executableCount <= 8)
                {
                    try
                    {
                        FileVersionInfo info = FileVersionInfo.GetVersionInfo(file);
                        productName = string.IsNullOrWhiteSpace(productName) ? info.ProductName ?? string.Empty : productName;
                        companyName = string.IsNullOrWhiteSpace(companyName) ? info.CompanyName ?? string.Empty : companyName;
                    }
                    catch
                    {
                        // Version metadata is optional.
                    }
                }
            }
            else if (ConfigurationExtensions.Contains(extension))
            {
                configurationCount++;
            }

            if (fileName.StartsWith("unins", StringComparison.OrdinalIgnoreCase)
                || fileName.Contains("uninstall", StringComparison.OrdinalIgnoreCase)
                || extension.Equals(".msi", StringComparison.OrdinalIgnoreCase)
                || (extension.Equals(".log", StringComparison.OrdinalIgnoreCase)
                    && fileName.Contains("install", StringComparison.OrdinalIgnoreCase)))
            {
                hasUninstaller = true;
            }
        }

        bool sharedVendor = directSubdirectories >= 6 && executableCount <= 1 && !hasUninstaller;
        bool hasAppEvidence = executableCount > 0 || hasUninstaller || configurationCount >= 2;
        bool microsoftOwned = companyName.Contains("Microsoft", StringComparison.OrdinalIgnoreCase)
                              || productName.Contains("Windows", StringComparison.OrdinalIgnoreCase)
                              || productName.Contains("Microsoft", StringComparison.OrdinalIgnoreCase);

        return new DirectoryEvidence(
            hasAppEvidence,
            executableCount,
            launchableExecutableCount,
            configurationCount,
            directSubdirectories,
            hasUninstaller,
            sharedVendor,
            microsoftOwned,
            productName.Trim(),
            companyName.Trim(),
            lastWriteUtc);
    }

    private static MatchEvaluation EvaluateMatch(
        string directory,
        string name,
        string normalizedQuery,
        string normalizedPublisher,
        string normalizedInstallLocation,
        IReadOnlyCollection<string> nameTokens,
        IReadOnlyCollection<string> publisherTokens)
    {
        string normalizedName = Normalize(name);
        string normalizedDirectory = NormalizePath(directory);
        int score = 0;
        var reasons = new List<string>();

        if (!string.IsNullOrWhiteSpace(normalizedInstallLocation)
            && string.Equals(normalizedDirectory, normalizedInstallLocation, StringComparison.OrdinalIgnoreCase))
        {
            score = 100;
            reasons.Add("يطابق مجلد التثبيت المسجل");
        }

        if (string.Equals(normalizedName, normalizedQuery, StringComparison.OrdinalIgnoreCase))
        {
            score = Math.Max(score, 95);
            reasons.Add("الاسم مطابق تمامًا");
        }
        else if (normalizedName.Contains(normalizedQuery, StringComparison.OrdinalIgnoreCase))
        {
            score = Math.Max(score, 80);
            reasons.Add("اسم المجلد يحتوي اسم البرنامج");
        }
        else if (normalizedName.Length >= 4 && normalizedQuery.Contains(normalizedName, StringComparison.OrdinalIgnoreCase))
        {
            score = Math.Max(score, 62);
            reasons.Add("اسم المجلد جزء من اسم البرنامج");
        }

        int matchedNameTokens = nameTokens.Count(token => normalizedName.Contains(token, StringComparison.OrdinalIgnoreCase));
        if (matchedNameTokens > 0)
        {
            score += Math.Min(36, matchedNameTokens * 12);
            reasons.Add($"تطابق {matchedNameTokens} كلمة من اسم البرنامج");
        }

        int matchedPublisherTokens = publisherTokens.Count(token => normalizedName.Contains(token, StringComparison.OrdinalIgnoreCase));
        if (matchedPublisherTokens > 0)
        {
            score += Math.Min(24, matchedPublisherTokens * 12);
            reasons.Add("يتطابق مع اسم الناشر");
        }
        else if (!string.IsNullOrWhiteSpace(normalizedPublisher)
                 && normalizedName.Length >= 4
                 && normalizedPublisher.Contains(normalizedName, StringComparison.OrdinalIgnoreCase))
        {
            score += 18;
            reasons.Add("المجلد يحمل اسم الناشر");
        }

        return new MatchEvaluation(Math.Min(score, 100), reasons.Count == 0
            ? "تطابق محتمل بالاسم"
            : string.Join("، ", reasons.Distinct()));
    }

    private static IEnumerable<string> EnumerateDirectDirectories(string root)
    {
        try
        {
            return Directory.EnumerateDirectories(root, "*", SearchOption.TopDirectoryOnly).ToList();
        }
        catch (Exception ex)
        {
            AppLogger.Error($"Could not enumerate leftover root: {root}", ex);
            return [];
        }
    }

    private static bool IsCandidateDirectory(string directory, string name)
    {
        if (string.IsNullOrWhiteSpace(name) || BlockedDirectoryNames.Contains(name))
        {
            return false;
        }

        try
        {
            return (File.GetAttributes(directory) & FileAttributes.ReparsePoint) == 0;
        }
        catch
        {
            return false;
        }
    }

    private static List<(string Location, string Root)> GetRoots()
    {
        return new List<(string, string)>
        {
            ("AppData المحلي", Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData)),
            ("AppData المتجول", Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)),
            ("بيانات البرامج المشتركة", Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData)),
            ("Program Files", Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles)),
            ("Program Files (x86)", Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86))
        }
        .Where(item => !string.IsNullOrWhiteSpace(item.Item2))
        .DistinctBy(item => item.Item2, StringComparer.OrdinalIgnoreCase)
        .ToList();
    }

    private static DateTime TryGetDirectoryLastWriteUtc(string path)
    {
        try
        {
            return Directory.GetLastWriteTimeUtc(path);
        }
        catch
        {
            return default;
        }
    }

    private static DirectorySizeEstimate EstimateDirectorySize(
        string path,
        CancellationToken cancellationToken,
        int maximumFiles)
    {
        long total = 0;
        int inspectedFiles = 0;
        bool truncated = false;
        try
        {
            var options = new EnumerationOptions
            {
                RecurseSubdirectories = true,
                IgnoreInaccessible = true,
                ReturnSpecialDirectories = false,
                AttributesToSkip = FileAttributes.ReparsePoint
            };

            foreach (string file in Directory.EnumerateFiles(path, "*", options))
            {
                cancellationToken.ThrowIfCancellationRequested();
                inspectedFiles++;
                if (inspectedFiles > maximumFiles)
                {
                    truncated = true;
                    break;
                }

                try
                {
                    total += new FileInfo(file).Length;
                }
                catch
                {
                    // Ignore inaccessible files.
                }
            }
        }
        catch
        {
            // Return the size collected so far.
        }

        return new DirectorySizeEstimate(total, truncated);
    }

    private static List<string> ExtractSignificantTokens(string value)
    {
        return value
            .Split([' ', '-', '_', '.', ',', '(', ')', '[', ']', '{', '}', '/', '\\'], StringSplitOptions.RemoveEmptyEntries)
            .Select(Normalize)
            .Where(token => token.Length >= 3 && !IgnoredTokens.Contains(token))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private static string NormalizePath(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        try
        {
            return Path.TrimEndingDirectorySeparator(Path.GetFullPath(
                Environment.ExpandEnvironmentVariables(value.Trim().Trim('"'))));
        }
        catch
        {
            return string.Empty;
        }
    }

    private static string Normalize(string value)
    {
        char[] ignored = [' ', '-', '_', '.', ',', '(', ')', '[', ']', '{', '}', '/', '\\'];
        string result = value.Trim().ToLowerInvariant();
        foreach (char character in ignored)
        {
            result = result.Replace(character.ToString(), string.Empty, StringComparison.Ordinal);
        }

        return result;
    }

    private static List<LeftoverItem> OrderResults(IEnumerable<LeftoverItem> results)
        => results
            .OrderByDescending(item => item.ConfidenceScore)
            .ThenByDescending(item => item.SizeBytes)
            .ThenBy(item => item.Name, StringComparer.CurrentCultureIgnoreCase)
            .ToList();

    private sealed record MatchEvaluation(int Score, string Reason);
    private sealed record DirectorySizeEstimate(long SizeBytes, bool Truncated);
    private sealed record DirectoryEvidence(
        bool HasApplicationEvidence,
        int ExecutableCount,
        int LaunchableExecutableCount,
        int ConfigurationFileCount,
        int DirectSubdirectoryCount,
        bool HasUninstallerRemnant,
        bool LooksSharedVendorFolder,
        bool IsMicrosoftOwned,
        string ProductName,
        string CompanyName,
        DateTime LastWriteUtc);

    private sealed class InstalledSignature
    {
        public required List<string> NameTokens { get; init; }
        public required List<string> PublisherTokens { get; init; }
        public required string InstallLocation { get; init; }
        public required string UninstallDirectory { get; init; }
        public bool IsLikelyCurrent { get; init; }

        public static InstalledSignature Create(InstalledApp app)
        {
            string installLocation = NormalizePath(app.InstallLocation);
            string uninstallExecutable = TryExtractCommandExecutable(app.UninstallString);
            string uninstallDirectory = NormalizePath(Path.GetDirectoryName(uninstallExecutable) ?? string.Empty);
            bool likelyCurrent = IsLikelyCurrentRegistration(app, installLocation, uninstallExecutable);

            return new InstalledSignature
            {
                NameTokens = ExtractSignificantTokens(app.DisplayName),
                PublisherTokens = ExtractSignificantTokens(app.Publisher),
                InstallLocation = installLocation,
                UninstallDirectory = uninstallDirectory,
                IsLikelyCurrent = likelyCurrent
            };
        }

        private static bool IsLikelyCurrentRegistration(
            InstalledApp app,
            string installLocation,
            string uninstallExecutable)
        {
            if (!string.IsNullOrWhiteSpace(installLocation) && Directory.Exists(installLocation))
            {
                return true;
            }

            if (string.IsNullOrWhiteSpace(app.UninstallString))
            {
                // A missing uninstall command is not enough evidence to call the registration stale.
                return true;
            }

            string fileName = Path.GetFileName(uninstallExecutable);
            if (fileName.Equals("msiexec.exe", StringComparison.OrdinalIgnoreCase)
                || fileName.Equals("rundll32.exe", StringComparison.OrdinalIgnoreCase)
                || fileName.Equals("cmd.exe", StringComparison.OrdinalIgnoreCase)
                || fileName.Equals("powershell.exe", StringComparison.OrdinalIgnoreCase)
                || fileName.Equals("pwsh.exe", StringComparison.OrdinalIgnoreCase)
                || fileName.Equals("wscript.exe", StringComparison.OrdinalIgnoreCase)
                || fileName.Equals("cscript.exe", StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            if (string.IsNullOrWhiteSpace(uninstallExecutable) || !Path.IsPathRooted(uninstallExecutable))
            {
                return true;
            }

            return File.Exists(uninstallExecutable);
        }

        private static string TryExtractCommandExecutable(string command)
        {
            if (string.IsNullOrWhiteSpace(command))
            {
                return string.Empty;
            }

            try
            {
                string expanded = Environment.ExpandEnvironmentVariables(command.Trim());
                if (expanded.StartsWith('"'))
                {
                    int closingQuote = expanded.IndexOf('"', 1);
                    return closingQuote > 1 ? expanded[1..closingQuote] : string.Empty;
                }

                int exeEnd = expanded.IndexOf(".exe", StringComparison.OrdinalIgnoreCase);
                if (exeEnd >= 0)
                {
                    return expanded[..(exeEnd + 4)].Trim();
                }

                return expanded.Split(' ', 2, StringSplitOptions.RemoveEmptyEntries).FirstOrDefault() ?? string.Empty;
            }
            catch
            {
                return string.Empty;
            }
        }
    }
}
