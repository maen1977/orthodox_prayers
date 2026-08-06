namespace SafeWindowsCleaner.Win7.Models
{
    public sealed class InstalledProgram
    {
        public string Name { get; set; }
        public string Publisher { get; set; }
        public string Version { get; set; }
        public string UninstallCommand { get; set; }
        public string DisplayText { get { return string.IsNullOrWhiteSpace(Version) ? Name : Name + "  " + Version; } }
    }
}
