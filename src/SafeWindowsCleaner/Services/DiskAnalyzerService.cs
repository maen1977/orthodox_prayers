using System.Security.Cryptography;
using SafeWindowsCleaner.Helpers;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class DiskAnalyzerService
{
    private static readonly HashSet<string> AlwaysProtectedFileNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "pagefile.sys", "hiberfil.sys", "swapfile.sys", "bootmgr", "bootnxt", "ntldr", "ntdetect.com"
    };

    private static readonly HashSet<string> ProtectedTopLevelDirectoryNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "Windows", "Program Files", "Program Files (x86)", "ProgramData", "System Volume Information",
        "$Recycle.Bin", "Recovery", "Boot", "EFI", "PerfLogs"
    };

    private static readonly HashSet<string> ImageExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".heic", ".svg", ".ico"
    };

    private static readonly HashSet<string> VideoExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".m4v", ".flv", ".mpeg", ".mpg"
    };

    private static readonly HashSet<string> AudioExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma", ".opus"
    };

    private static readonly HashSet<string> DocumentExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".csv", ".odt", ".ods", ".epub"
    };

    private static readonly HashSet<string> ArchiveExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso", ".cab"
    };

    private static readonly HashSet<string> ProgramExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".exe", ".msi", ".msix", ".appx", ".dll", ".sys", ".drv", ".com", ".bat", ".cmd", ".ps1"
    };

    public Task<DiskAnalysisResult> AnalyzeAsync(
        string rootPath,
        DiskAnalyzerOptions? options = null,
        IProgress<DiskScanProgress>? progress = null,
        CancellationToken cancellationToken = default)
    {
        DiskAnalyzerOptions normalizedOptions = NormalizeOptions(options);
        return Task.Run(() => Analyze(rootPath, normalizedOptions, progress, cancellationToken), cancellationToken);
    }

    private static DiskAnalyzerOptions NormalizeOptions(DiskAnalyzerOptions? options)
    {
        options ??= new DiskAnalyzerOptions();
        return new DiskAnalyzerOptions
        {
            LargestFileLimit = Math.Clamp(options.LargestFileLimit, 50, 5000),
            MinimumDuplicateSizeBytes = Math.Clamp(options.MinimumDuplicateSizeBytes, 10L * 1024L * 1024L, 10L * 1024L * 1024L * 1024L),
            CalculateDuplicates = options.CalculateDuplicates,
            DuplicateCandidateLimit = Math.Clamp(options.DuplicateCandidateLimit, 1_000, 100_000),
            DuplicateResultFileLimit = Math.Clamp(options.DuplicateResultFileLimit, 100, 5_000),
            ProgressInterval = Math.Clamp(options.ProgressInterval, 250, 10_000),
            HashBufferSizeBytes = Math.Clamp(options.HashBufferSizeBytes, 32 * 1024, 1024 * 1024),
            ScanThrottleMilliseconds = Math.Clamp(options.ScanThrottleMilliseconds, 0, 10)
        };
    }

    private static DiskAnalysisResult Analyze(
        string rootPath,
        DiskAnalyzerOptions options,
        IProgress<DiskScanProgress>? progress,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(rootPath))
        {
            throw new ArgumentException("A scan path is required.", nameof(rootPath));
        }

        string fullRootPath = Path.GetFullPath(Environment.ExpandEnvironmentVariables(rootPath.Trim()));
        string pathRoot = Path.GetPathRoot(fullRootPath) ?? fullRootPath;
        string root = string.Equals(fullRootPath, pathRoot, StringComparison.OrdinalIgnoreCase)
            ? fullRootPath
            : Path.TrimEndingDirectorySeparator(fullRootPath);
        if (!Directory.Exists(root))
        {
            throw new DirectoryNotFoundException($"The scan directory does not exist: {root}");
        }

        var largestFiles = new PriorityQueue<FileRecord, long>();
        Dictionary<long, List<FileRecord>>? duplicateCandidates = options.CalculateDuplicates
            ? new Dictionary<long, List<FileRecord>>()
            : null;
        var folderAggregates = new Dictionary<string, FolderAggregate>(StringComparer.OrdinalIgnoreCase);
        var categoryAggregates = new Dictionary<string, CategoryAggregate>(StringComparer.OrdinalIgnoreCase);
        var pendingDirectories = new Stack<string>();
        pendingDirectories.Push(root);

        long totalBytes = 0;
        int fileCount = 0;
        int skippedEntries = 0;
        int duplicateCandidateCount = 0;
        bool duplicateCandidateLimitReached = false;

        while (pendingDirectories.Count > 0)
        {
            cancellationToken.ThrowIfCancellationRequested();
            string currentDirectory = pendingDirectories.Pop();

            IEnumerable<string> entries;
            try
            {
                entries = Directory.EnumerateFileSystemEntries(currentDirectory, "*", new EnumerationOptions
                {
                    RecurseSubdirectories = false,
                    IgnoreInaccessible = true,
                    ReturnSpecialDirectories = false,
                    AttributesToSkip = FileAttributes.ReparsePoint
                });
            }
            catch (Exception ex) when (ex is UnauthorizedAccessException or IOException)
            {
                skippedEntries++;
                continue;
            }

            try
            {
                foreach (string entry in entries)
            {
                cancellationToken.ThrowIfCancellationRequested();

                FileAttributes attributes;
                try
                {
                    attributes = File.GetAttributes(entry);
                }
                catch (Exception ex) when (ex is UnauthorizedAccessException or IOException)
                {
                    skippedEntries++;
                    continue;
                }

                if ((attributes & FileAttributes.ReparsePoint) != 0)
                {
                    skippedEntries++;
                    continue;
                }

                if ((attributes & FileAttributes.Directory) != 0)
                {
                    if (ShouldSkipDirectory(entry))
                    {
                        skippedEntries++;
                        continue;
                    }

                    pendingDirectories.Push(entry);
                    continue;
                }

                FileInfo info;
                try
                {
                    info = new FileInfo(entry);
                    long size = info.Length;
                    DateTime lastModified = info.LastWriteTime;
                    string extension = info.Extension;
                    string category = GetCategory(extension);
                    (bool safe, string protectionReason) = AssessQuarantineSafety(entry);

                    var record = new FileRecord(
                        info.Name,
                        info.FullName,
                        size,
                        lastModified,
                        extension,
                        category,
                        safe,
                        protectionReason);

                    totalBytes = checked(totalBytes + size);
                    fileCount++;
                    AddLargest(largestFiles, record, options.LargestFileLimit);
                    AddFolderAggregate(folderAggregates, root, record);
                    AddCategoryAggregate(categoryAggregates, record);

                    if (options.CalculateDuplicates
                        && duplicateCandidates is not null
                        && size >= options.MinimumDuplicateSizeBytes)
                    {
                        if (duplicateCandidateCount < options.DuplicateCandidateLimit)
                        {
                            if (!duplicateCandidates.TryGetValue(size, out List<FileRecord>? sameSize))
                            {
                                sameSize = [];
                                duplicateCandidates[size] = sameSize;
                            }

                            sameSize.Add(record);
                            duplicateCandidateCount++;
                        }
                        else
                        {
                            duplicateCandidateLimitReached = true;
                        }
                    }
                }
                catch (Exception ex) when (ex is UnauthorizedAccessException or IOException or OverflowException)
                {
                    skippedEntries++;
                }

                if (fileCount > 0 && fileCount % options.ProgressInterval == 0)
                {
                    progress?.Report(new DiskScanProgress(
                        $"تم فحص {fileCount:N0} ملف — {FormatBytesForProgress(totalBytes)}",
                        fileCount,
                        totalBytes));

                    if (options.ScanThrottleMilliseconds > 0)
                    {
                        Thread.Sleep(options.ScanThrottleMilliseconds);
                    }
                }
                }
            }
            catch (Exception ex) when (ex is UnauthorizedAccessException or IOException)
            {
                skippedEntries++;
            }
        }

        List<DiskFileItem> duplicateFiles = [];
        long duplicateWasteBytes = 0;
        bool duplicateResultLimitReached = false;
        if (options.CalculateDuplicates && duplicateCandidates is not null)
        {
            progress?.Report(new DiskScanProgress("فحص مرشحي التكرار بطريقة خفيفة ثم التحقق ببصمة SHA-256...", fileCount, totalBytes));
            var duplicateResult = FindDuplicates(root, duplicateCandidates, options, progress, cancellationToken);
            duplicateFiles = duplicateResult.Items;
            duplicateWasteBytes = duplicateResult.WasteBytes;
            duplicateResultLimitReached = duplicateResult.ResultLimitReached;
            skippedEntries += duplicateResult.Failures;
        }

        List<DiskFileItem> largest = largestFiles.UnorderedItems
            .Select(item => item.Element)
            .OrderByDescending(item => item.SizeBytes)
            .ThenBy(item => item.Path, StringComparer.CurrentCultureIgnoreCase)
            .Select(record => ToDiskFileItem(record, root))
            .ToList();

        List<DiskFolderSummary> folders = folderAggregates.Values
            .OrderByDescending(item => item.SizeBytes)
            .ThenBy(item => item.Name, StringComparer.CurrentCultureIgnoreCase)
            .Select(item => new DiskFolderSummary
            {
                Name = item.Name,
                Path = item.Path,
                SizeBytes = item.SizeBytes,
                FileCount = item.FileCount
            })
            .ToList();

        List<DiskCategorySummary> categories = categoryAggregates.Values
            .OrderByDescending(item => item.SizeBytes)
            .ThenBy(item => item.Category, StringComparer.CurrentCultureIgnoreCase)
            .Select(item => new DiskCategorySummary
            {
                Category = item.Category,
                SizeBytes = item.SizeBytes,
                FileCount = item.FileCount,
                Percentage = totalBytes == 0 ? 0 : item.SizeBytes * 100d / totalBytes
            })
            .ToList();

        progress?.Report(new DiskScanProgress("اكتمل تحليل مساحة القرص.", fileCount, totalBytes));
        return new DiskAnalysisResult
        {
            RootPath = root,
            TotalBytes = totalBytes,
            DuplicateWasteBytes = duplicateWasteBytes,
            FileCount = fileCount,
            SkippedEntries = skippedEntries,
            DuplicateAnalysisPerformed = options.CalculateDuplicates,
            DuplicateCandidateLimitReached = duplicateCandidateLimitReached,
            DuplicateResultLimitReached = duplicateResultLimitReached,
            LargestFiles = largest,
            DuplicateFiles = duplicateFiles,
            FolderSummaries = folders,
            CategorySummaries = categories
        };
    }

    private static void AddLargest(PriorityQueue<FileRecord, long> queue, FileRecord record, int largestFileLimit)
    {
        if (queue.Count < largestFileLimit)
        {
            queue.Enqueue(record, record.SizeBytes);
            return;
        }

        if (queue.TryPeek(out _, out long smallestSize) && record.SizeBytes > smallestSize)
        {
            queue.Dequeue();
            queue.Enqueue(record, record.SizeBytes);
        }
    }

    private static void AddFolderAggregate(
        Dictionary<string, FolderAggregate> aggregates,
        string root,
        FileRecord record)
    {
        string relative = Path.GetRelativePath(root, record.Path);
        int separatorIndex = relative.IndexOfAny(new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar });
        string firstPart = separatorIndex < 0 ? "(ملفات مباشرة)" : relative[..separatorIndex];
        string aggregatePath = separatorIndex < 0 ? root : Path.Combine(root, firstPart);

        if (!aggregates.TryGetValue(firstPart, out FolderAggregate? aggregate))
        {
            aggregate = new FolderAggregate(firstPart, aggregatePath);
            aggregates[firstPart] = aggregate;
        }

        aggregate.SizeBytes = checked(aggregate.SizeBytes + record.SizeBytes);
        aggregate.FileCount++;
    }

    private static void AddCategoryAggregate(
        Dictionary<string, CategoryAggregate> aggregates,
        FileRecord record)
    {
        if (!aggregates.TryGetValue(record.Category, out CategoryAggregate? aggregate))
        {
            aggregate = new CategoryAggregate(record.Category);
            aggregates[record.Category] = aggregate;
        }

        aggregate.SizeBytes = checked(aggregate.SizeBytes + record.SizeBytes);
        aggregate.FileCount++;
    }

    private static (List<DiskFileItem> Items, long WasteBytes, int Failures, bool ResultLimitReached) FindDuplicates(
        string root,
        Dictionary<long, List<FileRecord>> candidates,
        DiskAnalyzerOptions options,
        IProgress<DiskScanProgress>? progress,
        CancellationToken cancellationToken)
    {
        var duplicateSets = new List<List<(FileRecord Record, string Hash)>>();
        int sampledFiles = 0;
        int hashedFiles = 0;
        int failures = 0;

        foreach ((long _, List<FileRecord> sameSizeFiles) in candidates
                     .Where(pair => pair.Value.Count > 1)
                     .OrderByDescending(pair => pair.Key))
        {
            cancellationToken.ThrowIfCancellationRequested();

            // A small first/middle/last sample prevents unnecessary full-disk reads on HDDs.
            // A full SHA-256 is still calculated before any item is classified as a duplicate.
            var samples = new Dictionary<string, List<FileRecord>>(StringComparer.OrdinalIgnoreCase);
            foreach (FileRecord record in sameSizeFiles)
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    string sample = ComputeSampleHash(record.Path, options.HashBufferSizeBytes, cancellationToken);
                    if (!samples.TryGetValue(sample, out List<FileRecord>? matchingSample))
                    {
                        matchingSample = [];
                        samples[sample] = matchingSample;
                    }

                    matchingSample.Add(record);
                }
                catch (Exception ex) when (ex is UnauthorizedAccessException or IOException)
                {
                    failures++;
                }

                sampledFiles++;
                if (sampledFiles % 100 == 0)
                {
                    progress?.Report(new DiskScanProgress(
                        $"فحص خفيف لـ {sampledFiles:N0} ملف مرشح للتكرار...",
                        sampledFiles,
                        0));
                }
            }

            foreach (List<FileRecord> sampleMatches in samples.Values.Where(group => group.Count > 1))
            {
                var hashes = new Dictionary<string, List<FileRecord>>(StringComparer.OrdinalIgnoreCase);
                foreach (FileRecord record in sampleMatches)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    try
                    {
                        string hash = ComputeSha256(record.Path, options.HashBufferSizeBytes, cancellationToken);
                        if (!hashes.TryGetValue(hash, out List<FileRecord>? matchingHash))
                        {
                            matchingHash = [];
                            hashes[hash] = matchingHash;
                        }

                        matchingHash.Add(record);
                    }
                    catch (Exception ex) when (ex is UnauthorizedAccessException or IOException)
                    {
                        failures++;
                    }

                    hashedFiles++;
                    if (hashedFiles % 20 == 0)
                    {
                        progress?.Report(new DiskScanProgress(
                            $"تم التحقق الكامل من بصمة {hashedFiles:N0} ملف...",
                            hashedFiles,
                            0));
                    }
                }

                foreach ((string hash, List<FileRecord> matching) in hashes.Where(pair => pair.Value.Count > 1))
                {
                    duplicateSets.Add(matching.Select(record => (record, hash)).ToList());
                }
            }
        }

        long wasteBytes = 0;
        var duplicateItems = new List<DiskFileItem>();
        int groupNumber = 0;
        bool resultLimitReached = false;

        foreach (List<(FileRecord Record, string Hash)> set in duplicateSets
                     .OrderByDescending(set => set[0].Record.SizeBytes * (set.Count - 1L)))
        {
            cancellationToken.ThrowIfCancellationRequested();
            groupNumber++;
            string groupName = $"مجموعة {groupNumber:N0}";
            List<(FileRecord Record, string Hash)> ordered = set
                .OrderBy(item => item.Record.LastModified)
                .ThenBy(item => item.Record.Path.Length)
                .ThenBy(item => item.Record.Path, StringComparer.CurrentCultureIgnoreCase)
                .ToList();

            wasteBytes = checked(wasteBytes + ordered[0].Record.SizeBytes * (ordered.Count - 1L));
            if (duplicateItems.Count + ordered.Count > options.DuplicateResultFileLimit)
            {
                resultLimitReached = true;
                continue;
            }

            for (int index = 0; index < ordered.Count; index++)
            {
                (FileRecord record, string hash) = ordered[index];
                duplicateItems.Add(new DiskFileItem
                {
                    Name = record.Name,
                    Path = record.Path,
                    SizeBytes = record.SizeBytes,
                    LastModified = record.LastModified,
                    Extension = record.Extension,
                    Category = record.Category,
                    IsSafeToQuarantine = record.IsSafeToQuarantine,
                    ProtectionReason = record.ProtectionReason,
                    ScanRoot = root,
                    DuplicateGroup = groupName,
                    HashShort = hash[..Math.Min(12, hash.Length)],
                    IsPreferredCopy = index == 0
                });
            }
        }

        return (duplicateItems, wasteBytes, failures, resultLimitReached);
    }

    private static string ComputeSampleHash(string path, int bufferSize, CancellationToken cancellationToken)
    {
        int sampleSize = Math.Clamp(bufferSize, 32 * 1024, 128 * 1024);
        using var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.ReadWrite | FileShare.Delete,
            bufferSize: sampleSize,
            options: FileOptions.RandomAccess);
        using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        hash.AppendData(BitConverter.GetBytes(stream.Length));

        long[] offsets =
        [
            0,
            Math.Max(0, (stream.Length - sampleSize) / 2),
            Math.Max(0, stream.Length - sampleSize)
        ];
        byte[] buffer = new byte[sampleSize];

        foreach (long offset in offsets.Distinct())
        {
            cancellationToken.ThrowIfCancellationRequested();
            stream.Position = offset;
            hash.AppendData(BitConverter.GetBytes(offset));
            int remaining = (int)Math.Min(sampleSize, stream.Length - offset);
            while (remaining > 0)
            {
                int read = stream.Read(buffer, 0, Math.Min(buffer.Length, remaining));
                if (read <= 0)
                {
                    break;
                }

                hash.AppendData(buffer, 0, read);
                remaining -= read;
            }
        }

        return Convert.ToHexString(hash.GetHashAndReset());
    }

    private static string ComputeSha256(string path, int bufferSize, CancellationToken cancellationToken)
    {
        using var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.ReadWrite | FileShare.Delete,
            bufferSize: bufferSize,
            options: FileOptions.SequentialScan);
        using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        byte[] buffer = new byte[bufferSize];

        while (true)
        {
            cancellationToken.ThrowIfCancellationRequested();
            int read = stream.Read(buffer, 0, buffer.Length);
            if (read <= 0)
            {
                break;
            }

            hash.AppendData(buffer, 0, read);
        }

        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }

    private static DiskFileItem ToDiskFileItem(FileRecord record, string root)
        => new()
        {
            Name = record.Name,
            Path = record.Path,
            SizeBytes = record.SizeBytes,
            LastModified = record.LastModified,
            Extension = record.Extension,
            Category = record.Category,
            IsSafeToQuarantine = record.IsSafeToQuarantine,
            ProtectionReason = record.ProtectionReason,
            ScanRoot = root
        };

    private static bool ShouldSkipDirectory(string path)
    {
        try
        {
            string fullPath = Path.TrimEndingDirectorySeparator(Path.GetFullPath(path));
            string quarantine = Path.TrimEndingDirectorySeparator(Path.GetFullPath(QuarantineService.QuarantineRoot));
            if (IsPathUnder(fullPath, quarantine) || PathsEqual(fullPath, quarantine))
            {
                return true;
            }

            string directoryName = Path.GetFileName(fullPath);
            return string.Equals(directoryName, "$Recycle.Bin", StringComparison.OrdinalIgnoreCase)
                   || string.Equals(directoryName, "System Volume Information", StringComparison.OrdinalIgnoreCase);
        }
        catch
        {
            return true;
        }
    }

    private static (bool Safe, string Reason) AssessQuarantineSafety(string path)
    {
        try
        {
            string fullPath = Path.GetFullPath(path);
            string fileName = Path.GetFileName(fullPath);
            if (AlwaysProtectedFileNames.Contains(fileName))
            {
                return (false, "ملف أساسي لنظام ويندوز");
            }

            if (fullPath.IndexOf(':', 2) >= 0)
            {
                return (false, "مسار بديل غير مدعوم");
            }

            string windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
            string programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
            string programFilesX86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
            string programData = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
            string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);

            foreach (string protectedRoot in new[] { windows, programFiles, programFilesX86, programData, appData, localAppData }
                         .Where(value => !string.IsNullOrWhiteSpace(value)))
            {
                if (IsPathUnder(fullPath, protectedRoot) || PathsEqual(fullPath, protectedRoot))
                {
                    return (false, "داخل مجلد نظام أو بيانات تطبيقات محمي");
                }
            }

            string systemDrive = Path.GetPathRoot(windows) ?? string.Empty;
            string itemDrive = Path.GetPathRoot(fullPath) ?? string.Empty;
            if (string.Equals(systemDrive, itemDrive, StringComparison.OrdinalIgnoreCase))
            {
                string userProfile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
                if (string.IsNullOrWhiteSpace(userProfile) || !IsPathUnder(fullPath, userProfile))
                {
                    return (false, "خارج ملفات المستخدم على قرص النظام");
                }
            }
            else
            {
                string relativeToDrive = Path.GetRelativePath(itemDrive, fullPath);
                string firstPart = relativeToDrive.Split(
                    new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar },
                    StringSplitOptions.RemoveEmptyEntries).FirstOrDefault() ?? string.Empty;
                if (ProtectedTopLevelDirectoryNames.Contains(firstPart))
                {
                    return (false, "داخل مجلد نظام محمي على القرص");
                }
            }

            string extension = Path.GetExtension(fullPath);
            if (extension.Equals(".sys", StringComparison.OrdinalIgnoreCase)
                || extension.Equals(".drv", StringComparison.OrdinalIgnoreCase))
            {
                return (false, "ملف برنامج تشغيل للنظام");
            }

            return (true, "راجع الملف قبل نقله إلى الحجر");
        }
        catch
        {
            return (false, "تعذر التحقق من سلامة المسار");
        }
    }

    private static string GetCategory(string extension)
    {
        if (ImageExtensions.Contains(extension)) return "@CategoryImages";
        if (VideoExtensions.Contains(extension)) return "@CategoryVideo";
        if (AudioExtensions.Contains(extension)) return "@CategoryAudio";
        if (DocumentExtensions.Contains(extension)) return "@CategoryDocuments";
        if (ArchiveExtensions.Contains(extension)) return "@CategoryArchives";
        if (ProgramExtensions.Contains(extension)) return "@CategoryPrograms";
        return string.IsNullOrWhiteSpace(extension) ? "@CategoryNoExtension" : "@CategoryOther";
    }

    private static bool IsPathUnder(string path, string root)
    {
        if (string.IsNullOrWhiteSpace(path) || string.IsNullOrWhiteSpace(root))
        {
            return false;
        }

        string fullRoot = Path.TrimEndingDirectorySeparator(Path.GetFullPath(root)) + Path.DirectorySeparatorChar;
        string fullPath = Path.GetFullPath(path);
        return fullPath.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase);
    }

    private static bool PathsEqual(string left, string right)
        => string.Equals(
            Path.TrimEndingDirectorySeparator(Path.GetFullPath(left)),
            Path.TrimEndingDirectorySeparator(Path.GetFullPath(right)),
            StringComparison.OrdinalIgnoreCase);

    private static string FormatBytesForProgress(long bytes)
        => SizeFormatter.Format(bytes, LocalizationService.ActiveLanguageCode);

    private sealed record FileRecord(
        string Name,
        string Path,
        long SizeBytes,
        DateTime LastModified,
        string Extension,
        string Category,
        bool IsSafeToQuarantine,
        string ProtectionReason);

    private sealed class FolderAggregate(string name, string path)
    {
        public string Name { get; } = name;
        public string Path { get; } = path;
        public long SizeBytes { get; set; }
        public int FileCount { get; set; }
    }

    private sealed class CategoryAggregate(string category)
    {
        public string Category { get; } = category;
        public long SizeBytes { get; set; }
        public int FileCount { get; set; }
    }
}
