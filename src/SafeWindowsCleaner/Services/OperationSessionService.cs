using System.Text.Json;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class OperationSessionService
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    };

    private readonly SemaphoreSlim _gate = new(1, 1);

    public static string SessionsDirectory { get; } = Path.Combine(SettingsService.DataDirectory, "OperationSessions");

    public async Task<Guid> CreatePlanAsync(OperationPreview preview, CancellationToken cancellationToken = default)
    {
        var record = new OperationSessionRecord
        {
            Operation = preview.Operation,
            Description = preview.Description,
            PlannedItemCount = Math.Max(0, preview.ItemCount),
            EstimatedBytes = Math.Max(0, preview.EstimatedBytes),
            RequiresAdministrator = preview.RequiresAdministrator,
            Recoverable = preview.Items.Any(item => item.Action.Contains("الحجر", StringComparison.OrdinalIgnoreCase)
                                                     || item.Action.Contains("quarantine", StringComparison.OrdinalIgnoreCase)
                                                     || item.Action.Contains("تعطيل", StringComparison.OrdinalIgnoreCase)),
            Items = preview.Items.Take(2000).ToList()
        };
        await SaveAsync(record, cancellationToken);
        return record.SessionId;
    }

    public async Task UpdateStatusAsync(Guid sessionId, OperationSessionStatus status, string summary, CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken);
        try
        {
            string path = GetPath(sessionId);
            if (!File.Exists(path))
            {
                return;
            }

            OperationSessionRecord? record = JsonSerializer.Deserialize<OperationSessionRecord>(
                await File.ReadAllTextAsync(path, cancellationToken), JsonOptions);
            if (record is null)
            {
                return;
            }

            record.Status = status;
            record.Summary = (summary ?? string.Empty).Trim();
            record.UpdatedAtUtc = DateTimeOffset.UtcNow;
            await WriteAtomicAsync(path, record, cancellationToken);
        }
        finally
        {
            _gate.Release();
        }
    }

    public async Task<List<OperationSessionRecord>> GetRecentAsync(int maximum = 100, CancellationToken cancellationToken = default)
    {
        if (!Directory.Exists(SessionsDirectory))
        {
            return [];
        }

        var records = new List<OperationSessionRecord>();
        foreach (string path in Directory.EnumerateFiles(SessionsDirectory, "*.json", SearchOption.TopDirectoryOnly)
                     .OrderByDescending(File.GetLastWriteTimeUtc)
                     .Take(Math.Clamp(maximum, 1, 1000)))
        {
            try
            {
                OperationSessionRecord? record = JsonSerializer.Deserialize<OperationSessionRecord>(
                    await File.ReadAllTextAsync(path, cancellationToken), JsonOptions);
                if (record is not null)
                {
                    records.Add(record);
                }
            }
            catch (Exception ex)
            {
                AppLogger.Error($"Could not read operation session: {path}", ex);
            }
        }

        return records.OrderByDescending(record => record.UpdatedAtUtc).ToList();
    }

    private async Task SaveAsync(OperationSessionRecord record, CancellationToken cancellationToken)
    {
        await _gate.WaitAsync(cancellationToken);
        try
        {
            Directory.CreateDirectory(SessionsDirectory);
            await WriteAtomicAsync(GetPath(record.SessionId), record, cancellationToken);
        }
        finally
        {
            _gate.Release();
        }
    }

    private static async Task WriteAtomicAsync(string path, OperationSessionRecord record, CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        string temporary = path + ".tmp";
        await File.WriteAllTextAsync(temporary, JsonSerializer.Serialize(record, JsonOptions), cancellationToken);
        File.Move(temporary, path, true);
    }

    private static string GetPath(Guid sessionId) => Path.Combine(SessionsDirectory, sessionId.ToString("N") + ".json");
}
