using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Media.Imaging;

namespace BigLaunch.Services;

/// <summary>
/// Screenshots.
///
/// 🔴 Known limit, stated rather than hidden: this is a GDI desktop copy, so
/// it captures windowed and BORDERLESS games (what almost everything runs as
/// today) but returns black for a game holding a true EXCLUSIVE-fullscreen
/// DX12 flip-model swapchain — the same wall this project already documented
/// when it had to switch to DXGI duplication for in-game capture. Grabbing
/// those needs a duplication/hook path, which a launcher has no business
/// injecting; the UI says so instead of pretending.
/// </summary>
public static class Capture
{
    [DllImport("user32.dll")] private static extern IntPtr GetDesktopWindow();
    [DllImport("user32.dll")] private static extern IntPtr GetWindowDC(IntPtr h);
    [DllImport("user32.dll")] private static extern int ReleaseDC(IntPtr h, IntPtr dc);
    [DllImport("user32.dll")] private static extern int GetSystemMetrics(int i);

    [DllImport("gdi32.dll")] private static extern IntPtr CreateCompatibleDC(IntPtr dc);
    [DllImport("gdi32.dll")] private static extern IntPtr CreateCompatibleBitmap(IntPtr dc, int w, int h);
    [DllImport("gdi32.dll")] private static extern IntPtr SelectObject(IntPtr dc, IntPtr o);
    [DllImport("gdi32.dll")] private static extern bool DeleteObject(IntPtr o);
    [DllImport("gdi32.dll")] private static extern bool DeleteDC(IntPtr dc);
    [DllImport("gdi32.dll")]
    private static extern bool BitBlt(IntPtr dst, int x, int y, int w, int h,
                                      IntPtr src, int sx, int sy, uint rop);

    private const uint SRCCOPY = 0x00CC0020;
    private const int SM_XVIRTUALSCREEN = 76, SM_YVIRTUALSCREEN = 77,
                      SM_CXVIRTUALSCREEN = 78, SM_CYVIRTUALSCREEN = 79;

    public static string Folder => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.MyPictures), "Big Launch");

    /// <summary>Save a PNG of the whole desktop. Returns the path, or null.</summary>
    public static string? Take()
    {
        IntPtr desk = IntPtr.Zero, src = IntPtr.Zero, mem = IntPtr.Zero, bmp = IntPtr.Zero, old = IntPtr.Zero;
        try
        {
            int x = GetSystemMetrics(SM_XVIRTUALSCREEN), y = GetSystemMetrics(SM_YVIRTUALSCREEN);
            int w = GetSystemMetrics(SM_CXVIRTUALSCREEN), h = GetSystemMetrics(SM_CYVIRTUALSCREEN);
            if (w <= 0 || h <= 0) return null;

            desk = GetDesktopWindow();
            src = GetWindowDC(desk);
            mem = CreateCompatibleDC(src);
            // 🔴 The bitmap MUST come from the WINDOW dc. From a fresh memory DC
            // it is created 1-bpp monochrome and every capture is solid black.
            bmp = CreateCompatibleBitmap(src, w, h);
            old = SelectObject(mem, bmp);

            if (!BitBlt(mem, 0, 0, w, h, src, x, y, SRCCOPY)) return null;

            var source = System.Windows.Interop.Imaging.CreateBitmapSourceFromHBitmap(
                bmp, IntPtr.Zero, Int32Rect.Empty, BitmapSizeOptions.FromEmptyOptions());

            Directory.CreateDirectory(Folder);
            string path = Path.Combine(Folder, $"BigLaunch_{DateTime.Now:yyyy-MM-dd_HH-mm-ss}.png");
            using (var fs = File.Create(path))
            {
                var enc = new PngBitmapEncoder();
                enc.Frames.Add(BitmapFrame.Create(source));
                enc.Save(fs);
            }
            Sfx.Play(Sound.Shutter);
            return path;
        }
        catch { return null; }
        finally
        {
            try
            {
                if (old != IntPtr.Zero) SelectObject(mem, old);
                if (bmp != IntPtr.Zero) DeleteObject(bmp);
                if (mem != IntPtr.Zero) DeleteDC(mem);
                if (src != IntPtr.Zero) ReleaseDC(desk, src);
            }
            catch { }
        }
    }
}
