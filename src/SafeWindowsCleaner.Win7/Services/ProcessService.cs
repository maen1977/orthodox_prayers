using SafeWindowsCleaner.Win7.Models;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;

namespace SafeWindowsCleaner.Win7.Services
{
    public sealed class ProcessService
    {
        private static readonly string[] ProtectedNames = { "explorer", "dwm", "winlogon", "csrss", "lsass", "services", "svchost", "smss", "wininit", "system", "taskmgr", "safewindowscleaner" };

        public List<ProcessItem> GetHeavyUserApps()
        {
            int sessionId = Process.GetCurrentProcess().SessionId;
            List<ProcessItem> items = new List<ProcessItem>();
            foreach (Process process in Process.GetProcesses())
            {
                using (process)
                {
                    try
                    {
                        if (process.SessionId != sessionId || process.Id == Process.GetCurrentProcess().Id) continue;
                        if (ProtectedNames.Any(x => string.Equals(x, process.ProcessName, StringComparison.OrdinalIgnoreCase))) continue;
                        if (string.IsNullOrWhiteSpace(process.MainWindowTitle)) continue;
                        long memory = process.PrivateMemorySize64;
                        if (memory < 25L * 1024L * 1024L) continue;
                        items.Add(new ProcessItem
                        {
                            ProcessId = process.Id,
                            Name = process.ProcessName,
                            WindowTitle = process.MainWindowTitle,
                            MemoryBytes = memory
                        });
                    }
                    catch { }
                }
            }
            return items.OrderByDescending(x => x.MemoryBytes).ToList();
        }

        public bool RequestClose(ProcessItem item)
        {
            if (item == null) return false;
            try
            {
                using (Process process = Process.GetProcessById(item.ProcessId))
                {
                    if (process.SessionId != Process.GetCurrentProcess().SessionId) return false;
                    if (ProtectedNames.Any(x => string.Equals(x, process.ProcessName, StringComparison.OrdinalIgnoreCase))) return false;
                    return process.CloseMainWindow();
                }
            }
            catch { return false; }
        }
    }
}
