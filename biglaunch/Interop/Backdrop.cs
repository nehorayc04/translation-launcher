using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using Microsoft.Win32;

namespace BigLaunch.Interop;

/// <summary>
/// The real Windows 11 acrylic/mica backdrop.
///
/// This is the SAME mechanism Winhanced's WinUI 3 shell uses underneath —
/// the backdrop is painted by DWM, not by the UI framework, so a WPF window
/// gets a pixel-identical material for free.
///
/// 🔴 The two hard-won rules (both cost a full round when broken):
///
///  1. DWMWA_SYSTEMBACKDROP_TYPE is a NO-OP on its own. The window must first
///     tell DWM to treat its whole client area as glass via
///     DwmExtendFrameIntoClientArea(MARGINS{-1,-1,-1,-1}). Without it every
///     call reports S_OK and nothing changes.
///
///  2. The window must NOT be layered. WPF's AllowsTransparency="True" sets
///     WS_EX_LAYERED, and a layered window is architecturally incompatible
///     with the DWM backdrop — you get a black rectangle while every API call
///     still succeeds. Keep AllowsTransparency="False" and instead make the
///     WPF composition target transparent (see <see cref="Apply"/>).
/// </summary>
public static class Backdrop
{
    private const int DWMWA_USE_IMMERSIVE_DARK_MODE = 20;
    private const int DWMWA_WINDOW_CORNER_PREFERENCE = 33;
    private const int DWMWA_BORDER_COLOR = 34;
    /// <summary>DWMWA_COLOR_NONE - "draw no border at all", not "draw a black one".</summary>
    private const int DWMWA_COLOR_NONE = unchecked((int)0xFFFFFFFE);
    private const int DWMWA_SYSTEMBACKDROP_TYPE = 38;

    // DWM_SYSTEMBACKDROP_TYPE
    public const int BACKDROP_AUTO = 0;
    public const int BACKDROP_NONE = 1;
    public const int BACKDROP_MICA = 2;
    public const int BACKDROP_ACRYLIC = 3;   // DWMSBT_TRANSIENTWINDOW
    public const int BACKDROP_MICA_ALT = 4;

    [StructLayout(LayoutKind.Sequential)]
    private struct MARGINS { public int L, R, T, B; }

    [DllImport("dwmapi.dll")]
    private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int value, int size);

    [DllImport("dwmapi.dll")]
    private static extern int DwmExtendFrameIntoClientArea(IntPtr hwnd, ref MARGINS m);

    /// <summary>
    /// Apply the backdrop to a window. Best-effort: on a machine where DWM
    /// declines (older build, composition off, a remote session) the shell
    /// still renders correctly against its own opaque ground colour.
    /// </summary>
    public static bool Apply(Window window, int type = BACKDROP_ACRYLIC)
    {
        try
        {
            var src = (HwndSource?)PresentationSource.FromVisual(window);
            if (src is null) return false;
            IntPtr hwnd = src.Handle;

            // WPF paints an opaque ground behind everything unless the
            // composition target itself is transparent. This is the
            // WPF-specific half of the recipe and is easy to miss.
            if (src.CompositionTarget is not null)
                src.CompositionTarget.BackgroundColor = Colors.Transparent;

            int dark = 1;
            DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ref dark, sizeof(int));

            // (1) hand the whole client area to DWM — REQUIRED
            var m = new MARGINS { L = -1, R = -1, T = -1, B = -1 };
            DwmExtendFrameIntoClientArea(hwnd, ref m);

            // (2) now the backdrop request is meaningful
            int t = type;
            int hr = DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ref t, sizeof(int));

            // 🔴 WINDOWS 11 DRAWS A BORDER ON EVERY WINDOW, INCLUDING WindowStyle=None.
            // That is the hairline frame running round the whole shell. It is not
            // ours and no XAML can reach it - it is composited by DWM outside the
            // client area - so the only way to be rid of it is to tell DWM not to
            // draw one. A 10ft shell fills the screen; a frame around the screen
            // is a frame around nothing, and it is the one pixel that gives away
            // that this is a desktop window rather than a console.
            int none = DWMWA_COLOR_NONE;
            DwmSetWindowAttribute(hwnd, DWMWA_BORDER_COLOR, ref none, sizeof(int));

            // Square corners for the same reason: rounded ones cut the art at the
            // four corners of a full-screen shell and read as part of that frame.
            int square = 1; // DWMWCP_DONOTROUND
            DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ref square, sizeof(int));

            return hr == 0;
        }
        catch { return false; }
    }

    /// <summary>
    /// The user's Windows accent colour. Winhanced binds SystemAccentColor;
    /// we mirror that so the shell picks up the same personality as the OS.
    /// Falls back to Steam's #1a9fff, which is the measured Big Picture accent.
    /// </summary>
    public static Color AccentColor()
    {
        try
        {
            using var k = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\DWM");
            if (k?.GetValue("AccentColor") is int abgr)
            {
                // DWM stores AABBGGRR
                byte r = (byte)(abgr & 0xFF);
                byte g = (byte)((abgr >> 8) & 0xFF);
                byte b = (byte)((abgr >> 16) & 0xFF);
                // Guard against a near-black/near-white accent, which reads as
                // "no accent at all" on a dark 10ft surface.
                int lum = (r * 299 + g * 587 + b * 114) / 1000;
                if (lum > 32 && lum < 240) return Color.FromRgb(r, g, b);
            }
        }
        catch { /* fall through */ }
        return Color.FromRgb(0x1A, 0x9F, 0xFF);
    }
}
