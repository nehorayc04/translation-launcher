using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace BigLaunch.Interop;

/// <summary>
/// The real icon of a running program, for the per-app volume rows.
///
/// 🔴 A ROW OF IDENTICAL GLYPHS IS A LIST YOU HAVE TO READ. Six apps all wearing
/// the same controller mark means the only thing telling them apart is a word,
/// and on a screen driven from a couch the icon is what the eye actually lands
/// on - it is how you find "the browser" without reading "Chrome".
///
/// Everything here is best-effort: an app that exits between the audio walk and
/// this lookup, or one this process may not open, simply keeps the glyph.
/// </summary>
public static class AppIcons
{
    private const int PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(int access, bool inherit, uint pid);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseHandle(IntPtr h);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool QueryFullProcessImageNameW(IntPtr proc, int flags,
                                                          StringBuilder path, ref int size);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct SHFILEINFO
    {
        public IntPtr hIcon;
        public int iIcon;
        public uint dwAttributes;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szDisplayName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 80)] public string szTypeName;
    }

    private const uint SHGFI_ICON = 0x000000100;
    private const uint SHGFI_LARGEICON = 0x000000000;

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr SHGetFileInfoW(string path, uint attrs, ref SHFILEINFO info,
                                                uint cb, uint flags);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DestroyIcon(IntPtr h);

    // Keyed by executable path, because ten sessions of one browser are one
    // icon - and because the answer can be null ("this one has none"), which is
    // itself worth remembering so it is not re-attempted every refresh.
    private static readonly ConcurrentDictionary<string, ImageSource?> Cache = new();

    /// <summary>
    /// The icon of an executable ON DISK, for a game with no box art.
    ///
    /// 🔴 AN EXE ICON IS NOT BOX ART, AND IT IS STILL THE RIGHT ANSWER. Titles
    /// outside Steam (Ubisoft, GOG, a loose install) have no cached cover
    /// anywhere on the machine and no catalog entry to fetch one from, so their
    /// tiles were a plate with a word on it - which reads as a broken card in a
    /// row of real covers. The game's own icon is local, instant, and is the
    /// same mark the user clicks on the desktop.
    /// </summary>
    public static ImageSource? ForFile(string? exePath)
    {
        if (string.IsNullOrWhiteSpace(exePath)) return null;
        try { if (!System.IO.File.Exists(exePath)) return null; } catch { return null; }
        return Cache.GetOrAdd(exePath, Load);
    }

    /// <summary>The icon of the process behind an audio session, or null.</summary>
    public static ImageSource? ForProcess(uint pid)
    {
        if (pid == 0) return null;
        string? path = PathOf(pid);
        if (string.IsNullOrEmpty(path)) return null;
        return Cache.GetOrAdd(path, Load);
    }

    /// <summary>The executable behind a pid, or null. Public because session
    /// tracking needs the same answer for the same reason the icons do - and for
    /// the same reason it cannot use Process.MainModule (see below).</summary>
    public static string? PathOfProcess(uint pid) => PathOf(pid);

    private static string? PathOf(uint pid)
    {
        // 🔴 QueryFullProcessImageName, NOT Process.MainModule. MainModule throws
        // for any process this one cannot open for VM read - which on a normal
        // desktop is most of them, including every elevated app - so the icons
        // would have been missing exactly where they matter. LIMITED_INFORMATION
        // is granted to a plain user for ordinary processes.
        IntPtr h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid);
        if (h == IntPtr.Zero) return null;
        try
        {
            var sb = new StringBuilder(1024);
            int size = sb.Capacity;
            return QueryFullProcessImageNameW(h, 0, sb, ref size) ? sb.ToString() : null;
        }
        catch { return null; }
        finally { CloseHandle(h); }
    }

    private static ImageSource? Load(string path)
    {
        var info = new SHFILEINFO();
        IntPtr hr = IntPtr.Zero;
        try
        {
            hr = SHGetFileInfoW(path, 0, ref info, (uint)Marshal.SizeOf<SHFILEINFO>(),
                                SHGFI_ICON | SHGFI_LARGEICON);
            if (info.hIcon == IntPtr.Zero) return null;

            var src = Imaging.CreateBitmapSourceFromHIcon(
                info.hIcon, Int32Rect.Empty, BitmapSizeOptions.FromEmptyOptions());
            // Frozen so it can be built once and used from any thread, and so WPF
            // stops tracking it for changes it will never have.
            src.Freeze();
            return src;
        }
        catch { return null; }
        finally
        {
            // 🔴 THE HICON IS OURS TO FREE. CreateBitmapSourceFromHIcon copies the
            // pixels; the handle it was given stays allocated until DestroyIcon,
            // and a shell that re-reads the mixer every few seconds would leak a
            // GDI handle per row per refresh until the desktop ran out.
            if (info.hIcon != IntPtr.Zero) DestroyIcon(info.hIcon);
        }
    }
}
