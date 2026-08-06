using System.Reflection;

namespace SafeWindowsCleaner.Services;

public static class BuildInfo
{
    public static Version Version { get; } = Assembly.GetEntryAssembly()?.GetName().Version ?? new Version(0, 0, 0, 0);

    public static string DisplayVersion => $"{Version.Major}.{Version.Minor}.{Math.Max(0, Version.Build)}";

    public static string EmbeddedGitHubRepository { get; } = ReadMetadata("GitHubRepository");

    private static string ReadMetadata(string key)
    {
        Assembly? assembly = Assembly.GetEntryAssembly();
        if (assembly is null)
        {
            return string.Empty;
        }

        return assembly.GetCustomAttributes<AssemblyMetadataAttribute>()
            .FirstOrDefault(attribute => string.Equals(attribute.Key, key, StringComparison.Ordinal))
            ?.Value?.Trim() ?? string.Empty;
    }
}
