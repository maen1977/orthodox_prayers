using Microsoft.Win32;
using SafeWindowsCleaner.Win7.Models;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;

namespace SafeWindowsCleaner.Win7.Services
{
    public sealed class InstalledProgramService
    {
        private const string UninstallPath = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall";

        public List<InstalledProgram> GetPrograms()
        {
            List<InstalledProgram> programs = new List<InstalledProgram>();
            ReadHive(RegistryHive.LocalMachine, RegistryView.Registry64, programs);
            ReadHive(RegistryHive.LocalMachine, RegistryView.Registry32, programs);
            ReadHive(RegistryHive.CurrentUser, RegistryView.Default, programs);
            return programs
                .Where(x => !string.IsNullOrWhiteSpace(x.Name) && !string.IsNullOrWhiteSpace(x.UninstallCommand))
                .GroupBy(x => x.Name + "|" + x.UninstallCommand, StringComparer.OrdinalIgnoreCase)
                .Select(x => x.First())
                .OrderBy(x => x.Name, StringComparer.CurrentCultureIgnoreCase)
                .ToList();
        }

        public void RunUninstaller(InstalledProgram program)
        {
            if (program == null || string.IsNullOrWhiteSpace(program.UninstallCommand)) return;
            ProcessStartInfo start = new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = "/d /s /c \"" + program.UninstallCommand + "\"",
                UseShellExecute = false,
                CreateNoWindow = true,
                WorkingDirectory = Environment.GetFolderPath(Environment.SpecialFolder.System)
            };
            Process.Start(start);
        }

        private static void ReadHive(RegistryHive hive, RegistryView view, List<InstalledProgram> programs)
        {
            try
            {
                using (RegistryKey baseKey = RegistryKey.OpenBaseKey(hive, view))
                using (RegistryKey root = baseKey.OpenSubKey(UninstallPath))
                {
                    if (root == null) return;
                    foreach (string subName in root.GetSubKeyNames())
                    {
                        try
                        {
                            using (RegistryKey sub = root.OpenSubKey(subName))
                            {
                                if (sub == null) continue;
                                object systemComponent = sub.GetValue("SystemComponent");
                                if (systemComponent is int && (int)systemComponent == 1) continue;
                                string name = sub.GetValue("DisplayName") as string;
                                string command = sub.GetValue("QuietUninstallString") as string;
                                if (string.IsNullOrWhiteSpace(command)) command = sub.GetValue("UninstallString") as string;
                                if (string.IsNullOrWhiteSpace(name) || string.IsNullOrWhiteSpace(command)) continue;
                                programs.Add(new InstalledProgram
                                {
                                    Name = name.Trim(),
                                    Publisher = Convert.ToString(sub.GetValue("Publisher")),
                                    Version = Convert.ToString(sub.GetValue("DisplayVersion")),
                                    UninstallCommand = command.Trim()
                                });
                            }
                        }
                        catch { }
                    }
                }
            }
            catch { }
        }
    }
}
