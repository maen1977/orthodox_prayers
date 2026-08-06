using System;
using System.IO;
using System.Text;

namespace SafeWindowsCleaner.Win7.Services
{
    public static class LogService
    {
        private static readonly string DirectoryPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SafeWindowsCleaner", "Win7", "Logs");
        public static void Write(string message)
        {
            Directory.CreateDirectory(DirectoryPath);
            File.AppendAllText(Path.Combine(DirectoryPath, "activity.log"), DateTime.Now.ToString("s") + " " + message + Environment.NewLine, Encoding.UTF8);
        }
    }
}
