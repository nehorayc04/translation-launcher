using System;
using System.Runtime.InteropServices;
using System.Text;

namespace BigLaunch.Interop;

/// <summary>Window activation helpers for the single-instance path.</summary>
public static class Focus
{
    private const int SW_RESTORE = 9;

    [DllImport("user32.dll")] private static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] private static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool AllowSetForegroundWindow(int pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr FindWindowW(string? cls, string? title);

    private const int ASFW_ANY = -1;

    /// <summary>
    /// Bring an already-running console to the front. Windows' focus-stealing
    /// prevention normally blocks this, so the EXITING process must first grant
    /// permission with AllowSetForegroundWindow — same trick the desktop
    /// launcher's single-instance guard uses.
    /// </summary>
    public static void RaiseExisting()
    {
        try
        {
            AllowSetForegroundWindow(ASFW_ANY);
            IntPtr h = FindWindowW(null, BigLaunchWindowTitle);
            if (h == IntPtr.Zero) return;
            if (IsIconic(h)) ShowWindow(h, SW_RESTORE);
            SetForegroundWindow(h);
        }
        catch { }
    }

    /// <summary>
    /// Bring a game we launched back to the front — the second half of Quick
    /// Resume. Un-suspending a process restores its threads but leaves it
    /// behind us on screen, which reads as "resume did nothing".
    /// </summary>
    public static void RaiseProcess(System.Diagnostics.Process p)
    {
        try
        {
            AllowSetForegroundWindow(ASFW_ANY);
            p.Refresh();
            IntPtr h = p.MainWindowHandle;
            if (h == IntPtr.Zero) return;
            if (IsIconic(h)) ShowWindow(h, SW_RESTORE);
            SetForegroundWindow(h);
        }
        catch { }
    }

    /// <summary>Must match MainWindow's Title exactly — it is the handle we find by.</summary>
    public const string BigLaunchWindowTitle = "Big Launch";
}
