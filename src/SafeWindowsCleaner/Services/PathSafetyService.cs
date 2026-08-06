namespace SafeWindowsCleaner.Services;

public static class PathSafetyService
{
    private static readonly HashSet<string> ProtectedRootNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "Windows", "Program Files", "Program Files (x86)", "ProgramData", "System Volume Information",
        "$Recycle.Bin", "Recovery", "Boot", "EFI", "PerfLogs"
    };

    private static readonly HashSet<string> ProtectedFileNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "pagefile.sys", "hiberfil.sys", "swapfile.sys", "bootmgr", "bootnxt", "ntldr", "ntdetect.com"
    };

    public static bool IsPathUnder(string candidatePath, string rootPath)
    {
        if (string.IsNullOrWhiteSpace(candidatePath) || string.IsNullOrWhiteSpace(rootPath))
        {
            return false;
        }

        string candidate = Path.GetFullPath(candidatePath);
        string root = Path.TrimEndingDirectorySeparator(Path.GetFullPath(rootPath));
        return string.Equals(candidate, root, StringComparison.OrdinalIgnoreCase)
               || candidate.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
    }

    public static bool IsDirectChildOf(string candidatePath, string rootPath)
    {
        if (string.IsNullOrWhiteSpace(candidatePath) || string.IsNullOrWhiteSpace(rootPath))
        {
            return false;
        }

        try
        {
            string candidate = Path.TrimEndingDirectorySeparator(Path.GetFullPath(candidatePath));
            string root = Path.TrimEndingDirectorySeparator(Path.GetFullPath(rootPath));
            string? parent = Path.GetDirectoryName(candidate);
            return !string.IsNullOrWhiteSpace(parent)
                   && string.Equals(Path.TrimEndingDirectorySeparator(parent), root, StringComparison.OrdinalIgnoreCase);
        }
        catch
        {
            return false;
        }
    }

    public static bool IsProtectedSystemPath(string path)
    {
        string fullPath = Path.GetFullPath(path);
        string fileName = Path.GetFileName(fullPath);
        if (ProtectedFileNames.Contains(fileName))
        {
            return true;
        }

        string extension = Path.GetExtension(fullPath);
        if (extension.Equals(".sys", StringComparison.OrdinalIgnoreCase)
            || extension.Equals(".drv", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        string windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        if (!string.IsNullOrWhiteSpace(windows) && IsPathUnder(fullPath, windows))
        {
            return true;
        }

        string drive = Path.GetPathRoot(fullPath) ?? string.Empty;
        if (string.IsNullOrWhiteSpace(drive))
        {
            return true;
        }

        string relative = Path.GetRelativePath(drive, fullPath);
        string first = relative.Split(
            new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar },
            StringSplitOptions.RemoveEmptyEntries).FirstOrDefault() ?? string.Empty;
        return ProtectedRootNames.Contains(first);
    }

    public static bool WouldRemoveEveryExistingCopy(IEnumerable<string> groupPaths, ISet<string> selectedPaths)
    {
        List<string> existing = groupPaths
            .Where(path => File.Exists(path))
            .Select(Path.GetFullPath)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
        return existing.Count > 0 && existing.All(selectedPaths.Contains);
    }
}
