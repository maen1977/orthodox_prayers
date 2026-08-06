using System.Diagnostics;
using System.Management;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Win32;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

/// <summary>
/// Configures a reversible Windows page file on the system drive. The service
/// selects the largest safe Lite preset (4, 8, or 16 GB) while leaving a
/// protected free-space reserve. It never presents disk space as physical RAM
/// or dedicated graphics memory.
/// </summary>
public sealed class VirtualMemoryService
{
    public const int FixedPageFileSizeMb = 16 * 1024;
    public const int MediumPageFileSizeMb = 8 * 1024;
    public const int MinimumPageFileSizeMb = 4 * 1024;
    public const long MinimumFreeBytesAfterApply = 8L * 1024L * 1024L * 1024L;

    private static readonly TimeSpan ManagementTimeout = TimeSpan.FromSeconds(20);
    private static readonly TimeSpan PowerShellTimeout = TimeSpan.FromSeconds(30);
    private const string MemoryManagementKeyPath = @"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management";
    private const string PagingFilesValueName = "PagingFiles";
    private static readonly Regex PagingFileEntryPattern = new(
        @"^\s*(?<path>.+?pagefile\.sys)\s+(?<initial>\d+)\s+(?<maximum>\d+)\s*$",
        RegexOptions.Compiled | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

    private static string BackupPath => Path.Combine(SettingsService.DataDirectory, "virtual-memory-backup.json");
    private static string RestartMarkerPath => Path.Combine(SettingsService.DataDirectory, "virtual-memory-restart-required.flag");

    public bool HasBackup => File.Exists(BackupPath);

    public async Task<VirtualMemoryStatus> GetStatusAsync(CancellationToken cancellationToken = default)
    {
        EnsureWindows();
        string systemDrive = GetSystemDrive();
        DriveInfo drive = new(systemDrive);
        RegistryPagingState registryState = ReadRegistryState();
        bool automatic = await GetAutomaticManagementAsync(cancellationToken);
        PagingFileConfiguration? configuration = registryState.Entries
            .Select(ParsePagingFileEntry)
            .FirstOrDefault(item => item is not null
                                    && string.Equals(
                                        Path.GetPathRoot(item.Path)?.TrimEnd('\\'),
                                        systemDrive.TrimEnd('\\'),
                                        StringComparison.OrdinalIgnoreCase));

        return new VirtualMemoryStatus(
            systemDrive,
            drive.AvailableFreeSpace,
            automatic,
            registryState.Entries,
            configuration,
            File.Exists(BackupPath),
            IsRestartRequired());
    }

    public static int GetRecommendedPageFileSizeMb(long availableFreeBytes)
    {
        int[] candidates = [FixedPageFileSizeMb, MediumPageFileSizeMb, MinimumPageFileSizeMb];
        foreach (int candidate in candidates)
        {
            long candidateBytes = candidate * 1024L * 1024L;
            if (availableFreeBytes - candidateBytes >= MinimumFreeBytesAfterApply)
            {
                return candidate;
            }
        }

        return 0;
    }

    public static bool IsLitePreset(PagingFileConfiguration? configuration)
    {
        if (configuration is null || configuration.InitialSizeMb != configuration.MaximumSizeMb)
        {
            return false;
        }

        return configuration.InitialSizeMb is FixedPageFileSizeMb
            or MediumPageFileSizeMb
            or MinimumPageFileSizeMb;
    }

    public async Task<VirtualMemoryStatus> ApplyRecommendedAsync(CancellationToken cancellationToken = default)
    {
        EnsureWindows();
        EnsureAdministrator();

        string systemDrive = GetSystemDrive();
        DriveInfo drive = new(systemDrive);
        if (!drive.IsReady)
        {
            throw new InvalidOperationException("The system drive is not ready.");
        }

        int selectedSizeMb = GetRecommendedPageFileSizeMb(drive.AvailableFreeSpace);
        if (selectedSizeMb == 0)
        {
            throw new InvalidOperationException("There is not enough free space to create a safe page-file preset while preserving the system-drive reserve.");
        }

        RegistryPagingState previousRegistryState = ReadRegistryState();
        bool previousAutomatic = await GetAutomaticManagementAsync(cancellationToken);
        await SaveBackupOnceAsync(previousAutomatic, previousRegistryState, cancellationToken);

        try
        {
            await SetAutomaticManagementAsync(false, cancellationToken);
            string pageFilePath = Path.Combine(systemDrive, "pagefile.sys");
            string systemRoot = systemDrive.TrimEnd('\\');
            var updatedEntries = previousRegistryState.Entries
                .Where(entry => ShouldPreserveOtherDriveEntry(entry, systemRoot))
                .ToList();
            updatedEntries.Add(BuildPagingFileEntry(pageFilePath, selectedSizeMb, selectedSizeMb));
            string[] expectedEntries = updatedEntries.ToArray();
            WritePagingFiles(expectedEntries);
            VerifyPagingFilesWritten(expectedEntries);
            await VerifyAutomaticManagementAsync(expected: false, cancellationToken);
            Directory.CreateDirectory(SettingsService.DataDirectory);
            await File.WriteAllTextAsync(RestartMarkerPath, DateTimeOffset.UtcNow.ToString("O"), cancellationToken);
        }
        catch
        {
            TryRestoreRegistryState(previousRegistryState);
            try
            {
                await SetAutomaticManagementAsync(previousAutomatic, CancellationToken.None);
            }
            catch (Exception rollbackException)
            {
                AppLogger.Error("Could not fully roll back automatic page-file management after a failed change.", rollbackException);
            }
            throw;
        }

        return await GetStatusAsync(cancellationToken);
    }

    // Retained for source compatibility with earlier 2.2 builds and tests.
    public Task<VirtualMemoryStatus> ApplyFixed16GbAsync(CancellationToken cancellationToken = default)
        => ApplyRecommendedAsync(cancellationToken);

    public async Task<bool> RestorePreviousIfAvailableAsync(CancellationToken cancellationToken = default)
    {
        if (!File.Exists(BackupPath))
        {
            return false;
        }

        await RestorePreviousAsync(cancellationToken);
        return true;
    }

    public async Task<VirtualMemoryStatus> RestorePreviousAsync(CancellationToken cancellationToken = default)
    {
        EnsureWindows();
        EnsureAdministrator();
        if (!File.Exists(BackupPath))
        {
            throw new InvalidOperationException("No saved virtual-memory setting is available to restore.");
        }

        string json = await File.ReadAllTextAsync(BackupPath, cancellationToken);
        VirtualMemoryBackup backup = JsonSerializer.Deserialize<VirtualMemoryBackup>(json, JsonOptions)
                                      ?? throw new InvalidOperationException("The saved virtual-memory backup is invalid.");

        var state = new RegistryPagingState(backup.PagingFilesValueExisted, backup.PagingFiles ?? []);
        TryRestoreRegistryState(state);
        VerifyRegistryStateRestored(state);
        await SetAutomaticManagementAsync(backup.AutomaticManagedPagefile, cancellationToken);
        await VerifyAutomaticManagementAsync(backup.AutomaticManagedPagefile, cancellationToken);
        Directory.CreateDirectory(SettingsService.DataDirectory);
        await File.WriteAllTextAsync(RestartMarkerPath, DateTimeOffset.UtcNow.ToString("O"), cancellationToken);
        File.Delete(BackupPath);
        return await GetStatusAsync(cancellationToken);
    }

    public Task<IReadOnlyList<GpuMemoryInfo>> GetGpuMemoryInfoAsync(CancellationToken cancellationToken = default)
    {
        EnsureWindows();
        return Task.Run<IReadOnlyList<GpuMemoryInfo>>(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();
            var result = new List<GpuMemoryInfo>();
            using var searcher = new ManagementObjectSearcher(
                "SELECT Name, AdapterRAM FROM Win32_VideoController");
            searcher.Options.ReturnImmediately = false;
            searcher.Options.Timeout = ManagementTimeout;
            using ManagementObjectCollection adapters = searcher.Get();
            foreach (ManagementObject adapter in adapters)
            {
                using (adapter)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    string name = Convert.ToString(adapter["Name"], System.Globalization.CultureInfo.InvariantCulture)?.Trim()
                                  ?? string.Empty;
                    long? bytes = null;
                    object? rawMemory = adapter["AdapterRAM"];
                    if (rawMemory is not null)
                    {
                        try
                        {
                            ulong raw = Convert.ToUInt64(rawMemory, System.Globalization.CultureInfo.InvariantCulture);
                            bytes = raw > long.MaxValue ? long.MaxValue : (long)raw;
                        }
                        catch (Exception ex) when (ex is FormatException or InvalidCastException or OverflowException)
                        {
                            AppLogger.Error("Display-adapter memory value could not be converted.", ex);
                        }
                    }

                    if (!string.IsNullOrWhiteSpace(name))
                    {
                        result.Add(new GpuMemoryInfo(name, bytes));
                    }
                }
            }

            return result;
        }, cancellationToken);
    }

    public static string BuildPagingFileEntry(string path, int initialSizeMb, int maximumSizeMb)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            throw new ArgumentException("A page-file path is required.", nameof(path));
        }
        if (initialSizeMb <= 0 || maximumSizeMb < initialSizeMb)
        {
            throw new ArgumentOutOfRangeException(nameof(initialSizeMb), "Page-file sizes must be positive and the maximum cannot be smaller than the initial size.");
        }

        return $"{Path.GetFullPath(path)} {initialSizeMb} {maximumSizeMb}";
    }

    public static PagingFileConfiguration? ParsePagingFileEntry(string? entry)
    {
        Match match = PagingFileEntryPattern.Match(entry ?? string.Empty);
        if (!match.Success
            || !int.TryParse(match.Groups["initial"].Value, out int initial)
            || !int.TryParse(match.Groups["maximum"].Value, out int maximum)
            || initial <= 0
            || maximum < initial)
        {
            return null;
        }

        string path = Environment.ExpandEnvironmentVariables(match.Groups["path"].Value.Trim().Trim('"'));
        try
        {
            return new PagingFileConfiguration(Path.GetFullPath(path), initial, maximum);
        }
        catch
        {
            return null;
        }
    }

    private static async Task<bool> GetAutomaticManagementAsync(CancellationToken cancellationToken)
    {
        try
        {
            return await ReadAutomaticManagementWithWmiAsync(cancellationToken);
        }
        catch (Exception wmiException) when (wmiException is not OperationCanceledException)
        {
            AppLogger.Error("Direct WMI page-file status query failed; trying the PowerShell compatibility path.", wmiException);
            string output = await RunPowerShellAsync(
                "$item = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop; [Console]::Out.Write([bool]$item.AutomaticManagedPagefile)",
                cancellationToken);
            if (bool.TryParse(output, out bool enabled))
            {
                return enabled;
            }

            throw new InvalidOperationException("Windows returned an invalid automatic page-file setting.", wmiException);
        }
    }

    private static async Task SetAutomaticManagementAsync(bool enabled, CancellationToken cancellationToken)
    {
        try
        {
            await WriteAutomaticManagementWithWmiAsync(enabled, cancellationToken);
        }
        catch (Exception wmiException) when (wmiException is not OperationCanceledException)
        {
            AppLogger.Error("Direct WMI page-file update failed; trying the PowerShell compatibility path.", wmiException);
            string value = enabled ? "$true" : "$false";
            string script =
                "$item = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop; " +
                "$item | Set-CimInstance -Property @{ AutomaticManagedPagefile = " + value + " } -ErrorAction Stop | Out-Null";
            await RunPowerShellAsync(script, cancellationToken);
        }
    }

    private static Task<bool> ReadAutomaticManagementWithWmiAsync(CancellationToken cancellationToken)
    {
        return Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();
            using ManagementObjectSearcher searcher = CreateComputerSystemSearcher(
                "SELECT AutomaticManagedPagefile FROM Win32_ComputerSystem");
            using ManagementObjectCollection results = searcher.Get();
            foreach (ManagementObject computer in results)
            {
                using (computer)
                {
                    if (computer["AutomaticManagedPagefile"] is bool enabled)
                    {
                        return enabled;
                    }
                }
            }

            throw new InvalidOperationException("Windows did not return the automatic page-file setting.");
        }, cancellationToken);
    }

    private static Task WriteAutomaticManagementWithWmiAsync(bool enabled, CancellationToken cancellationToken)
    {
        return Task.Run(() =>
        {
            cancellationToken.ThrowIfCancellationRequested();
            using ManagementObjectSearcher searcher = CreateComputerSystemSearcher(
                "SELECT * FROM Win32_ComputerSystem");
            using ManagementObjectCollection results = searcher.Get();
            foreach (ManagementObject computer in results)
            {
                using (computer)
                {
                    computer["AutomaticManagedPagefile"] = enabled;
                    computer.Put();
                    return;
                }
            }

            throw new InvalidOperationException("Windows did not expose a writable automatic page-file setting.");
        }, cancellationToken);
    }

    private static ManagementObjectSearcher CreateComputerSystemSearcher(string query)
    {
        var searcher = new ManagementObjectSearcher(query);
        searcher.Options.ReturnImmediately = false;
        searcher.Options.Timeout = ManagementTimeout;
        return searcher;
    }

    private static async Task VerifyAutomaticManagementAsync(bool expected, CancellationToken cancellationToken)
    {
        Exception? lastError = null;
        for (int attempt = 0; attempt < 3; attempt++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                bool actual = await GetAutomaticManagementAsync(cancellationToken);
                if (actual == expected)
                {
                    return;
                }

                lastError = new InvalidOperationException(
                    $"Windows reported AutomaticManagedPagefile={actual} after requesting {expected}.");
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                lastError = ex;
            }

            await Task.Delay(TimeSpan.FromMilliseconds(350), cancellationToken);
        }

        throw new InvalidOperationException("Windows did not confirm the requested automatic page-file setting.", lastError);
    }

    private static async Task SaveBackupOnceAsync(
        bool automaticManagedPagefile,
        RegistryPagingState registryState,
        CancellationToken cancellationToken)
    {
        if (File.Exists(BackupPath))
        {
            return;
        }

        Directory.CreateDirectory(SettingsService.DataDirectory);
        var backup = new VirtualMemoryBackup
        {
            CreatedAtUtc = DateTimeOffset.UtcNow,
            AutomaticManagedPagefile = automaticManagedPagefile,
            PagingFilesValueExisted = registryState.ValueExisted,
            PagingFiles = registryState.Entries
        };
        string temporaryPath = BackupPath + ".tmp";
        await File.WriteAllTextAsync(temporaryPath, JsonSerializer.Serialize(backup, JsonOptions), cancellationToken);
        File.Move(temporaryPath, BackupPath, true);
    }

    private static RegistryPagingState ReadRegistryState()
    {
        using RegistryKey baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, GetMachineRegistryView());
        using RegistryKey? key = baseKey.OpenSubKey(MemoryManagementKeyPath, writable: false);
        if (key is null)
        {
            throw new InvalidOperationException("Windows memory-management settings are unavailable.");
        }

        object? raw = key.GetValue(PagingFilesValueName, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
        return raw switch
        {
            string[] entries => new RegistryPagingState(true, entries.Where(value => !string.IsNullOrWhiteSpace(value)).ToArray()),
            string single when !string.IsNullOrWhiteSpace(single) => new RegistryPagingState(true, [single]),
            null => new RegistryPagingState(false, []),
            _ => throw new InvalidOperationException("The Windows PagingFiles registry value has an unsupported type.")
        };
    }

    private static void WritePagingFiles(string[] entries)
    {
        using RegistryKey baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, GetMachineRegistryView());
        using RegistryKey key = baseKey.OpenSubKey(MemoryManagementKeyPath, writable: true)
                                ?? throw new InvalidOperationException("Windows memory-management settings cannot be opened for writing.");
        key.SetValue(PagingFilesValueName, entries, RegistryValueKind.MultiString);
        key.Flush();
    }

    private static void VerifyPagingFilesWritten(string[] expectedEntries)
    {
        RegistryPagingState actual = ReadRegistryState();
        if (!actual.ValueExisted || !PagingFileEntriesEqual(expectedEntries, actual.Entries))
        {
            throw new InvalidOperationException("Windows did not retain the requested page-file registry setting.");
        }
    }

    private static void VerifyRegistryStateRestored(RegistryPagingState expected)
    {
        RegistryPagingState actual = ReadRegistryState();
        if (actual.ValueExisted != expected.ValueExisted
            || !PagingFileEntriesEqual(expected.Entries, actual.Entries))
        {
            throw new InvalidOperationException("Windows did not restore the saved page-file registry setting.");
        }
    }

    private static bool PagingFileEntriesEqual(IEnumerable<string> expected, IEnumerable<string> actual)
    {
        string[] left = expected.Select(NormalizePagingFileEntryForComparison)
            .Where(value => value.Length > 0)
            .OrderBy(value => value, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        string[] right = actual.Select(NormalizePagingFileEntryForComparison)
            .Where(value => value.Length > 0)
            .OrderBy(value => value, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        return left.SequenceEqual(right, StringComparer.OrdinalIgnoreCase);
    }

    private static string NormalizePagingFileEntryForComparison(string? entry)
        => Regex.Replace((entry ?? string.Empty).Trim(), @"\s+", " ");

    private static void TryRestoreRegistryState(RegistryPagingState state)
    {
        using RegistryKey baseKey = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, GetMachineRegistryView());
        using RegistryKey? key = baseKey.OpenSubKey(MemoryManagementKeyPath, writable: true);
        if (key is null)
        {
            return;
        }

        if (state.ValueExisted)
        {
            key.SetValue(PagingFilesValueName, state.Entries, RegistryValueKind.MultiString);
        }
        else
        {
            key.DeleteValue(PagingFilesValueName, throwOnMissingValue: false);
        }
        key.Flush();
    }

    private static RegistryView GetMachineRegistryView()
        => Environment.Is64BitOperatingSystem ? RegistryView.Registry64 : RegistryView.Registry32;

    private static bool ShouldPreserveOtherDriveEntry(string entry, string systemRoot)
    {
        string value = (entry ?? string.Empty).Trim();
        if (value.StartsWith("?:", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        PagingFileConfiguration? parsed = ParsePagingFileEntry(value);
        if (parsed is null)
        {
            // Preserve an unknown concrete entry rather than deleting a custom
            // configuration that the application does not understand.
            return !string.IsNullOrWhiteSpace(value);
        }

        string? root = Path.GetPathRoot(parsed.Path)?.TrimEnd('\\');
        return !string.Equals(root, systemRoot, StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsRestartRequired()
    {
        if (!File.Exists(RestartMarkerPath))
        {
            return false;
        }

        try
        {
            DateTime markerUtc = File.GetLastWriteTimeUtc(RestartMarkerPath);
            DateTime bootUtc = DateTime.UtcNow - TimeSpan.FromMilliseconds(Environment.TickCount64);
            if (markerUtc <= bootUtc)
            {
                File.Delete(RestartMarkerPath);
                return false;
            }
        }
        catch (Exception ex)
        {
            AppLogger.Error("Could not evaluate the virtual-memory restart marker.", ex);
        }

        return true;
    }

    private static string GetSystemDrive()
    {
        string root = Path.GetPathRoot(Environment.SystemDirectory)
                      ?? throw new InvalidOperationException("The Windows system drive could not be determined.");
        return root.EndsWith(Path.DirectorySeparatorChar) ? root : root + Path.DirectorySeparatorChar;
    }

    private static void EnsureWindows()
    {
        if (!OperatingSystem.IsWindows())
        {
            throw new PlatformNotSupportedException("Virtual-memory configuration is available only on Windows.");
        }
    }

    private static void EnsureAdministrator()
    {
        if (!ElevationService.IsAdministrator)
        {
            throw new UnauthorizedAccessException("Administrator privileges are required to change virtual memory.");
        }
    }

    private static async Task<string> RunPowerShellAsync(string script, CancellationToken cancellationToken)
    {
        string encoded = Convert.ToBase64String(Encoding.Unicode.GetBytes(script));
        var startInfo = new ProcessStartInfo
        {
            FileName = "powershell.exe",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
        startInfo.ArgumentList.Add("-NoLogo");
        startInfo.ArgumentList.Add("-NoProfile");
        startInfo.ArgumentList.Add("-NonInteractive");
        startInfo.ArgumentList.Add("-ExecutionPolicy");
        startInfo.ArgumentList.Add("Bypass");
        startInfo.ArgumentList.Add("-EncodedCommand");
        startInfo.ArgumentList.Add(encoded);

        using var process = new Process { StartInfo = startInfo };
        if (!process.Start())
        {
            throw new InvalidOperationException("PowerShell could not be started.");
        }

        Task<string> outputTask = process.StandardOutput.ReadToEndAsync();
        Task<string> errorTask = process.StandardError.ReadToEndAsync();
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(PowerShellTimeout);
        try
        {
            await process.WaitForExitAsync(timeout.Token);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                if (!process.HasExited)
                {
                    process.Kill(entireProcessTree: true);
                }
            }
            catch
            {
                // Best effort only; the timeout is still reported to the caller.
            }

            throw new TimeoutException("Windows PowerShell did not complete the virtual-memory operation within 30 seconds.");
        }

        string output = (await outputTask).Trim();
        string error = (await errorTask).Trim();
        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException(string.IsNullOrWhiteSpace(error)
                ? $"PowerShell exited with code {process.ExitCode}."
                : error);
        }

        return output;
    }

    private sealed record RegistryPagingState(bool ValueExisted, string[] Entries);
}
