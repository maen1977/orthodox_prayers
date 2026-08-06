using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using SafeWindowsCleaner.Models;

namespace SafeWindowsCleaner.Services;

public sealed class UpdateService
{
    private const long MaximumDownloadBytes = 512L * 1024L * 1024L;
    private static readonly HttpClient HttpClient = CreateHttpClient();

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public async Task<UpdateInfo?> CheckForUpdateAsync(
        string repository,
        Version currentVersion,
        CancellationToken cancellationToken = default)
    {
        string normalizedRepository = SettingsService.NormalizeRepository(repository);
        if (string.IsNullOrWhiteSpace(normalizedRepository))
        {
            throw new InvalidOperationException("أدخل المستودع بصيغة owner/repository داخل الإعدادات أولًا.");
        }

        Uri apiUri = new($"https://api.github.com/repos/{normalizedRepository}/releases/latest");
        using HttpResponseMessage response = await HttpClient.GetAsync(apiUri, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        response.EnsureSuccessStatusCode();

        await using Stream stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        GitHubRelease? release = await JsonSerializer.DeserializeAsync<GitHubRelease>(stream, JsonOptions, cancellationToken);
        if (release is null || string.IsNullOrWhiteSpace(release.TagName))
        {
            throw new InvalidDataException("تعذر قراءة معلومات الإصدار من GitHub.");
        }

        Version latestVersion = ParseVersion(release.TagName);
        if (latestVersion.CompareTo(currentVersion) <= 0)
        {
            return null;
        }

        List<GitHubAsset> assets = release.Assets ?? [];
        string targetArchitecture = Environment.Is64BitProcess ? "x64" : "x86";
        string? selectedSetupName = SelectSetupAssetName(
            assets.Select(asset => asset.Name),
            targetArchitecture,
            expectedVersion: latestVersion,
            allowLegacyNameFallback: Environment.Is64BitProcess);
        GitHubAsset? setup = selectedSetupName is null
            ? null
            : assets.FirstOrDefault(asset =>
                string.Equals(asset.Name, selectedSetupName, StringComparison.OrdinalIgnoreCase));

        if (setup is null)
        {
            throw new InvalidDataException(
                $"الإصدار الجديد لا يحتوي على مثبت Windows 10/11 بمعمارية {targetArchitecture} معتمد.");
        }

        string setupChecksumName = setup.Name + ".sha256";
        GitHubAsset? checksum = assets.FirstOrDefault(asset =>
            string.Equals(asset.Name, setupChecksumName, StringComparison.OrdinalIgnoreCase));
        checksum ??= assets.FirstOrDefault(asset =>
            asset.Name.Contains("SHA256", StringComparison.OrdinalIgnoreCase)
            && asset.Name.EndsWith(".txt", StringComparison.OrdinalIgnoreCase));

        if (checksum is null)
        {
            throw new InvalidDataException("لا يوجد ملف SHA-256 مرافق للمثبت؛ تم رفض التحديث لحماية المستخدم.");
        }

        return new UpdateInfo
        {
            TagName = release.TagName,
            Version = latestVersion,
            ReleasePageUrl = release.HtmlUrl,
            ReleaseNotes = string.IsNullOrWhiteSpace(release.Body) ? "لا توجد ملاحظات إصدار." : release.Body.Trim(),
            PublishedAt = release.PublishedAt,
            SetupAsset = ToAsset(setup),
            ChecksumAsset = ToAsset(checksum)
        };
    }


    public static string? SelectSetupAssetName(
        IEnumerable<string> assetNames,
        string targetArchitecture,
        Version? expectedVersion = null,
        bool allowLegacyNameFallback = false)
    {
        ArgumentNullException.ThrowIfNull(assetNames);

        string[] names = assetNames
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .ToArray();

        string architecture = string.Equals(targetArchitecture, "x64", StringComparison.OrdinalIgnoreCase)
            ? "x64"
            : string.Equals(targetArchitecture, "x86", StringComparison.OrdinalIgnoreCase)
                ? "x86"
                : throw new ArgumentOutOfRangeException(
                    nameof(targetArchitecture),
                    targetArchitecture,
                    "Only x64 and x86 update packages are supported.");

        string architectureSuffix = $"-Win10-11-{architecture}-Setup.exe";
        string? architectureMatch;
        if (expectedVersion is not null)
        {
            string versionText = expectedVersion.Build >= 0
                ? $"{expectedVersion.Major}.{expectedVersion.Minor}.{expectedVersion.Build}"
                : $"{expectedVersion.Major}.{expectedVersion.Minor}";
            string expectedName = $"SafeWindowsCleaner-{versionText}{architectureSuffix}";
            architectureMatch = names.FirstOrDefault(name =>
                string.Equals(name, expectedName, StringComparison.OrdinalIgnoreCase));
        }
        else
        {
            architectureMatch = names.FirstOrDefault(name =>
                name.StartsWith("SafeWindowsCleaner-", StringComparison.OrdinalIgnoreCase)
                && name.EndsWith(architectureSuffix, StringComparison.OrdinalIgnoreCase));
        }
        if (!string.IsNullOrWhiteSpace(architectureMatch))
        {
            return architectureMatch;
        }

        if (!allowLegacyNameFallback)
        {
            return null;
        }

        string[] legacyNames =
        [
            "SafeWindowsCleaner-Lite-Setup.exe",
            "SafeWindowsCleaner-Setup.exe"
        ];
        foreach (string legacyName in legacyNames)
        {
            string? match = names.FirstOrDefault(name =>
                string.Equals(name, legacyName, StringComparison.OrdinalIgnoreCase));
            if (!string.IsNullOrWhiteSpace(match))
            {
                return match;
            }
        }

        return null;
    }

    public async Task<PreparedUpdate> DownloadAndVerifyAsync(
        UpdateInfo update,
        IProgress<UpdateDownloadProgress>? progress = null,
        CancellationToken cancellationToken = default,
        bool requireSignedUpdate = true,
        string trustedPublisherThumbprint = "")
    {
        string updateDirectory = Path.Combine(
            SettingsService.DataDirectory,
            "Updates",
            SanitizeDirectoryName(update.TagName));
        Directory.CreateDirectory(updateDirectory);

        string installerPath = Path.Combine(updateDirectory, update.SetupAsset.Name);
        string checksumPath = Path.Combine(updateDirectory, update.ChecksumAsset.Name);

        await DownloadFileAsync(update.SetupAsset, installerPath, progress, cancellationToken);
        await DownloadFileAsync(update.ChecksumAsset, checksumPath, progress, cancellationToken);

        string expectedHash = ReadExpectedHash(await File.ReadAllTextAsync(checksumPath, cancellationToken), update.SetupAsset.Name);
        string actualHash = await ComputeSha256Async(installerPath, cancellationToken);
        if (!string.Equals(expectedHash, actualHash, StringComparison.OrdinalIgnoreCase))
        {
            TryDelete(installerPath);
            throw new InvalidDataException("فشلت مطابقة SHA-256. تم حذف ملف التحديث ورفض تشغيله.");
        }

        if (requireSignedUpdate)
        {
            string trusted = SettingsService.NormalizeThumbprint(trustedPublisherThumbprint);
            if (string.IsNullOrWhiteSpace(trusted))
            {
                trusted = AuthenticodeVerifier.GetCurrentPublisherThumbprint();
            }
            if (string.IsNullOrWhiteSpace(trusted))
            {
                TryDelete(installerPath);
                throw new InvalidDataException("لا يمكن تثبيت تحديث موقّع قبل تحديد بصمة شهادة الناشر أو تشغيل نسخة حالية موقّعة.");
            }

            AuthenticodeVerificationResult signature = AuthenticodeVerifier.Verify(installerPath, trusted);
            if (!signature.IsValid)
            {
                TryDelete(installerPath);
                throw new InvalidDataException("تم رفض التحديث لأن توقيعه الرقمي غير صالح أو لا يطابق ناشر البرنامج. " + signature.Message);
            }

            AppLogger.Info($"Update Authenticode signature verified: Subject={signature.Subject}, Thumbprint={signature.Thumbprint}");
        }

        AppLogger.Info($"Update verified successfully: {update.TagName}, SHA256={actualHash}");
        progress?.Report(new UpdateDownloadProgress("تم التحقق من سلامة التحديث.", update.SetupAsset.SizeBytes, update.SetupAsset.SizeBytes));
        return new PreparedUpdate(installerPath, update.TagName);
    }

    public static void LaunchInstaller(PreparedUpdate update)
    {
        if (!File.Exists(update.InstallerPath))
        {
            throw new FileNotFoundException("ملف التحديث غير موجود.", update.InstallerPath);
        }

        Process.Start(new ProcessStartInfo
        {
            FileName = update.InstallerPath,
            Arguments = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /NORESTARTAPPLICATIONS /RESTARTAPP=1",
            UseShellExecute = true,
            Verb = "runas"
        });
    }

    private static async Task DownloadFileAsync(
        UpdateAsset asset,
        string destinationPath,
        IProgress<UpdateDownloadProgress>? progress,
        CancellationToken cancellationToken)
    {
        EnsureAllowedDownloadUri(asset.DownloadUri);
        if (asset.SizeBytes > MaximumDownloadBytes)
        {
            throw new InvalidDataException("حجم ملف التحديث أكبر من الحد المسموح.");
        }

        using HttpResponseMessage response = await HttpClient.GetAsync(asset.DownloadUri, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        response.EnsureSuccessStatusCode();
        if (response.RequestMessage?.RequestUri is Uri finalUri)
        {
            EnsureAllowedDownloadUri(finalUri);
        }

        long? contentLength = response.Content.Headers.ContentLength;
        if (contentLength is > MaximumDownloadBytes)
        {
            throw new InvalidDataException("حجم ملف التحديث أكبر من الحد المسموح.");
        }

        string temporaryPath = destinationPath + ".download";
        TryDelete(temporaryPath);

        try
        {
            await using Stream source = await response.Content.ReadAsStreamAsync(cancellationToken);
            await using FileStream destination = new(
                temporaryPath,
                FileMode.CreateNew,
                FileAccess.Write,
                FileShare.None,
                81920,
                FileOptions.Asynchronous | FileOptions.SequentialScan);

            byte[] buffer = new byte[81920];
            long totalRead = 0;
            while (true)
            {
                int read = await source.ReadAsync(buffer.AsMemory(0, buffer.Length), cancellationToken);
                if (read == 0)
                {
                    break;
                }

                totalRead += read;
                if (totalRead > MaximumDownloadBytes)
                {
                    throw new InvalidDataException("تم تجاوز الحد الأقصى لحجم التحديث أثناء التنزيل.");
                }

                await destination.WriteAsync(buffer.AsMemory(0, read), cancellationToken);
                progress?.Report(new UpdateDownloadProgress($"تنزيل {asset.Name}...", totalRead, contentLength));
            }

            await destination.FlushAsync(cancellationToken);
            File.Move(temporaryPath, destinationPath, true);
        }
        catch
        {
            TryDelete(temporaryPath);
            throw;
        }
    }

    private static async Task<string> ComputeSha256Async(string path, CancellationToken cancellationToken)
    {
        await using FileStream stream = new(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            81920,
            FileOptions.Asynchronous | FileOptions.SequentialScan);
        byte[] hash = await SHA256.HashDataAsync(stream, cancellationToken);
        return Convert.ToHexString(hash).ToLowerInvariant();
    }

    private static string ReadExpectedHash(string checksumText, string assetName)
    {
        foreach (string line in checksumText.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            string[] parts = line.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length == 1 && IsSha256(parts[0]))
            {
                return parts[0].ToLowerInvariant();
            }

            if (parts.Length >= 2 && IsSha256(parts[0]))
            {
                string listedName = string.Join(' ', parts.Skip(1)).TrimStart('*');
                if (string.Equals(Path.GetFileName(listedName), assetName, StringComparison.OrdinalIgnoreCase))
                {
                    return parts[0].ToLowerInvariant();
                }
            }
        }

        throw new InvalidDataException("ملف البصمة لا يحتوي على SHA-256 صالح للمثبت.");
    }

    private static bool IsSha256(string value)
        => value.Length == 64 && value.All(Uri.IsHexDigit);

    private static UpdateAsset ToAsset(GitHubAsset asset)
    {
        if (!Uri.TryCreate(asset.BrowserDownloadUrl, UriKind.Absolute, out Uri? uri))
        {
            throw new InvalidDataException("رابط ملف الإصدار غير صالح.");
        }

        EnsureAllowedDownloadUri(uri);
        return new UpdateAsset { Name = asset.Name, DownloadUri = uri, SizeBytes = asset.Size };
    }

    private static void EnsureAllowedDownloadUri(Uri uri)
    {
        if (!string.Equals(uri.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException("يجب أن يستخدم رابط التحديث HTTPS.");
        }

        string host = uri.Host;
        bool allowed = string.Equals(host, "github.com", StringComparison.OrdinalIgnoreCase)
                       || string.Equals(host, "api.github.com", StringComparison.OrdinalIgnoreCase)
                       || host.EndsWith(".githubusercontent.com", StringComparison.OrdinalIgnoreCase);
        if (!allowed)
        {
            throw new InvalidDataException("مصدر ملف التحديث غير مسموح.");
        }
    }

    private static Version ParseVersion(string tag)
    {
        string normalized = tag.Trim().TrimStart('v', 'V');
        int suffixIndex = normalized.IndexOfAny(['-', '+']);
        if (suffixIndex >= 0)
        {
            normalized = normalized[..suffixIndex];
        }

        if (!Version.TryParse(normalized, out Version? version))
        {
            throw new InvalidDataException($"رقم إصدار GitHub غير صالح: {tag}");
        }

        return version;
    }

    private static string SanitizeDirectoryName(string value)
    {
        char[] invalid = Path.GetInvalidFileNameChars();
        return new string(value.Select(character => invalid.Contains(character) ? '_' : character).ToArray());
    }

    private static void TryDelete(string path)
    {
        try
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
        catch
        {
            // Best-effort cleanup only.
        }
    }

    private static HttpClient CreateHttpClient()
    {
        var handler = new HttpClientHandler
        {
            AllowAutoRedirect = true,
            MaxAutomaticRedirections = 5
        };
        var client = new HttpClient(handler)
        {
            Timeout = TimeSpan.FromMinutes(5)
        };
        client.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("SafeWindowsCleaner", BuildInfo.DisplayVersion));
        client.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/vnd.github+json"));
        client.DefaultRequestHeaders.Add("X-GitHub-Api-Version", "2022-11-28");
        return client;
    }

    private sealed class GitHubRelease
    {
        [JsonPropertyName("tag_name")]
        public string TagName { get; init; } = string.Empty;

        [JsonPropertyName("html_url")]
        public string HtmlUrl { get; init; } = string.Empty;

        [JsonPropertyName("body")]
        public string? Body { get; init; }

        [JsonPropertyName("published_at")]
        public DateTimeOffset? PublishedAt { get; init; }

        [JsonPropertyName("assets")]
        public List<GitHubAsset>? Assets { get; init; }
    }

    private sealed class GitHubAsset
    {
        [JsonPropertyName("name")]
        public string Name { get; init; } = string.Empty;

        [JsonPropertyName("browser_download_url")]
        public string BrowserDownloadUrl { get; init; } = string.Empty;

        [JsonPropertyName("size")]
        public long Size { get; init; }
    }
}
