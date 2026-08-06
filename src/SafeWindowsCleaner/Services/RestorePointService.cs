using System.ComponentModel;
using System.Runtime.InteropServices;

namespace SafeWindowsCleaner.Services;

public sealed class RestorePointService
{
    private const int BeginSystemChange = 100;
    private const int EndSystemChange = 101;
    private const int ApplicationUninstall = 1;
    private const int ModifySettings = 12;
    private const int CancelledOperation = 13;
    private const int MaximumDescriptionLength = 256;

    public Task<RestorePointSessionResult> BeginAsync(
        string description,
        bool uninstallOperation = false,
        CancellationToken cancellationToken = default)
    {
        return Task.Run(() => BeginCore(description, uninstallOperation), cancellationToken);
    }

    public RestorePointCompletionResult Complete(RestorePointSession session, bool cancelled)
        => CompleteCore(session, cancelled);

    public Task<RestorePointCompletionResult> CompleteAsync(
        RestorePointSession session,
        bool cancelled,
        CancellationToken cancellationToken = default)
    {
        return Task.Run(() => CompleteCore(session, cancelled), cancellationToken);
    }

    private static RestorePointSessionResult BeginCore(string description, bool uninstallOperation)
    {
        if (!OperatingSystem.IsWindows())
        {
            return new(false, null, "نقاط الاستعادة متاحة على ويندوز فقط.", 0);
        }

        string normalizedDescription = string.IsNullOrWhiteSpace(description)
            ? "Safe Windows Cleaner — Before Change"
            : description.Trim();
        if (normalizedDescription.Length >= MaximumDescriptionLength)
        {
            normalizedDescription = normalizedDescription[..(MaximumDescriptionLength - 1)];
        }

        var info = new RestorePointInfo
        {
            EventType = BeginSystemChange,
            RestorePointType = uninstallOperation ? ApplicationUninstall : ModifySettings,
            SequenceNumber = 0,
            Description = normalizedDescription
        };

        bool success = SRSetRestorePoint(ref info, out StateManagerStatus status);
        if (!success || status.Status != 0 || status.SequenceNumber <= 0)
        {
            int error = status.Status != 0 ? status.Status : Marshal.GetLastWin32Error();
            return new(false, null, BuildFailureMessage(error), error);
        }

        return new(true, new RestorePointSession(status.SequenceNumber, normalizedDescription, info.RestorePointType),
            $"تم إنشاء نقطة استعادة برقم {status.SequenceNumber}.", 0);
    }

    private static RestorePointCompletionResult CompleteCore(RestorePointSession session, bool cancelled)
    {
        var info = new RestorePointInfo
        {
            EventType = EndSystemChange,
            RestorePointType = cancelled ? CancelledOperation : session.RestorePointType,
            SequenceNumber = session.SequenceNumber,
            Description = session.Description
        };

        bool success = SRSetRestorePoint(ref info, out StateManagerStatus status);
        if (!success || status.Status != 0)
        {
            int error = status.Status != 0 ? status.Status : Marshal.GetLastWin32Error();
            return new(false, BuildFailureMessage(error), error);
        }

        return new(true, cancelled ? "تم إلغاء جلسة نقطة الاستعادة." : "تم إغلاق جلسة نقطة الاستعادة بنجاح.", 0);
    }

    private static string BuildFailureMessage(int error)
    {
        string details;
        try
        {
            details = error > 0 ? new Win32Exception(error).Message : "خطأ غير معروف";
        }
        catch
        {
            details = "خطأ غير معروف";
        }

        return error switch
        {
            5 => "تعذر إنشاء نقطة الاستعادة لأن العملية تحتاج إلى صلاحية مسؤول.",
            1058 => "خدمة استعادة النظام معطلة على هذا الجهاز.",
            _ => $"تعذر إنشاء أو إكمال نقطة الاستعادة: {details} (رمز {error})."
        };
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct RestorePointInfo
    {
        public int EventType;
        public int RestorePointType;
        public long SequenceNumber;

        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = MaximumDescriptionLength)]
        public string Description;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct StateManagerStatus
    {
        public int Status;
        public long SequenceNumber;
    }

    [DllImport("srclient.dll", CharSet = CharSet.Unicode, SetLastError = true, EntryPoint = "SRSetRestorePointW")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SRSetRestorePoint(ref RestorePointInfo restorePointInfo, out StateManagerStatus stateManagerStatus);
}

public sealed record RestorePointSession(long SequenceNumber, string Description, int RestorePointType);
public sealed record RestorePointSessionResult(bool Succeeded, RestorePointSession? Session, string Message, int ErrorCode);
public sealed record RestorePointCompletionResult(bool Succeeded, string Message, int ErrorCode);
