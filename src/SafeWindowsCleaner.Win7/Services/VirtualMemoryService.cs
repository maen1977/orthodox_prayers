using Microsoft.Win32;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Management;
using System.Xml.Serialization;

namespace SafeWindowsCleaner.Win7.Services
{
    public sealed class VirtualMemoryService
    {
        private const string MemoryKeyPath = @"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management";
        private static readonly string BackupPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SafeWindowsCleaner", "Win7", "virtual-memory-backup.xml");
        public const int MaximumSizeMb = 16384;
        public const int MediumSizeMb = 8192;
        public const int MinimumSizeMb = 4096;
        public const long MinimumFreeBytesAfterApply = 8L * 1024L * 1024L * 1024L;
        private static readonly TimeSpan ManagementTimeout = TimeSpan.FromSeconds(20);

        public string GetStatus()
        {
            try
            {
                string drive = GetSystemDrive().TrimEnd('\\');
                using (RegistryKey key = Registry.LocalMachine.OpenSubKey(MemoryKeyPath))
                {
                    string[] values = key == null ? null : key.GetValue("PagingFiles") as string[];
                    if (values != null)
                    {
                        foreach (string value in values)
                        {
                            int sizeMb;
                            if (TryReadFixedEntry(value, drive, out sizeMb))
                            {
                                return LocalizationService.Format(
                                    "FixedPreset",
                                    SizeFormatter.Format(sizeMb * 1024L * 1024L));
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogService.Write("Virtual-memory status read failed: " + ex);
            }
            return LocalizationService.Get("Automatic");
        }

        public long GetAvailableFreeSpace()
        {
            return new DriveInfo(GetSystemDrive()).AvailableFreeSpace;
        }

        public int GetRecommendedSizeMb()
        {
            return GetRecommendedSizeMb(GetAvailableFreeSpace());
        }

        public static int GetRecommendedSizeMb(long availableFreeBytes)
        {
            int[] candidates = { MaximumSizeMb, MediumSizeMb, MinimumSizeMb };
            foreach (int candidate in candidates)
            {
                long bytes = candidate * 1024L * 1024L;
                if (availableFreeBytes - bytes >= MinimumFreeBytesAfterApply)
                {
                    return candidate;
                }
            }
            return 0;
        }

        public int ApplyRecommended()
        {
            int selectedSizeMb = GetRecommendedSizeMb();
            if (selectedSizeMb == 0)
            {
                throw new InvalidOperationException(LocalizationService.Get("NeedSpace"));
            }

            VirtualMemoryBackup previous = ReadCurrent();
            if (!File.Exists(BackupPath))
            {
                SaveBackup(previous);
            }

            try
            {
                string systemDrive = GetSystemDrive().TrimEnd('\\');
                string replacement = systemDrive + "\\pagefile.sys " + selectedSizeMb + " " + selectedSizeMb;
                List<string> entries = new List<string>();
                foreach (string item in previous.PagingFiles ?? new string[0])
                {
                    if (!IsSystemDriveEntry(item, systemDrive))
                    {
                        entries.Add(item);
                    }
                }
                entries.Add(replacement);

                SetAutomaticManaged(false);
                string[] expectedEntries = entries.ToArray();
                WritePagingFiles(expectedEntries);
                VerifyPagingFiles(expectedEntries, true);
                if (GetAutomaticManaged())
                {
                    throw new InvalidOperationException(LocalizationService.Get("PagefileUnavailable"));
                }
                LogService.Write("Configured a fixed " + selectedSizeMb + " MB page file on " + systemDrive);
                return selectedSizeMb;
            }
            catch
            {
                TryRestore(previous);
                throw;
            }
        }

        public bool RestorePrevious()
        {
            if (!File.Exists(BackupPath)) return false;
            VirtualMemoryBackup backup;
            using (FileStream stream = File.OpenRead(BackupPath))
            {
                backup = (VirtualMemoryBackup)new XmlSerializer(typeof(VirtualMemoryBackup)).Deserialize(stream);
            }
            if (backup.FormatVersion < 2)
            {
                // Backups written by 2.3 and earlier did not store whether the
                // registry value existed. On supported Windows installations the
                // saved array represents an existing PagingFiles value.
                backup.PagingFilesValueExisted = true;
            }
            RestoreCore(backup);
            File.Delete(BackupPath);
            LogService.Write("Restored previous page-file configuration.");
            return true;
        }

        private static VirtualMemoryBackup ReadCurrent()
        {
            string[] pagingFiles = new string[0];
            bool valueExisted = false;
            using (RegistryKey key = Registry.LocalMachine.OpenSubKey(MemoryKeyPath))
            {
                if (key != null)
                {
                    object raw = key.GetValue("PagingFiles", null, RegistryValueOptions.DoNotExpandEnvironmentNames);
                    valueExisted = raw != null;
                    pagingFiles = raw as string[] ?? new string[0];
                }
            }
            return new VirtualMemoryBackup
            {
                FormatVersion = 2,
                PagingFiles = pagingFiles,
                PagingFilesValueExisted = valueExisted,
                AutomaticManaged = GetAutomaticManaged()
            };
        }

        private static void WritePagingFiles(string[] entries)
        {
            WritePagingFiles(entries, true);
        }

        private static void WritePagingFiles(string[] entries, bool valueShouldExist)
        {
            using (RegistryKey key = Registry.LocalMachine.OpenSubKey(MemoryKeyPath, true))
            {
                if (key == null) throw new InvalidOperationException(LocalizationService.Get("PagefileUnavailable"));
                if (valueShouldExist)
                {
                    key.SetValue("PagingFiles", entries, RegistryValueKind.MultiString);
                }
                else
                {
                    key.DeleteValue("PagingFiles", false);
                }
                key.Flush();
            }
        }

        private static void VerifyPagingFiles(string[] expected, bool valueShouldExist)
        {
            using (RegistryKey key = Registry.LocalMachine.OpenSubKey(MemoryKeyPath))
            {
                if (key == null) throw new InvalidOperationException(LocalizationService.Get("PagefileUnavailable"));
                object raw = key.GetValue("PagingFiles", null, RegistryValueOptions.DoNotExpandEnvironmentNames);
                if (!valueShouldExist)
                {
                    if (raw != null) throw new InvalidOperationException(LocalizationService.Get("PagefileUnavailable"));
                    return;
                }

                string[] actual = raw as string[] ?? new string[0];
                if (!EntriesEqual(expected, actual))
                {
                    throw new InvalidOperationException(LocalizationService.Get("PagefileUnavailable"));
                }
            }
        }

        private static bool EntriesEqual(string[] left, string[] right)
        {
            if (left == null) left = new string[0];
            if (right == null) right = new string[0];
            if (left.Length != right.Length) return false;
            List<string> leftValues = new List<string>(left);
            List<string> rightValues = new List<string>(right);
            leftValues.Sort(StringComparer.OrdinalIgnoreCase);
            rightValues.Sort(StringComparer.OrdinalIgnoreCase);
            for (int index = 0; index < leftValues.Count; index++)
            {
                if (!string.Equals(NormalizeEntry(leftValues[index]), NormalizeEntry(rightValues[index]), StringComparison.OrdinalIgnoreCase))
                    return false;
            }
            return true;
        }

        private static string NormalizeEntry(string value)
        {
            return string.Join(" ", (value ?? string.Empty).Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries));
        }

        private static void RestoreCore(VirtualMemoryBackup backup)
        {
            WritePagingFiles(backup.PagingFiles ?? new string[0], backup.PagingFilesValueExisted);
            SetAutomaticManaged(backup.AutomaticManaged);
            VerifyPagingFiles(backup.PagingFiles ?? new string[0], backup.PagingFilesValueExisted);
            if (GetAutomaticManaged() != backup.AutomaticManaged)
            {
                throw new InvalidOperationException(LocalizationService.Get("PagefileUnavailable"));
            }
        }

        private static void TryRestore(VirtualMemoryBackup backup)
        {
            try
            {
                RestoreCore(backup);
            }
            catch (Exception ex)
            {
                LogService.Write("Virtual-memory rollback failed: " + ex);
            }
        }

        private static bool GetAutomaticManaged()
        {
            try
            {
                using (ManagementObjectSearcher searcher = CreateComputerSystemSearcher("SELECT AutomaticManagedPagefile FROM Win32_ComputerSystem"))
                {
                    foreach (ManagementObject item in searcher.Get())
                    {
                        using (item)
                        {
                            object value = item["AutomaticManagedPagefile"];
                            if (value is bool) return (bool)value;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogService.Write("Automatic page-file status read failed; trying WMIC: " + ex.Message);
                bool fallback;
                if (TryReadAutomaticManagedWithWmic(out fallback)) return fallback;
                throw new InvalidOperationException(LocalizationService.Get("PagefileUnavailable"), ex);
            }
            throw new InvalidOperationException(LocalizationService.Get("PagefileUnavailable"));
        }

        private static void SetAutomaticManaged(bool enabled)
        {
            try
            {
                using (ManagementObjectSearcher searcher = CreateComputerSystemSearcher("SELECT * FROM Win32_ComputerSystem"))
                {
                    foreach (ManagementObject item in searcher.Get())
                    {
                        using (item)
                        {
                            item["AutomaticManagedPagefile"] = enabled;
                            item.Put();
                            return;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                LogService.Write("Automatic page-file update failed; trying WMIC: " + ex.Message);
                if (TrySetAutomaticManagedWithWmic(enabled)) return;
                throw new InvalidOperationException(LocalizationService.Get("PagefileUnavailable"), ex);
            }
            throw new InvalidOperationException(LocalizationService.Get("PagefileUnavailable"));
        }

        private static ManagementObjectSearcher CreateComputerSystemSearcher(string query)
        {
            ManagementObjectSearcher searcher = new ManagementObjectSearcher(query);
            searcher.Options.ReturnImmediately = false;
            searcher.Options.Timeout = ManagementTimeout;
            return searcher;
        }

        private static bool TryReadAutomaticManagedWithWmic(out bool enabled)
        {
            enabled = true;
            string output;
            if (!TryRunWmic("computersystem get AutomaticManagedPagefile /value", out output)) return false;
            int separator = output.IndexOf('=');
            if (separator < 0) return false;
            return bool.TryParse(output.Substring(separator + 1).Trim(), out enabled);
        }

        private static bool TrySetAutomaticManagedWithWmic(bool enabled)
        {
            string output;
            string value = enabled ? "True" : "False";
            string machine = Environment.MachineName.Replace("\"", string.Empty);
            if (!TryRunWmic("computersystem where name=\"" + machine + "\" set AutomaticManagedPagefile=" + value, out output))
                return false;
            bool actual;
            return TryReadAutomaticManagedWithWmic(out actual) && actual == enabled;
        }

        private static bool TryRunWmic(string arguments, out string output)
        {
            output = string.Empty;
            try
            {
                ProcessStartInfo startInfo = new ProcessStartInfo
                {
                    FileName = "wmic.exe",
                    Arguments = arguments,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                    WindowStyle = ProcessWindowStyle.Hidden
                };
                using (Process process = Process.Start(startInfo))
                {
                    if (process == null) return false;
                    output = process.StandardOutput.ReadToEnd();
                    string error = process.StandardError.ReadToEnd();
                    if (!process.WaitForExit(30000))
                    {
                        try { process.Kill(); } catch { }
                        LogService.Write("WMIC virtual-memory operation timed out.");
                        return false;
                    }
                    if (process.ExitCode != 0)
                    {
                        LogService.Write("WMIC virtual-memory operation failed: " + error);
                        return false;
                    }
                    return true;
                }
            }
            catch (Exception ex)
            {
                LogService.Write("WMIC virtual-memory fallback failed: " + ex.Message);
                return false;
            }
        }

        private static void SaveBackup(VirtualMemoryBackup backup)
        {
            string directory = Path.GetDirectoryName(BackupPath);
            Directory.CreateDirectory(directory);
            using (FileStream stream = File.Create(BackupPath))
            {
                new XmlSerializer(typeof(VirtualMemoryBackup)).Serialize(stream, backup);
            }
        }

        private static string GetSystemDrive()
        {
            string root = Path.GetPathRoot(Environment.SystemDirectory);
            if (string.IsNullOrEmpty(root)) throw new InvalidOperationException(LocalizationService.Get("PagefileUnavailable"));
            return root;
        }

        private static bool IsSystemDriveEntry(string entry, string systemDrive)
        {
            string value = (entry ?? string.Empty).Trim().Trim('"');
            return value.StartsWith(systemDrive + "\\", StringComparison.OrdinalIgnoreCase)
                   && value.IndexOf("pagefile.sys", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private static bool TryReadFixedEntry(string entry, string systemDrive, out int sizeMb)
        {
            sizeMb = 0;
            string value = (entry ?? string.Empty).Trim().Trim('"');
            string prefix = systemDrive + "\\pagefile.sys ";
            if (!value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) return false;
            string[] parts = value.Substring(prefix.Length).Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            int initial;
            int maximum;
            if (parts.Length != 2 || !int.TryParse(parts[0], out initial) || !int.TryParse(parts[1], out maximum)) return false;
            if (initial != maximum) return false;
            if (initial != MaximumSizeMb && initial != MediumSizeMb && initial != MinimumSizeMb) return false;
            sizeMb = initial;
            return true;
        }

        public sealed class VirtualMemoryBackup
        {
            public int FormatVersion { get; set; }
            public string[] PagingFiles { get; set; }
            public bool PagingFilesValueExisted { get; set; }
            public bool AutomaticManaged { get; set; }
        }
    }
}
