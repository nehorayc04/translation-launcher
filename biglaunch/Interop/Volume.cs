using System;
using System.Runtime.InteropServices;

namespace BigLaunch.Interop;

/// <summary>
/// System master volume — read and set.
///
/// 🔴 WHY THIS EXISTS AT ALL: a 10ft shell driven by a controller has no way to
/// change the volume. On a desktop you reach for a keyboard media key; on a
/// couch there is no keyboard, and "alt-tab to the Windows mixer" is exactly the
/// thing this shell is supposed to make unnecessary. Winhanced puts a speaker in
/// its header pill for the same reason.
///
/// It talks to Core Audio (IAudioEndpointVolume) rather than sending
/// VK_VOLUME_UP keystrokes: the keystroke route cannot READ the level, so the
/// shell could offer a control that never shows where it currently sits - and a
/// slider that does not know its own value is worse than no slider.
///
/// Every entry point is best-effort: an audio stack that refuses (no endpoint,
/// a session teardown mid-call) must never take down the shell, so a failure
/// reports "unavailable" and the UI simply omits the row.
/// </summary>
public static class Volume
{
    // 🔴 [PreserveSig] ON EVERY METHOD IS NOT OPTIONAL. Without it the runtime
    // rewrites the call: it hides the HRESULT, appends a hidden retval slot and
    // THROWS on failure - so every `hr != 0` check below silently reads 0 forever
    // and real failures arrive as exceptions instead. The happy path survives by
    // accident (S_OK is 0 either way), which is exactly why it went unnoticed.
    //
    // The vtable ORDER is the contract here - each interface below must declare
    // every method that precedes the ones we call, or the runtime dispatches to
    // the wrong slot and the result is silent nonsense rather than an error.


    [ComImport, Guid("5CDF2C82-841E-4546-9722-0CF74078229A"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IAudioEndpointVolume
    {
        [PreserveSig] int RegisterControlChangeNotify(IntPtr notify);
        [PreserveSig] int UnregisterControlChangeNotify(IntPtr notify);
        [PreserveSig] int GetChannelCount(out uint count);
        [PreserveSig] int SetMasterVolumeLevel(float db, ref Guid ctx);
        [PreserveSig] int SetMasterVolumeLevelScalar(float level, ref Guid ctx);
        [PreserveSig] int GetMasterVolumeLevel(out float db);
        [PreserveSig] int GetMasterVolumeLevelScalar(out float level);
        [PreserveSig] int SetChannelVolumeLevel(uint ch, float db, ref Guid ctx);
        [PreserveSig] int SetChannelVolumeLevelScalar(uint ch, float level, ref Guid ctx);
        [PreserveSig] int GetChannelVolumeLevel(uint ch, out float db);
        [PreserveSig] int GetChannelVolumeLevelScalar(uint ch, out float level);
        [PreserveSig] int SetMute([MarshalAs(UnmanagedType.Bool)] bool mute, ref Guid ctx);
        [PreserveSig] int GetMute([MarshalAs(UnmanagedType.Bool)] out bool mute);
        [PreserveSig] int GetVolumeStepInfo(out uint step, out uint stepCount);
        [PreserveSig] int VolumeStepUp(ref Guid ctx);
        [PreserveSig] int VolumeStepDown(ref Guid ctx);
        [PreserveSig] int QueryHardwareSupport(out uint mask);
        [PreserveSig] int GetVolumeRange(out float min, out float max, out float inc);
    }

    private static Guid _ctx = Guid.Empty;

    /// <summary>
    /// The endpoint is resolved per call rather than cached: the default device
    /// CHANGES under the user (headphones plugged in, a monitor's speakers
    /// waking up), and a cached pointer would then be adjusting the volume of a
    /// device nobody is listening to.
    /// </summary>
    private static IAudioEndpointVolume? Endpoint()
    {
        try
        {
            var enumr = (IMMDeviceEnumerator)(object)new MMDeviceEnumerator();
            if (enumr.GetDefaultAudioEndpoint(0 /* eRender */, 1 /* eMultimedia */, out var dev) != 0
                || dev is null) return null;
            var iid = typeof(IAudioEndpointVolume).GUID;
            if (dev.Activate(ref iid, 23 /* CLSCTX_ALL */, IntPtr.Zero, out object o) != 0) return null;
            return o as IAudioEndpointVolume;
        }
        catch { return null; }
    }

    /// <summary>0..100, or -1 when there is no usable output device.</summary>
    public static int Level()
    {
        try
        {
            var ep = Endpoint();
            if (ep is null) return -1;
            return ep.GetMasterVolumeLevelScalar(out float v) == 0
                ? (int)Math.Round(v * 100) : -1;
        }
        catch { return -1; }
    }

    public static bool Muted()
    {
        try
        {
            var ep = Endpoint();
            return ep is not null && ep.GetMute(out bool m) == 0 && m;
        }
        catch { return false; }
    }

    /// <summary>Set 0..100. Clamped, so a caller can add a step blindly.</summary>
    public static bool Set(int percent)
    {
        try
        {
            var ep = Endpoint();
            if (ep is null) return false;
            float v = Math.Clamp(percent, 0, 100) / 100f;
            // Raising the volume un-mutes. Otherwise pressing "louder" on a muted
            // system does nothing audible, and the user presses it again and
            // again - the control appears broken while it is working perfectly.
            if (percent > 0) ep.SetMute(false, ref _ctx);
            return ep.SetMasterVolumeLevelScalar(v, ref _ctx) == 0;
        }
        catch { return false; }
    }

    public static bool ToggleMute()
    {
        try
        {
            var ep = Endpoint();
            if (ep is null) return false;
            if (ep.GetMute(out bool m) != 0) return false;
            return ep.SetMute(!m, ref _ctx) == 0;
        }
        catch { return false; }
    }
}
