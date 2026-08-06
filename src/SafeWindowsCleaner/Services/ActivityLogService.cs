using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class ActivityLogService
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    private readonly SemaphoreSlim _gate = new(1, 1);

    public static string ActivityDirectory { get; } = Path.Combine(SettingsService.DataDirectory, "Activity");
    public static string ActivityPath { get; } = Path.Combine(ActivityDirectory, "activity.jsonl");

    public async Task<ActivityLogEntry> AppendAsync(
        string operation,
        string status,
        string summary,
        int itemCount = 0,
        long bytesAffected = 0,
        long restorePointSequence = 0,
        CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken);
        try
        {
            Directory.CreateDirectory(ActivityDirectory);
            List<ActivityLogEntry> entries = await ReadEntriesCoreAsync(cancellationToken);
            ActivityLogEntry? previous = entries.LastOrDefault();
            var entry = new ActivityLogEntry
            {
                Sequence = (previous?.Sequence ?? 0) + 1,
                TimestampUtc = DateTimeOffset.UtcNow,
                Operation = NormalizeText(operation, 120),
                Status = NormalizeText(status, 50),
                Summary = NormalizeText(summary, 1000),
                ItemCount = Math.Max(0, itemCount),
                BytesAffected = Math.Max(0, bytesAffected),
                RestorePointSequence = Math.Max(0, restorePointSequence),
                PreviousHash = previous?.Hash ?? string.Empty
            };
            entry.Hash = ComputeHash(entry);

            string line = JsonSerializer.Serialize(entry, JsonOptions) + Environment.NewLine;
            await File.AppendAllTextAsync(ActivityPath, line, Encoding.UTF8, cancellationToken);
            return entry;
        }
        finally
        {
            _gate.Release();
        }
    }

    public async Task<List<ActivityLogEntry>> GetEntriesAsync(int maximum = 1000, CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken);
        try
        {
            List<ActivityLogEntry> entries = await ReadEntriesCoreAsync(cancellationToken);
            return entries
                .OrderByDescending(entry => entry.Sequence)
                .Take(Math.Clamp(maximum, 1, 10000))
                .ToList();
        }
        finally
        {
            _gate.Release();
        }
    }

    public async Task<ActivityLogVerificationResult> VerifyAsync(CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken);
        try
        {
            List<ActivityLogEntry> entries = await ReadEntriesCoreAsync(cancellationToken);
            string expectedPreviousHash = string.Empty;
            long expectedSequence = 1;

            foreach (ActivityLogEntry entry in entries)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (entry.Sequence != expectedSequence)
                {
                    return new(false, entries.Count, $"تسلسل السجل غير صحيح عند العملية رقم {expectedSequence}.");
                }

                if (!string.Equals(entry.PreviousHash, expectedPreviousHash, StringComparison.OrdinalIgnoreCase))
                {
                    return new(false, entries.Count, $"سلسلة البصمات منقطعة عند العملية رقم {entry.Sequence}.");
                }

                string expectedHash = ComputeHash(entry);
                if (!CryptographicOperations.FixedTimeEquals(
                        Encoding.ASCII.GetBytes(expectedHash),
                        Encoding.ASCII.GetBytes(entry.Hash ?? string.Empty)))
                {
                    return new(false, entries.Count, $"تم اكتشاف تعديل أو تلف عند العملية رقم {entry.Sequence}.");
                }

                expectedPreviousHash = entry.Hash ?? string.Empty;
                expectedSequence++;
            }

            return new(true, entries.Count, entries.Count == 0
                ? "سجل النشاط فارغ."
                : $"سلسلة بصمات السجل سليمة لعدد {entries.Count:N0} عملية.");
        }
        catch (Exception ex)
        {
            AppLogger.Error("Activity log verification failed.", ex);
            return new(false, 0, "تعذر التحقق من سجل النشاط بسبب خطأ في القراءة.");
        }
        finally
        {
            _gate.Release();
        }
    }

    public static string ComputeHash(ActivityLogEntry entry)
    {
        string canonical = string.Join("\u001f",
            entry.Sequence.ToString(CultureInfo.InvariantCulture),
            entry.TimestampUtc.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture),
            entry.Operation ?? string.Empty,
            entry.Status ?? string.Empty,
            entry.Summary ?? string.Empty,
            entry.ItemCount.ToString(CultureInfo.InvariantCulture),
            entry.BytesAffected.ToString(CultureInfo.InvariantCulture),
            entry.RestorePointSequence.ToString(CultureInfo.InvariantCulture),
            entry.PreviousHash ?? string.Empty);

        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(canonical))).ToLowerInvariant();
    }

    private static async Task<List<ActivityLogEntry>> ReadEntriesCoreAsync(CancellationToken cancellationToken)
    {
        var entries = new List<ActivityLogEntry>();
        if (!File.Exists(ActivityPath))
        {
            return entries;
        }

        string[] lines = await File.ReadAllLinesAsync(ActivityPath, cancellationToken);
        foreach (string line in lines)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            try
            {
                ActivityLogEntry? entry = JsonSerializer.Deserialize<ActivityLogEntry>(line, JsonOptions);
                if (entry is not null)
                {
                    entries.Add(entry);
                }
            }
            catch (JsonException ex)
            {
                AppLogger.Error("Invalid activity log line detected.", ex);
                entries.Add(new ActivityLogEntry
                {
                    Sequence = long.MinValue,
                    TimestampUtc = DateTimeOffset.MinValue,
                    Operation = "سجل غير صالح",
                    Status = "@Corrupt",
                    Summary = "تعذر قراءة أحد أسطر سجل النشاط.",
                    Hash = "invalid"
                });
                break;
            }
        }

        return entries.OrderBy(entry => entry.Sequence).ToList();
    }

    private static string NormalizeText(string? value, int maximumLength)
    {
        string normalized = (value ?? string.Empty).Replace('\r', ' ').Replace('\n', ' ').Trim();
        return normalized.Length <= maximumLength ? normalized : normalized[..maximumLength];
    }
}
