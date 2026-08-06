using System.Runtime.InteropServices;

namespace SafeWindowsCleaner.Services;

public sealed record SystemMemorySnapshot(
    long TotalPhysicalBytes,
    long AvailablePhysicalBytes,
    int MemoryLoadPercent,
    DateTimeOffset CapturedAt)
{
    public long UsedPhysicalBytes => Math.Max(0, TotalPhysicalBytes - AvailablePhysicalBytes);
}

public sealed class SystemMemoryService
{
    public SystemMemorySnapshot Capture()
    {
        var status = new MemoryStatusEx
        {
            Length = checked((uint)Marshal.SizeOf<MemoryStatusEx>())
        };

        if (!GlobalMemoryStatusEx(ref status))
        {
            throw new InvalidOperationException($"GlobalMemoryStatusEx failed with Win32 error {Marshal.GetLastWin32Error()}.");
        }

        return new SystemMemorySnapshot(
            ToInt64Saturated(status.TotalPhysical),
            ToInt64Saturated(status.AvailablePhysical),
            checked((int)status.MemoryLoad),
            DateTimeOffset.UtcNow);
    }

    private static long ToInt64Saturated(ulong value)
        => value > long.MaxValue ? long.MaxValue : (long)value;

    [StructLayout(LayoutKind.Sequential)]
    private struct MemoryStatusEx
    {
        public uint Length;
        public uint MemoryLoad;
        public ulong TotalPhysical;
        public ulong AvailablePhysical;
        public ulong TotalPageFile;
        public ulong AvailablePageFile;
        public ulong TotalVirtual;
        public ulong AvailableVirtual;
        public ulong AvailableExtendedVirtual;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GlobalMemoryStatusEx(ref MemoryStatusEx buffer);
}
