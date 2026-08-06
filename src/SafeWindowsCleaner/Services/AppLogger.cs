using System.Text;

namespace SafeWindowsCleaner.Services;

public static class AppLogger
{
    private static readonly object Sync = new();
    public static string LogDirectory { get; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "SafeWindowsCleaner",
        "Logs");

    public static string CurrentLogPath { get; } = Path.Combine(LogDirectory, $"cleaner-{DateTime.Now:yyyy-MM-dd}.log");

    public static void Info(string message) => Write("INFO", message, null);
    public static void Error(string message, Exception? exception = null) => Write("ERROR", message, exception);

    private static void Write(string level, string message, Exception? exception)
    {
        try
        {
            Directory.CreateDirectory(LogDirectory);
            var builder = new StringBuilder();
            builder.Append($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [{level}] {message}");
            if (exception is not null)
            {
                builder.AppendLine();
                builder.Append(exception);
            }

            builder.AppendLine();

            lock (Sync)
            {
                File.AppendAllText(CurrentLogPath, builder.ToString(), Encoding.UTF8);
            }
        }
        catch
        {
            // Logging must never crash the application.
        }
    }
}
