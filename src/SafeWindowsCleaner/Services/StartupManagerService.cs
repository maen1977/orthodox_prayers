using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Microsoft.Win32;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class StartupManagerService
{
    private static readonly string ManagerRoot = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "SafeWindowsCleaner",
        "StartupManager");

    private static readonly string StatePath = Path.Combine(ManagerRoot, "state.json");
    private static readonly string DisabledStartupRoot = Path.Combine(ManagerRoot, "DisabledStartup");
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };
    private readonly SemaphoreSlim _stateLock = new(1, 1);

    private static readonly string[] RunKeyPaths =
    [
        @"Software\Microsoft\Windows\CurrentVersion\Run",
        @"Software\Microsoft\Windows\CurrentVersion\RunOnce"
    ];

    private static readonly HashSet<string> CriticalServices = new(StringComparer.OrdinalIgnoreCase)
    {
        "Appinfo", "BFE", "BrokerInfrastructure", "CoreMessagingRegistrar", "CryptSvc",
        "DcomLaunch", "Dhcp", "Dnscache", "EventLog", "EventSystem", "gpsvc",
        "LSM", "mpssvc", "NlaSvc", "nsi", "PlugPlay", "Power", "ProfSvc",
        "RpcEptMapper", "RpcSs", "SamSs", "Schedule", "SecurityHealthService",
        "SENS", "SystemEventsBroker", "Themes", "UserManager", "WinDefend",
        "Winmgmt", "WlanSvc", "wscsvc"
    };

    public async Task<List<StartupItem>> GetStartupItemsAsync(IProgress<string>? progress = null)
    {
        return await Task.Run(async () =>
        {
            StartupManagerState state = await LoadStateAsync();
            List<StartupItem> items = [];

            progress?.Report("قراءة عناصر بدء التشغيل من الريجستري...");
            ReadRegistryItems(items, state);

            progress?.Report("قراءة مجلدات بدء التشغيل...");
            ReadStartupFolderItems(items, state);

            progress?.Report("قراءة المهام المجدولة...");
            try
            {
                items.AddRange(await ReadScheduledTasksAsync());
            }
            catch (Exception ex)
            {
                AppLogger.Error("Failed to enumerate scheduled tasks.", ex);
            }

            progress?.Report("قراءة الخدمات...");
            try
            {
                items.AddRange(await ReadServicesAsync(state));
            }
            catch (Exception ex)
            {
                AppLogger.Error("Failed to enumerate services.", ex);
            }

            return items
                .GroupBy(item => item.Id, StringComparer.OrdinalIgnoreCase)
                .Select(group => group.First())
                .OrderBy(item => item.Category, StringComparer.CurrentCulture)
                .ThenByDescending(item => item.IsEnabled)
                .ThenBy(item => item.Name, StringComparer.CurrentCultureIgnoreCase)
                .ToList();
        });
    }

    public async Task<StartupOperationResult> DisableAsync(
        IEnumerable<StartupItem> startupItems,
        IProgress<string>? progress = null)
    {
        StartupOperationResult result = new();
        StartupManagerState state = await LoadStateAsync();

        foreach (StartupItem item in startupItems)
        {
            progress?.Report($"تعطيل: {item.Name}");
            if (!item.CanToggle || !item.IsEnabled)
            {
                result.SkippedItems++;
                continue;
            }

            try
            {
                bool changed = item.Kind switch
                {
                    StartupItemKind.Registry => await DisableRegistryItemAsync(item, state),
                    StartupItemKind.StartupFolder => await DisableStartupFileAsync(item, state),
                    StartupItemKind.ScheduledTask => await DisableScheduledTaskAsync(item),
                    StartupItemKind.Service => await DisableServiceAsync(item, state),
                    _ => false
                };

                if (changed)
                {
                    result.SucceededItems++;
                    await SaveStateAsync(state);
                    AppLogger.Info($"Startup item disabled: {item.Kind} | {item.Name} | {item.Location}");
                }
                else
                {
                    result.SkippedItems++;
                }
            }
            catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)
            {
                result.SkippedItems++;
                AppLogger.Info($"User canceled elevation while disabling startup item: {item.Name}");
            }
            catch (Exception ex)
            {
                result.FailedItems++;
                AppLogger.Error($"Failed to disable startup item: {item.Name}", ex);
            }
        }

        return result;
    }

    public async Task<StartupOperationResult> EnableAsync(
        IEnumerable<StartupItem> startupItems,
        IProgress<string>? progress = null)
    {
        StartupOperationResult result = new();
        StartupManagerState state = await LoadStateAsync();

        foreach (StartupItem item in startupItems)
        {
            progress?.Report($"إعادة تفعيل: {item.Name}");
            if (!item.CanToggle || item.IsEnabled)
            {
                result.SkippedItems++;
                continue;
            }

            try
            {
                bool changed = item.Kind switch
                {
                    StartupItemKind.Registry => await EnableRegistryItemAsync(item, state),
                    StartupItemKind.StartupFolder => await EnableStartupFileAsync(item, state),
                    StartupItemKind.ScheduledTask => await EnableScheduledTaskAsync(item),
                    StartupItemKind.Service => await EnableServiceAsync(item, state),
                    _ => false
                };

                if (changed)
                {
                    result.SucceededItems++;
                    await SaveStateAsync(state);
                    AppLogger.Info($"Startup item enabled: {item.Kind} | {item.Name} | {item.Location}");
                }
                else
                {
                    result.SkippedItems++;
                }
            }
            catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)
            {
                result.SkippedItems++;
                AppLogger.Info($"User canceled elevation while enabling startup item: {item.Name}");
            }
            catch (Exception ex)
            {
                result.FailedItems++;
                AppLogger.Error($"Failed to enable startup item: {item.Name}", ex);
            }
        }

        return result;
    }

    private static void ReadRegistryItems(List<StartupItem> items, StartupManagerState state)
    {
        HashSet<string> activeIds = new(StringComparer.OrdinalIgnoreCase);
        (RegistryHive Hive, RegistryView View)[] locations =
        [
            (RegistryHive.CurrentUser, RegistryView.Default),
            (RegistryHive.LocalMachine, RegistryView.Registry64),
            (RegistryHive.LocalMachine, RegistryView.Registry32)
        ];

        foreach ((RegistryHive hive, RegistryView view) in locations)
        {
            foreach (string keyPath in RunKeyPaths)
            {
                try
                {
                    using RegistryKey baseKey = RegistryKey.OpenBaseKey(hive, view);
                    using RegistryKey? key = baseKey.OpenSubKey(keyPath, writable: false);
                    if (key is null)
                    {
                        continue;
                    }

                    foreach (string valueName in key.GetValueNames())
                    {
                        object? rawValue = key.GetValue(valueName, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
                        if (rawValue is not string command || string.IsNullOrWhiteSpace(command))
                        {
                            continue;
                        }

                        string id = BuildRegistryId(hive, view, keyPath, valueName);
                        activeIds.Add(id);

                        string executablePath = TryExtractExecutablePath(command);
                        (string publisher, string signature) = GetFileTrustDetails(executablePath);
                        bool protectedItem = IsWindowsSystemExecutable(executablePath);

                        items.Add(new StartupItem
                        {
                            Id = id,
                            Name = string.IsNullOrWhiteSpace(valueName) ? "(القيمة الافتراضية)" : valueName,
                            Kind = StartupItemKind.Registry,
                            Category = "@Registry",
                            Command = command,
                            Location = $"{HiveText(hive)} — {Path.GetFileName(keyPath)} ({ViewText(view)})",
                            Publisher = publisher,
                            SignatureStatus = signature,
                            ExecutablePath = executablePath,
                            IsEnabled = true,
                            CanToggle = !protectedItem,
                            ProtectionReason = protectedItem ? "محمي لأنه يشغّل ملفًا من نظام ويندوز" : string.Empty,
                            SourceA = hive.ToString(),
                            SourceB = view.ToString(),
                            SourceC = keyPath,
                            SourceD = valueName
                        });
                    }
                }
                catch (Exception ex)
                {
                    AppLogger.Error($"Failed to read registry startup key: {hive} {view} {keyPath}", ex);
                }
            }
        }

        foreach (DisabledRegistryEntry entry in state.DisabledRegistryEntries)
        {
            if (activeIds.Contains(entry.Id) || !IsValidRegistryBackup(entry))
            {
                continue;
            }

            string executablePath = TryExtractExecutablePath(entry.ValueData);
            (string publisher, string signature) = GetFileTrustDetails(executablePath);
            bool protectedItem = IsWindowsSystemExecutable(executablePath);

            items.Add(new StartupItem
            {
                Id = entry.Id,
                Name = string.IsNullOrWhiteSpace(entry.ValueName) ? "(القيمة الافتراضية)" : entry.ValueName,
                Kind = StartupItemKind.Registry,
                Category = "@Registry",
                Command = entry.ValueData,
                Location = $"{HiveText(ParseHive(entry.Hive))} — {Path.GetFileName(entry.KeyPath)} ({ViewText(ParseView(entry.View))})",
                Publisher = publisher,
                SignatureStatus = signature,
                ExecutablePath = executablePath,
                IsEnabled = false,
                CanToggle = !protectedItem,
                ProtectionReason = protectedItem ? "محمي لأنه يشغّل ملفًا من نظام ويندوز" : string.Empty,
                SourceA = entry.Hive,
                SourceB = entry.View,
                SourceC = entry.KeyPath,
                SourceD = entry.ValueName
            });
        }
    }

    private static void ReadStartupFolderItems(List<StartupItem> items, StartupManagerState state)
    {
        string[] startupFolders =
        [
            Environment.GetFolderPath(Environment.SpecialFolder.Startup),
            Environment.GetFolderPath(Environment.SpecialFolder.CommonStartup)
        ];

        foreach (string startupFolder in startupFolders.Where(Directory.Exists))
        {
            IEnumerable<string> files;
            try
            {
                files = Directory.EnumerateFiles(startupFolder, "*", SearchOption.TopDirectoryOnly).ToList();
            }
            catch (Exception ex)
            {
                AppLogger.Error($"Failed to read startup folder: {startupFolder}", ex);
                continue;
            }

            foreach (string file in files)
            {
                FileAttributes attributes;
                try
                {
                    attributes = File.GetAttributes(file);
                }
                catch
                {
                    continue;
                }

                bool protectedItem = attributes.HasFlag(FileAttributes.ReparsePoint);
                string executablePath = Path.GetExtension(file).Equals(".exe", StringComparison.OrdinalIgnoreCase)
                    ? file
                    : string.Empty;
                (string publisher, string signature) = GetFileTrustDetails(executablePath);

                items.Add(new StartupItem
                {
                    Id = $"startup-file:{NormalizePath(file)}",
                    Name = Path.GetFileNameWithoutExtension(file),
                    Kind = StartupItemKind.StartupFolder,
                    Category = "@StartupFolder",
                    Command = file,
                    Location = IsPathUnder(file, Environment.GetFolderPath(Environment.SpecialFolder.CommonStartup))
                        ? "بدء التشغيل — جميع المستخدمين"
                        : "بدء التشغيل — المستخدم الحالي",
                    Publisher = publisher,
                    SignatureStatus = signature,
                    ExecutablePath = executablePath,
                    IsEnabled = true,
                    CanToggle = !protectedItem,
                    ProtectionReason = protectedItem ? "رابط ملفات خاص؛ لن يتم نقله تلقائيًا" : string.Empty,
                    SourceA = file
                });
            }
        }

        foreach (DisabledStartupFile entry in state.DisabledStartupFiles)
        {
            if (!File.Exists(entry.DisabledPath))
            {
                continue;
            }

            string executablePath = Path.GetExtension(entry.OriginalPath).Equals(".exe", StringComparison.OrdinalIgnoreCase)
                ? entry.DisabledPath
                : string.Empty;
            (string publisher, string signature) = GetFileTrustDetails(executablePath);

            items.Add(new StartupItem
            {
                Id = entry.Id,
                Name = Path.GetFileNameWithoutExtension(entry.OriginalPath),
                Kind = StartupItemKind.StartupFolder,
                Category = "@StartupFolder",
                Command = entry.OriginalPath,
                Location = IsPathUnder(entry.OriginalPath, Environment.GetFolderPath(Environment.SpecialFolder.CommonStartup))
                    ? "بدء التشغيل — جميع المستخدمين"
                    : "بدء التشغيل — المستخدم الحالي",
                Publisher = publisher,
                SignatureStatus = signature,
                ExecutablePath = executablePath,
                IsEnabled = false,
                CanToggle = true,
                SourceA = entry.OriginalPath,
                SourceB = entry.DisabledPath
            });
        }
    }

    private static async Task<List<StartupItem>> ReadScheduledTasksAsync()
    {
        const string script = "$ErrorActionPreference='Stop'; " +
                              "Get-ScheduledTask | ForEach-Object { " +
                              "$task=$_; $triggerTypes=@($task.Triggers | ForEach-Object { [string]$_.CimClass.CimClassName }); " +
                              "if ($triggerTypes -contains 'MSFT_TaskBootTrigger' -or $triggerTypes -contains 'MSFT_TaskLogonTrigger') { " +
                              "$actions=($task.Actions | ForEach-Object { (([string]$_.Execute)+' '+([string]$_.Arguments)).Trim() }) -join '; '; " +
                              "[PSCustomObject]@{Name=$task.TaskName;Path=$task.TaskPath;State=[string]$task.State;Actions=$actions;Author=[string]$task.Author;Triggers=($triggerTypes -join ',')} " +
                              "} } | ConvertTo-Json -Depth 4 -Compress";

        string json = await RunPowerShellForOutputAsync(script);
        List<ScheduledTaskRecord> records = DeserializeJsonList<ScheduledTaskRecord>(json);
        List<StartupItem> items = [];

        foreach (ScheduledTaskRecord task in records)
        {
            string taskPath = string.IsNullOrWhiteSpace(task.Path) ? @"\" : task.Path;
            bool enabled = !string.Equals(task.State, "Disabled", StringComparison.OrdinalIgnoreCase);
            bool protectedItem = taskPath.StartsWith(@"\Microsoft\Windows\", StringComparison.OrdinalIgnoreCase);
            string executablePath = TryExtractExecutablePath(task.Actions ?? string.Empty);
            (string publisher, string signature) = GetFileTrustDetails(executablePath);

            items.Add(new StartupItem
            {
                Id = $"task:{taskPath}{task.Name}",
                Name = task.Name ?? "مهمة بدون اسم",
                Kind = StartupItemKind.ScheduledTask,
                Category = "@ScheduledTasks",
                Command = task.Actions ?? string.Empty,
                Location = $"{taskPath} — {TranslateTaskTriggers(task.Triggers)}",
                Publisher = string.IsNullOrWhiteSpace(task.Author) ? publisher : task.Author!,
                SignatureStatus = signature,
                ExecutablePath = executablePath,
                IsEnabled = enabled,
                CanToggle = !protectedItem,
                ProtectionReason = protectedItem ? "مهمة تابعة لنظام ويندوز" : string.Empty,
                SourceA = task.Name ?? string.Empty,
                SourceB = taskPath
            });
        }

        return items;
    }

    private static async Task<List<StartupItem>> ReadServicesAsync(StartupManagerState state)
    {
        const string script = "$ErrorActionPreference='Stop'; " +
                              "Get-CimInstance Win32_Service | Where-Object { $_.ServiceType -notmatch 'Driver' } | " +
                              "Select-Object Name,DisplayName,PathName,StartMode,State | ConvertTo-Json -Depth 3 -Compress";

        string json = await RunPowerShellForOutputAsync(script);
        List<ServiceRecord> records = DeserializeJsonList<ServiceRecord>(json);
        List<StartupItem> items = [];

        foreach (ServiceRecord service in records)
        {
            if (string.IsNullOrWhiteSpace(service.Name))
            {
                continue;
            }

            ServiceRestoreState? restoreState = state.ServiceRestoreStates.FirstOrDefault(entry =>
                string.Equals(entry.ServiceName, service.Name, StringComparison.OrdinalIgnoreCase));
            bool startsAutomatically = string.Equals(service.StartMode, "Auto", StringComparison.OrdinalIgnoreCase);
            if (!startsAutomatically && restoreState is null)
            {
                continue;
            }

            string command = service.PathName ?? string.Empty;
            string executablePath = TryExtractExecutablePath(command);
            (string publisher, string signature) = GetFileTrustDetails(executablePath);
            int startValue = ReadServiceStartValue(service.Name);
            bool protectedItem = CriticalServices.Contains(service.Name)
                                 || startValue is 0 or 1
                                 || IsWindowsSystemExecutable(executablePath);
            bool enabled = !string.Equals(service.StartMode, "Disabled", StringComparison.OrdinalIgnoreCase);

            items.Add(new StartupItem
            {
                Id = $"service:{service.Name}",
                Name = string.IsNullOrWhiteSpace(service.DisplayName) ? service.Name : service.DisplayName!,
                Kind = StartupItemKind.Service,
                Category = "@Services",
                Command = command,
                Location = $"{service.Name} — الحالة الحالية: {TranslateServiceState(service.State)}",
                Publisher = publisher,
                SignatureStatus = signature,
                ExecutablePath = executablePath,
                IsEnabled = enabled,
                CanToggle = !protectedItem,
                ProtectionReason = protectedItem ? "خدمة نظام حساسة أو تعمل من مجلد ويندوز" : string.Empty,
                SourceA = service.Name,
                SourceB = service.StartMode ?? "Manual",
                SourceC = restoreState?.StartMode ?? string.Empty
            });
        }

        return items;
    }

    private async Task<bool> DisableRegistryItemAsync(StartupItem item, StartupManagerState state)
    {
        RegistryHive hive = ParseHive(item.SourceA);
        RegistryView view = ParseView(item.SourceB);

        using RegistryKey baseKey = RegistryKey.OpenBaseKey(hive, view);
        using RegistryKey? readKey = baseKey.OpenSubKey(item.SourceC, writable: false);
        if (readKey is null)
        {
            return false;
        }

        object? rawValue = readKey.GetValue(item.SourceD, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
        if (rawValue is not string valueData)
        {
            return false;
        }

        RegistryValueKind valueKind = readKey.GetValueKind(item.SourceD);
        DisabledRegistryEntry backup = new()
        {
            Id = item.Id,
            Hive = hive.ToString(),
            View = view.ToString(),
            KeyPath = item.SourceC,
            ValueName = item.SourceD,
            ValueData = valueData,
            ValueKind = valueKind.ToString(),
            DisabledAt = DateTimeOffset.UtcNow
        };

        if (hive == RegistryHive.CurrentUser)
        {
            using RegistryKey? writeKey = baseKey.OpenSubKey(item.SourceC, writable: true);
            if (writeKey is null)
            {
                return false;
            }

            writeKey.DeleteValue(item.SourceD, throwOnMissingValue: false);
        }
        else
        {
            string registryPath = $"HKLM\\{item.SourceC}";
            string registrySwitch = view == RegistryView.Registry32 ? "/reg:32" : "/reg:64";
            string valueSelector = string.IsNullOrEmpty(item.SourceD)
                ? "/ve"
                : $"/v {PowerShellLiteral(item.SourceD)}";
            string script = $"& reg.exe delete {PowerShellLiteral(registryPath)} {valueSelector} /f {registrySwitch}; " +
                            "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }";
            await RunElevatedPowerShellAsync(script);
        }

        state.DisabledRegistryEntries.RemoveAll(entry => string.Equals(entry.Id, item.Id, StringComparison.OrdinalIgnoreCase));
        state.DisabledRegistryEntries.Add(backup);
        return true;
    }

    private async Task<bool> EnableRegistryItemAsync(StartupItem item, StartupManagerState state)
    {
        DisabledRegistryEntry? backup = state.DisabledRegistryEntries.FirstOrDefault(entry =>
            string.Equals(entry.Id, item.Id, StringComparison.OrdinalIgnoreCase));
        if (backup is null || !IsValidRegistryBackup(backup))
        {
            return false;
        }

        RegistryHive hive = ParseHive(backup.Hive);
        RegistryView view = ParseView(backup.View);
        RegistryValueKind kind = Enum.TryParse(backup.ValueKind, out RegistryValueKind parsedKind)
            ? parsedKind
            : RegistryValueKind.String;

        if (hive == RegistryHive.CurrentUser)
        {
            using RegistryKey baseKey = RegistryKey.OpenBaseKey(hive, view);
            using RegistryKey writeKey = baseKey.CreateSubKey(backup.KeyPath, writable: true);
            writeKey.SetValue(backup.ValueName, backup.ValueData, kind);
        }
        else
        {
            string registryPath = $"HKLM\\{backup.KeyPath}";
            string registrySwitch = view == RegistryView.Registry32 ? "/reg:32" : "/reg:64";
            string registryType = kind == RegistryValueKind.ExpandString ? "REG_EXPAND_SZ" : "REG_SZ";
            string valueSelector = string.IsNullOrEmpty(backup.ValueName)
                ? "/ve"
                : $"/v {PowerShellLiteral(backup.ValueName)}";
            string script = $"& reg.exe add {PowerShellLiteral(registryPath)} {valueSelector} " +
                            $"/t {registryType} /d {PowerShellLiteral(backup.ValueData)} /f {registrySwitch}; " +
                            "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }";
            await RunElevatedPowerShellAsync(script);
        }

        state.DisabledRegistryEntries.Remove(backup);
        return true;
    }

    private static async Task<bool> DisableStartupFileAsync(StartupItem item, StartupManagerState state)
    {
        string originalPath = Path.GetFullPath(item.SourceA);
        if (!File.Exists(originalPath) || !IsDirectChildOfStartupFolder(originalPath))
        {
            return false;
        }

        FileAttributes attributes = File.GetAttributes(originalPath);
        if (attributes.HasFlag(FileAttributes.ReparsePoint))
        {
            return false;
        }

        string sessionDirectory = Path.Combine(DisabledStartupRoot, Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(sessionDirectory);
        string disabledPath = Path.Combine(sessionDirectory, Path.GetFileName(originalPath));

        if (IsPathUnder(originalPath, Environment.GetFolderPath(Environment.SpecialFolder.CommonStartup)))
        {
            string script = $"Move-Item -LiteralPath {PowerShellLiteral(originalPath)} -Destination {PowerShellLiteral(disabledPath)} -ErrorAction Stop";
            await RunElevatedPowerShellAsync(script);
        }
        else
        {
            File.Move(originalPath, disabledPath);
        }

        state.DisabledStartupFiles.RemoveAll(entry => string.Equals(entry.Id, item.Id, StringComparison.OrdinalIgnoreCase));
        state.DisabledStartupFiles.Add(new DisabledStartupFile
        {
            Id = item.Id,
            OriginalPath = originalPath,
            DisabledPath = disabledPath,
            DisabledAt = DateTimeOffset.UtcNow
        });
        return true;
    }

    private static async Task<bool> EnableStartupFileAsync(StartupItem item, StartupManagerState state)
    {
        DisabledStartupFile? backup = state.DisabledStartupFiles.FirstOrDefault(entry =>
            string.Equals(entry.Id, item.Id, StringComparison.OrdinalIgnoreCase));
        if (backup is null)
        {
            return false;
        }

        string disabledPath = backup.DisabledPath;
        string originalPath = backup.OriginalPath;
        if (!File.Exists(disabledPath) || File.Exists(originalPath))
        {
            return false;
        }

        if (!IsDirectChildOfStartupFolder(originalPath)
            || !IsPathUnder(disabledPath, DisabledStartupRoot))
        {
            return false;
        }

        string? parent = Path.GetDirectoryName(originalPath);
        if (string.IsNullOrWhiteSpace(parent))
        {
            return false;
        }

        Directory.CreateDirectory(parent);
        if (IsPathUnder(originalPath, Environment.GetFolderPath(Environment.SpecialFolder.CommonStartup)))
        {
            string script = $"Move-Item -LiteralPath {PowerShellLiteral(disabledPath)} -Destination {PowerShellLiteral(originalPath)} -ErrorAction Stop";
            await RunElevatedPowerShellAsync(script);
        }
        else
        {
            File.Move(disabledPath, originalPath);
        }

        TryDeleteEmptyDirectory(Path.GetDirectoryName(disabledPath));
        state.DisabledStartupFiles.Remove(backup);
        return true;
    }

    private static async Task<bool> DisableScheduledTaskAsync(StartupItem item)
    {
        string script = $"Get-ScheduledTask -TaskName {PowerShellLiteral(item.SourceA)} -TaskPath {PowerShellLiteral(item.SourceB)} " +
                        "-ErrorAction Stop | Disable-ScheduledTask -ErrorAction Stop | Out-Null";
        await RunElevatedPowerShellAsync(script);
        return true;
    }

    private static async Task<bool> EnableScheduledTaskAsync(StartupItem item)
    {
        string script = $"Get-ScheduledTask -TaskName {PowerShellLiteral(item.SourceA)} -TaskPath {PowerShellLiteral(item.SourceB)} " +
                        "-ErrorAction Stop | Enable-ScheduledTask -ErrorAction Stop | Out-Null";
        await RunElevatedPowerShellAsync(script);
        return true;
    }

    private static async Task<bool> DisableServiceAsync(StartupItem item, StartupManagerState state)
    {
        string serviceName = item.SourceA;
        ServiceRestoreState? existing = state.ServiceRestoreStates.FirstOrDefault(entry =>
            string.Equals(entry.ServiceName, serviceName, StringComparison.OrdinalIgnoreCase));

        ServiceRestoreState? pendingBackup = existing is null
            ? new ServiceRestoreState
            {
                ServiceName = serviceName,
                StartMode = NormalizeServiceStartMode(item.SourceB),
                DelayedAutoStart = ReadServiceDelayedAutoStart(serviceName)
            }
            : null;

        string script = $"Set-Service -Name {PowerShellLiteral(serviceName)} -StartupType Disabled -ErrorAction Stop";
        await RunElevatedPowerShellAsync(script);

        if (pendingBackup is not null)
        {
            state.ServiceRestoreStates.Add(pendingBackup);
        }

        return true;
    }

    private static async Task<bool> EnableServiceAsync(StartupItem item, StartupManagerState state)
    {
        string serviceName = item.SourceA;
        ServiceRestoreState? backup = state.ServiceRestoreStates.FirstOrDefault(entry =>
            string.Equals(entry.ServiceName, serviceName, StringComparison.OrdinalIgnoreCase));
        string startMode = NormalizeServiceStartMode(backup?.StartMode ?? "Manual");
        string startupType = startMode.Equals("Auto", StringComparison.OrdinalIgnoreCase)
            ? "Automatic"
            : "Manual";

        string script = $"Set-Service -Name {PowerShellLiteral(serviceName)} -StartupType {startupType} -ErrorAction Stop; ";
        if (startupType == "Automatic")
        {
            int delayedValue = backup?.DelayedAutoStart == true ? 1 : 0;
            string serviceRegistryPath = $@"Registry::HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\{serviceName}";
            script += $"New-ItemProperty -LiteralPath {PowerShellLiteral(serviceRegistryPath)} -Name 'DelayedAutoStart' -PropertyType DWord -Value {delayedValue} -Force -ErrorAction SilentlyContinue | Out-Null;";
        }

        await RunElevatedPowerShellAsync(script);
        if (backup is not null)
        {
            state.ServiceRestoreStates.Remove(backup);
        }

        return true;
    }

    private async Task<StartupManagerState> LoadStateAsync()
    {
        await _stateLock.WaitAsync();
        try
        {
            Directory.CreateDirectory(ManagerRoot);
            if (!File.Exists(StatePath))
            {
                return new StartupManagerState();
            }

            string json = await File.ReadAllTextAsync(StatePath, Encoding.UTF8);
            StartupManagerState? state = JsonSerializer.Deserialize<StartupManagerState>(json, JsonOptions);
            return state ?? new StartupManagerState();
        }
        catch (Exception ex)
        {
            AppLogger.Error("Failed to load startup manager state.", ex);
            return new StartupManagerState();
        }
        finally
        {
            _stateLock.Release();
        }
    }

    private async Task SaveStateAsync(StartupManagerState state)
    {
        await _stateLock.WaitAsync();
        try
        {
            Directory.CreateDirectory(ManagerRoot);
            string temporaryPath = StatePath + ".tmp";
            string json = JsonSerializer.Serialize(state, JsonOptions);
            await File.WriteAllTextAsync(temporaryPath, json, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
            File.Move(temporaryPath, StatePath, overwrite: true);
        }
        finally
        {
            _stateLock.Release();
        }
    }

    private static async Task<string> RunPowerShellForOutputAsync(string script)
    {
        script = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); $OutputEncoding=[Console]::OutputEncoding; " + script;

        using Process process = new();
        process.StartInfo = new ProcessStartInfo
        {
            FileName = "powershell.exe",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
            CreateNoWindow = true
        };
        process.StartInfo.ArgumentList.Add("-NoProfile");
        process.StartInfo.ArgumentList.Add("-NonInteractive");
        process.StartInfo.ArgumentList.Add("-ExecutionPolicy");
        process.StartInfo.ArgumentList.Add("Bypass");
        process.StartInfo.ArgumentList.Add("-EncodedCommand");
        process.StartInfo.ArgumentList.Add(EncodePowerShell(script));

        process.Start();
        Task<string> outputTask = process.StandardOutput.ReadToEndAsync();
        Task<string> errorTask = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync();
        string output = await outputTask;
        string error = await errorTask;

        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException($"PowerShell exited with code {process.ExitCode}: {error}");
        }

        return output.Trim().TrimStart('\uFEFF');
    }

    private static async Task RunElevatedPowerShellAsync(string script)
    {
        using Process? process = Process.Start(new ProcessStartInfo
        {
            FileName = "powershell.exe",
            Arguments = $"-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand {EncodePowerShell(script)}",
            UseShellExecute = true,
            Verb = "runas",
            WindowStyle = ProcessWindowStyle.Hidden
        });

        if (process is null)
        {
            throw new InvalidOperationException("تعذر تشغيل عملية الصلاحيات الإدارية.");
        }

        await process.WaitForExitAsync();
        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException($"فشلت العملية الإدارية برمز {process.ExitCode}.");
        }
    }

    private static List<T> DeserializeJsonList<T>(string json)
    {
        if (string.IsNullOrWhiteSpace(json) || json.Equals("null", StringComparison.OrdinalIgnoreCase))
        {
            return [];
        }

        using JsonDocument document = JsonDocument.Parse(json);
        return document.RootElement.ValueKind switch
        {
            JsonValueKind.Array => JsonSerializer.Deserialize<List<T>>(json, JsonOptions) ?? [],
            JsonValueKind.Object => [JsonSerializer.Deserialize<T>(json, JsonOptions)!],
            _ => []
        };
    }

    private static string TryExtractExecutablePath(string command)
    {
        if (string.IsNullOrWhiteSpace(command))
        {
            return string.Empty;
        }

        string expanded = Environment.ExpandEnvironmentVariables(command.Trim());
        if (expanded.StartsWith(@"\SystemRoot\", StringComparison.OrdinalIgnoreCase))
        {
            expanded = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), expanded[12..]);
        }

        string candidate;
        if (expanded.StartsWith('"'))
        {
            int quoteEnd = expanded.IndexOf('"', 1);
            candidate = quoteEnd > 1 ? expanded[1..quoteEnd] : expanded.Trim('"');
        }
        else
        {
            int executableEnd = expanded.IndexOf(".exe", StringComparison.OrdinalIgnoreCase);
            candidate = executableEnd >= 0
                ? expanded[..(executableEnd + 4)]
                : expanded.Split(' ', StringSplitOptions.RemoveEmptyEntries).FirstOrDefault() ?? string.Empty;
        }

        candidate = candidate.Trim().Trim('"');
        if (candidate.StartsWith(@"\??\", StringComparison.OrdinalIgnoreCase))
        {
            candidate = candidate[4..];
        }

        if (File.Exists(candidate))
        {
            return Path.GetFullPath(candidate);
        }

        if (!Path.IsPathRooted(candidate))
        {
            string systemCandidate = Path.Combine(Environment.SystemDirectory, candidate);
            if (File.Exists(systemCandidate))
            {
                return systemCandidate;
            }
        }

        return string.Empty;
    }

    private static (string Publisher, string Signature) GetFileTrustDetails(string executablePath)
    {
        if (string.IsNullOrWhiteSpace(executablePath) || !File.Exists(executablePath))
        {
            return ("غير معروف", "غير معروف");
        }

        string publisher = "غير معروف";
        try
        {
            FileVersionInfo versionInfo = FileVersionInfo.GetVersionInfo(executablePath);
            publisher = string.IsNullOrWhiteSpace(versionInfo.CompanyName) ? "غير معروف" : versionInfo.CompanyName!;
        }
        catch
        {
            // Keep the neutral value.
        }

        return HasValidAuthenticodeSignature(executablePath)
            ? (publisher, "توقيع صالح")
            : (publisher, "غير موثوق/غير موقّع");
    }

    private static bool HasValidAuthenticodeSignature(string filePath)
    {
        IntPtr filePathPointer = IntPtr.Zero;
        IntPtr fileInfoPointer = IntPtr.Zero;
        IntPtr trustDataPointer = IntPtr.Zero;

        try
        {
            filePathPointer = Marshal.StringToCoTaskMemUni(filePath);
            WinTrustFileInfo fileInfo = new()
            {
                StructSize = (uint)Marshal.SizeOf<WinTrustFileInfo>(),
                FilePath = filePathPointer,
                FileHandle = IntPtr.Zero,
                KnownSubject = IntPtr.Zero
            };

            fileInfoPointer = Marshal.AllocCoTaskMem(Marshal.SizeOf<WinTrustFileInfo>());
            Marshal.StructureToPtr(fileInfo, fileInfoPointer, fDeleteOld: false);

            WinTrustData trustData = new()
            {
                StructSize = (uint)Marshal.SizeOf<WinTrustData>(),
                PolicyCallbackData = IntPtr.Zero,
                SipClientData = IntPtr.Zero,
                UiChoice = 2, // WTD_UI_NONE
                RevocationChecks = 0, // WTD_REVOKE_NONE
                UnionChoice = 1, // WTD_CHOICE_FILE
                FileInfo = fileInfoPointer,
                StateAction = 0, // WTD_STATEACTION_IGNORE
                StateData = IntPtr.Zero,
                UrlReference = IntPtr.Zero,
                ProviderFlags = 0x00001000, // WTD_CACHE_ONLY_URL_RETRIEVAL
                UiContext = 0
            };

            trustDataPointer = Marshal.AllocCoTaskMem(Marshal.SizeOf<WinTrustData>());
            Marshal.StructureToPtr(trustData, trustDataPointer, fDeleteOld: false);

            Guid action = new("00AAC56B-CD44-11D0-8CC2-00C04FC295EE");
            return WinVerifyTrust(IntPtr.Zero, action, trustDataPointer) == 0;
        }
        catch
        {
            return false;
        }
        finally
        {
            if (trustDataPointer != IntPtr.Zero)
            {
                Marshal.FreeCoTaskMem(trustDataPointer);
            }

            if (fileInfoPointer != IntPtr.Zero)
            {
                Marshal.FreeCoTaskMem(fileInfoPointer);
            }

            if (filePathPointer != IntPtr.Zero)
            {
                Marshal.FreeCoTaskMem(filePathPointer);
            }
        }
    }

    private static bool IsWindowsSystemExecutable(string executablePath)
    {
        if (string.IsNullOrWhiteSpace(executablePath))
        {
            return false;
        }

        string windowsDirectory = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        return IsPathUnder(executablePath, windowsDirectory);
    }

    private static bool IsDirectChildOfStartupFolder(string path)
    {
        string? parent = Path.GetDirectoryName(Path.GetFullPath(path));
        if (string.IsNullOrWhiteSpace(parent))
        {
            return false;
        }

        string userStartup = Path.GetFullPath(Environment.GetFolderPath(Environment.SpecialFolder.Startup));
        string commonStartup = Path.GetFullPath(Environment.GetFolderPath(Environment.SpecialFolder.CommonStartup));
        return string.Equals(parent.TrimEnd(Path.DirectorySeparatorChar), userStartup.TrimEnd(Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase)
               || string.Equals(parent.TrimEnd(Path.DirectorySeparatorChar), commonStartup.TrimEnd(Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsPathUnder(string path, string root)
    {
        if (string.IsNullOrWhiteSpace(path) || string.IsNullOrWhiteSpace(root))
        {
            return false;
        }

        string fullPath = Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        string fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        return fullPath.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase);
    }

    private static string NormalizePath(string path)
        => Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar).ToUpperInvariant();

    private static bool IsValidRegistryBackup(DisabledRegistryEntry entry)
    {
        if (!Enum.TryParse(entry.Hive, out RegistryHive hive)
            || !Enum.TryParse(entry.View, out RegistryView view)
            || !RunKeyPaths.Contains(entry.KeyPath, StringComparer.OrdinalIgnoreCase))
        {
            return false;
        }

        bool supportedLocation = hive == RegistryHive.CurrentUser && view == RegistryView.Default
                                 || hive == RegistryHive.LocalMachine
                                    && view is RegistryView.Registry32 or RegistryView.Registry64;
        if (!supportedLocation)
        {
            return false;
        }

        if (!Enum.TryParse(entry.ValueKind, out RegistryValueKind kind)
            || kind is not RegistryValueKind.String and not RegistryValueKind.ExpandString)
        {
            return false;
        }

        return string.Equals(
            entry.Id,
            BuildRegistryId(hive, view, entry.KeyPath, entry.ValueName),
            StringComparison.OrdinalIgnoreCase);
    }

    private static string BuildRegistryId(RegistryHive hive, RegistryView view, string keyPath, string valueName)
        => $"registry:{hive}:{view}:{keyPath}:{valueName}";

    private static RegistryHive ParseHive(string value)
        => Enum.TryParse(value, out RegistryHive hive) ? hive : RegistryHive.CurrentUser;

    private static RegistryView ParseView(string value)
        => Enum.TryParse(value, out RegistryView view) ? view : RegistryView.Default;

    private static string HiveText(RegistryHive hive)
        => hive == RegistryHive.LocalMachine ? "كل المستخدمين" : "المستخدم الحالي";

    private static string ViewText(RegistryView view)
        => view switch
        {
            RegistryView.Registry32 => "32 بت",
            RegistryView.Registry64 => "64 بت",
            _ => "افتراضي"
        };

    private static string EncodePowerShell(string script)
        => Convert.ToBase64String(Encoding.Unicode.GetBytes(script));

    private static string PowerShellLiteral(string value)
        => "'" + value.Replace("'", "''", StringComparison.Ordinal) + "'";

    private static int ReadServiceStartValue(string serviceName)
    {
        try
        {
            using RegistryKey? key = Registry.LocalMachine.OpenSubKey($@"SYSTEM\CurrentControlSet\Services\{serviceName}");
            return key?.GetValue("Start") is int value ? value : -1;
        }
        catch
        {
            return -1;
        }
    }

    private static bool ReadServiceDelayedAutoStart(string serviceName)
    {
        try
        {
            using RegistryKey? key = Registry.LocalMachine.OpenSubKey($@"SYSTEM\CurrentControlSet\Services\{serviceName}");
            return key?.GetValue("DelayedAutoStart") is int value && value == 1;
        }
        catch
        {
            return false;
        }
    }

    private static string NormalizeServiceStartMode(string startMode)
        => startMode.Equals("Auto", StringComparison.OrdinalIgnoreCase)
           || startMode.Equals("Automatic", StringComparison.OrdinalIgnoreCase)
            ? "Auto"
            : "Manual";

    private static string TranslateTaskTriggers(string? triggers)
    {
        if (string.IsNullOrWhiteSpace(triggers))
        {
            return "تشغيل تلقائي";
        }

        List<string> labels = [];
        if (triggers.Contains("BootTrigger", StringComparison.OrdinalIgnoreCase))
        {
            labels.Add("بدء النظام");
        }

        if (triggers.Contains("LogonTrigger", StringComparison.OrdinalIgnoreCase))
        {
            labels.Add("تسجيل الدخول");
        }

        return labels.Count == 0 ? "تشغيل تلقائي" : string.Join(" + ", labels);
    }

    private static string TranslateServiceState(string? state)
        => state?.ToLowerInvariant() switch
        {
            "running" => "تعمل",
            "stopped" => "متوقفة",
            "start pending" => "قيد التشغيل",
            "stop pending" => "قيد الإيقاف",
            _ => state ?? "غير معروف"
        };

    private static void TryDeleteEmptyDirectory(string? directory)
    {
        if (string.IsNullOrWhiteSpace(directory))
        {
            return;
        }

        try
        {
            if (Directory.Exists(directory) && !Directory.EnumerateFileSystemEntries(directory).Any())
            {
                Directory.Delete(directory);
            }
        }
        catch
        {
            // Cleanup is best-effort only.
        }
    }

    [DllImport("wintrust.dll", ExactSpelling = true, SetLastError = true)]
    private static extern uint WinVerifyTrust(IntPtr windowHandle, [MarshalAs(UnmanagedType.LPStruct)] Guid actionId, IntPtr trustData);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WinTrustFileInfo
    {
        public uint StructSize;
        public IntPtr FilePath;
        public IntPtr FileHandle;
        public IntPtr KnownSubject;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WinTrustData
    {
        public uint StructSize;
        public IntPtr PolicyCallbackData;
        public IntPtr SipClientData;
        public uint UiChoice;
        public uint RevocationChecks;
        public uint UnionChoice;
        public IntPtr FileInfo;
        public uint StateAction;
        public IntPtr StateData;
        public IntPtr UrlReference;
        public uint ProviderFlags;
        public uint UiContext;
    }

    private sealed class StartupManagerState
    {
        public StartupManagerState() { }
        public List<DisabledRegistryEntry> DisabledRegistryEntries { get; set; } = [];
        public List<DisabledStartupFile> DisabledStartupFiles { get; set; } = [];
        public List<ServiceRestoreState> ServiceRestoreStates { get; set; } = [];
    }

    private sealed class DisabledRegistryEntry
    {
        public DisabledRegistryEntry() { }
        public string Id { get; set; } = string.Empty;
        public string Hive { get; set; } = string.Empty;
        public string View { get; set; } = string.Empty;
        public string KeyPath { get; set; } = string.Empty;
        public string ValueName { get; set; } = string.Empty;
        public string ValueData { get; set; } = string.Empty;
        public string ValueKind { get; set; } = RegistryValueKind.String.ToString();
        public DateTimeOffset DisabledAt { get; set; }
    }

    private sealed class DisabledStartupFile
    {
        public DisabledStartupFile() { }
        public string Id { get; set; } = string.Empty;
        public string OriginalPath { get; set; } = string.Empty;
        public string DisabledPath { get; set; } = string.Empty;
        public DateTimeOffset DisabledAt { get; set; }
    }

    private sealed class ServiceRestoreState
    {
        public ServiceRestoreState() { }
        public string ServiceName { get; set; } = string.Empty;
        public string StartMode { get; set; } = "Manual";
        public bool DelayedAutoStart { get; set; }
    }

    private sealed class ScheduledTaskRecord
    {
        public ScheduledTaskRecord() { }
        public string? Name { get; set; }
        public string? Path { get; set; }
        public string? State { get; set; }
        public string? Actions { get; set; }
        public string? Author { get; set; }
        public string? Triggers { get; set; }
    }

    private sealed class ServiceRecord
    {
        public ServiceRecord() { }
        public string Name { get; set; } = string.Empty;
        public string? DisplayName { get; set; }
        public string? PathName { get; set; }
        public string? StartMode { get; set; }
        public string? State { get; set; }
    }
}
