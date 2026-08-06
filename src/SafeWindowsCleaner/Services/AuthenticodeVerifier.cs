using System.Runtime.InteropServices;
using System.Security.Cryptography.X509Certificates;

namespace SafeWindowsCleaner.Services;

public sealed record AuthenticodeVerificationResult(bool IsValid, string Subject, string Thumbprint, string Message);

public static class AuthenticodeVerifier
{
    private static readonly Guid GenericVerifyV2 = new("00AAC56B-CD44-11d0-8CC2-00C04FC295EE");

    public static AuthenticodeVerificationResult Verify(string filePath, string? trustedThumbprint = null)
    {
        if (!OperatingSystem.IsWindows())
        {
            return new(false, string.Empty, string.Empty, "Authenticode verification requires Windows.");
        }

        if (!File.Exists(filePath))
        {
            return new(false, string.Empty, string.Empty, "The signed file does not exist.");
        }

        uint status = VerifyTrust(filePath);
        if (status != 0)
        {
            return new(false, string.Empty, string.Empty, $"WinVerifyTrust rejected the signature (0x{status:X8}).");
        }

        try
        {
            using var certificate = new X509Certificate2(X509Certificate.CreateFromSignedFile(filePath));
            string thumbprint = SettingsService.NormalizeThumbprint(certificate.Thumbprint);
            string expected = SettingsService.NormalizeThumbprint(trustedThumbprint);
            if (!string.IsNullOrWhiteSpace(expected)
                && !string.Equals(thumbprint, expected, StringComparison.OrdinalIgnoreCase))
            {
                return new(false, certificate.Subject, thumbprint, "The update is signed, but not by the trusted publisher certificate.");
            }

            return new(true, certificate.Subject, thumbprint, "The Authenticode signature is valid.");
        }
        catch (Exception ex)
        {
            return new(false, string.Empty, string.Empty, "The signer certificate could not be read: " + ex.Message);
        }
    }

    public static string GetCurrentPublisherThumbprint()
    {
        try
        {
            string? path = Environment.ProcessPath;
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path) || !OperatingSystem.IsWindows())
            {
                return string.Empty;
            }

            using var certificate = new X509Certificate2(X509Certificate.CreateFromSignedFile(path));
            return SettingsService.NormalizeThumbprint(certificate.Thumbprint);
        }
        catch
        {
            return string.Empty;
        }
    }

    private static uint VerifyTrust(string filePath)
    {
        var fileInfo = new WinTrustFileInfo(filePath);
        IntPtr fileInfoPointer = IntPtr.Zero;
        IntPtr dataPointer = IntPtr.Zero;
        try
        {
            fileInfoPointer = Marshal.AllocHGlobal(Marshal.SizeOf<WinTrustFileInfo>());
            Marshal.StructureToPtr(fileInfo, fileInfoPointer, false);
            var data = new WinTrustData(fileInfoPointer);
            dataPointer = Marshal.AllocHGlobal(Marshal.SizeOf<WinTrustData>());
            Marshal.StructureToPtr(data, dataPointer, false);
            return WinVerifyTrust(IntPtr.Zero, GenericVerifyV2, dataPointer);
        }
        finally
        {
            if (dataPointer != IntPtr.Zero)
            {
                Marshal.DestroyStructure<WinTrustData>(dataPointer);
                Marshal.FreeHGlobal(dataPointer);
            }
            if (fileInfoPointer != IntPtr.Zero)
            {
                Marshal.DestroyStructure<WinTrustFileInfo>(fileInfoPointer);
                Marshal.FreeHGlobal(fileInfoPointer);
            }
        }
    }

    [DllImport("wintrust.dll", ExactSpelling = true, SetLastError = true)]
    private static extern uint WinVerifyTrust(IntPtr hwnd, [MarshalAs(UnmanagedType.LPStruct)] Guid actionId, IntPtr trustData);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WinTrustFileInfo
    {
        public uint cbStruct;
        [MarshalAs(UnmanagedType.LPWStr)] public string pcwszFilePath;
        public IntPtr hFile;
        public IntPtr pgKnownSubject;

        public WinTrustFileInfo(string path)
        {
            cbStruct = (uint)Marshal.SizeOf<WinTrustFileInfo>();
            pcwszFilePath = path;
            hFile = IntPtr.Zero;
            pgKnownSubject = IntPtr.Zero;
        }
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WinTrustData
    {
        public uint cbStruct;
        public IntPtr pPolicyCallbackData;
        public IntPtr pSIPClientData;
        public uint dwUIChoice;
        public uint fdwRevocationChecks;
        public uint dwUnionChoice;
        public IntPtr pFile;
        public uint dwStateAction;
        public IntPtr hWVTStateData;
        public IntPtr pwszURLReference;
        public uint dwProvFlags;
        public uint dwUIContext;
        public IntPtr pSignatureSettings;

        public WinTrustData(IntPtr fileInfo)
        {
            cbStruct = (uint)Marshal.SizeOf<WinTrustData>();
            pPolicyCallbackData = IntPtr.Zero;
            pSIPClientData = IntPtr.Zero;
            dwUIChoice = 2; // WTD_UI_NONE
            fdwRevocationChecks = 0; // WTD_REVOKE_NONE
            dwUnionChoice = 1; // WTD_CHOICE_FILE
            pFile = fileInfo;
            dwStateAction = 0; // WTD_STATEACTION_IGNORE
            hWVTStateData = IntPtr.Zero;
            pwszURLReference = IntPtr.Zero;
            dwProvFlags = 0x00000010; // WTD_CACHE_ONLY_URL_RETRIEVAL
            dwUIContext = 0;
            pSignatureSettings = IntPtr.Zero;
        }
    }
}
