using SafeWindowsCleaner.Win7.Models;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace SafeWindowsCleaner.Win7.Services
{
    public sealed class CleanupService
    {
        private const int MaximumItems = 5000;
        private static readonly TimeSpan MinimumAge = TimeSpan.FromHours(24);

        public List<CleanupItem> Scan()
        {
            List<CleanupItem> results = new List<CleanupItem>();
            foreach (Target target in GetTargets())
            {
                if (results.Count >= MaximumItems) break;
                ScanDirectory(target, results);
            }
            return results.OrderByDescending(x => x.SizeBytes).ToList();
        }

        private static IEnumerable<Target> GetTargets()
        {
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
            yield return new Target(Path.GetTempPath(), "Temp");
            yield return new Target(Path.Combine(windows, "Temp"), "WindowsTemp");
            yield return new Target(Path.Combine(local, "Google", "Chrome", "User Data", "Default", "Cache"), "BrowserCache");
            yield return new Target(Path.Combine(local, "Google", "Chrome", "User Data", "Default", "Code Cache"), "BrowserCache");
            yield return new Target(Path.Combine(local, "Mozilla", "Firefox", "Profiles"), "BrowserCache", "cache2");
            yield return new Target(Path.Combine(local, "Microsoft", "Windows", "Temporary Internet Files"), "BrowserCache");
        }

        private static void ScanDirectory(Target target, List<CleanupItem> results)
        {
            if (string.IsNullOrWhiteSpace(target.Root) || !Directory.Exists(target.Root)) return;
            try
            {
                IEnumerable<string> files;
                if (string.IsNullOrEmpty(target.RequiredDirectoryName))
                {
                    files = SafeEnumerateFiles(target.Root);
                }
                else
                {
                    files = SafeEnumerateDirectories(target.Root)
                        .Where(x => string.Equals(Path.GetFileName(x), target.RequiredDirectoryName, StringComparison.OrdinalIgnoreCase))
                        .SelectMany(SafeEnumerateFiles);
                }

                foreach (string file in files)
                {
                    if (results.Count >= MaximumItems) return;
                    try
                    {
                        FileInfo info = new FileInfo(file);
                        if (!info.Exists || DateTime.Now - info.LastWriteTime < MinimumAge) continue;
                        results.Add(new CleanupItem
                        {
                            IsSelected = true,
                            Category = LocalizationService.Get(target.CategoryKey),
                            Path = info.FullName,
                            SizeBytes = info.Length,
                            LastWriteTime = info.LastWriteTime
                        });
                    }
                    catch { }
                }
            }
            catch { }
        }

        private static IEnumerable<string> SafeEnumerateFiles(string root)
        {
            Stack<string> pending = new Stack<string>();
            pending.Push(root);
            while (pending.Count > 0)
            {
                string current = pending.Pop();
                string[] files = new string[0];
                string[] directories = new string[0];
                try { files = Directory.GetFiles(current); } catch { }
                foreach (string file in files) yield return file;
                try { directories = Directory.GetDirectories(current); } catch { }
                foreach (string directory in directories)
                {
                    try
                    {
                        FileAttributes attributes = File.GetAttributes(directory);
                        if ((attributes & FileAttributes.ReparsePoint) == 0) pending.Push(directory);
                    }
                    catch { }
                }
            }
        }

        private static IEnumerable<string> SafeEnumerateDirectories(string root)
        {
            Stack<string> pending = new Stack<string>();
            pending.Push(root);
            while (pending.Count > 0)
            {
                string current = pending.Pop();
                yield return current;
                string[] directories = new string[0];
                try { directories = Directory.GetDirectories(current); } catch { }
                foreach (string directory in directories)
                {
                    try
                    {
                        FileAttributes attributes = File.GetAttributes(directory);
                        if ((attributes & FileAttributes.ReparsePoint) == 0) pending.Push(directory);
                    }
                    catch { }
                }
            }
        }

        private sealed class Target
        {
            public Target(string root, string categoryKey, string requiredDirectoryName = null)
            {
                Root = root;
                CategoryKey = categoryKey;
                RequiredDirectoryName = requiredDirectoryName;
            }
            public string Root { get; private set; }
            public string CategoryKey { get; private set; }
            public string RequiredDirectoryName { get; private set; }
        }
    }
}
