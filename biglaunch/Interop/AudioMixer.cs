using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;

namespace BigLaunch.Interop;

/// <summary>One active playback endpoint the machine can route sound to.</summary>
public sealed record AudioDevice(string Id, string Name, bool IsDefault);

/// <summary>One row of the per-app mixer. Volume is 0..100.</summary>
public sealed record AudioSession(string Id, string Name, int Volume, bool Muted, uint ProcessId);

/// <summary>
/// The other half of the audio panel: WHICH device sound comes out of, and
/// WHICH app is making it. Volume.cs already owns the master level and mute -
/// nothing here touches those.
///
/// 🔴 WHY BOTH HALVES ARE NEEDED: master volume alone cannot solve the two
/// things that actually go wrong on a couch. The game is quiet because a
/// browser tab in the background is loud (a per-app problem), or there is no
/// sound at all because Windows is still routing to the monitor after the
/// headset was plugged in (a per-device problem). Neither is fixable with a
/// single slider, and both otherwise mean alt-tabbing to the Windows mixer -
/// the exact thing this shell exists to make unnecessary.
///
/// Everything is best-effort. The audio stack is genuinely hostile to polling:
/// sessions appear and die between two calls, an endpoint can vanish
/// mid-enumeration, and the device-switch API is undocumented. A failure here
/// returns an empty list or false so the panel simply shows fewer rows - it
/// must never take down a shell that is polling it once a second.
/// </summary>
public static class AudioMixer
{
    // ---- COM ------------------------------------------------------------
    //
    // Same vtable discipline as Volume.cs: every interface below declares EVERY
    // method that precedes the ones actually called, in exact IDL order,
    // including the ones never touched. A missing slot does not fail loudly -
    // it dispatches to the wrong function pointer and returns silent nonsense.
    //
    // These declarations are deliberately re-declared rather than shared with
    // Volume.cs: its copies are private, and a vtable is easier to audit when
    // it sits in the file that calls it.
    //
    // 🔴 STRING PARAMETERS MUST BE ANNOTATED. In COM interop (unlike P/Invoke)
    // the default marshaling for `string` is BSTR - every string below is
    // really an LPCWSTR/LPWSTR, so an un-annotated one would hand the callee a
    // pointer into a length-prefixed buffer.
    //
    // 🔴 [PreserveSig] IS MANDATORY ON EVERY METHOD BELOW - it is not decoration.
    // Without it the C# compiler emits the method with implFlags=IL, and the
    // runtime then applies the HRESULT/retval transformation: it APPENDS a
    // hidden `[out,retval] int*` argument to the native call and returns THAT
    // slot (zero-initialised, never written by the callee) instead of the
    // HRESULT, while a failing HRESULT is thrown as an exception rather than
    // returned. Every `hr != 0` check in this file would therefore read 0
    // forever, and - the reason this is not merely cosmetic -
    // IsSystemSoundsSession, whose whole answer is the DISTINCTION between
    // S_OK(0) and S_FALSE(1), would report 0 for every session: every row
    // collapses into the one "system" dedupe bucket and the per-app mixer
    // renders a single row named "System".
    //
    // Note this survives a smoke test: S_OK is 0 either way, so only a method
    // returning a NON-ZERO SUCCESS code exposes it. Measured on the live stack -
    // with the attribute, five real app sessions return S_FALSE(1) and only
    // pid 0 returns S_OK(0); without it, all six return 0.


    [ComImport, Guid("77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IAudioSessionManager2
    {
        // the two inherited IAudioSessionManager slots come first
        [PreserveSig] int GetAudioSessionControl(IntPtr sessionGuid, uint streamFlags, out IAudioSessionControl ctl);
        [PreserveSig] int GetSimpleAudioVolume(IntPtr sessionGuid, uint streamFlags, out ISimpleAudioVolume vol);
        [PreserveSig] int GetSessionEnumerator(out IAudioSessionEnumerator sessions);
        [PreserveSig] int RegisterSessionNotification(IntPtr notification);
        [PreserveSig] int UnregisterSessionNotification(IntPtr notification);
        [PreserveSig] int RegisterDuckNotification([MarshalAs(UnmanagedType.LPWStr)] string sessionId, IntPtr duck);
        [PreserveSig] int UnregisterDuckNotification(IntPtr duck);
    }

    [ComImport, Guid("E2F5BB11-0570-40CA-ACDD-3AA01277DEE8"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IAudioSessionEnumerator
    {
        [PreserveSig] int GetCount(out int count);
        [PreserveSig] int GetSession(int index, out IAudioSessionControl session);
    }

    // Only ever used as the handle GetSession hands back, and immediately cast
    // to IAudioSessionControl2. The slots are still spelled out so the next
    // reader can see what the base vtable is and where C2 continues from.
    [ComImport, Guid("F4B1A599-7266-4319-A8CA-E70ACB11E8CD"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IAudioSessionControl
    {
        [PreserveSig] int GetState(out int state);
        [PreserveSig] int GetDisplayName([MarshalAs(UnmanagedType.LPWStr)] out string name);
        [PreserveSig] int SetDisplayName([MarshalAs(UnmanagedType.LPWStr)] string value, ref Guid ctx);
        [PreserveSig] int GetIconPath([MarshalAs(UnmanagedType.LPWStr)] out string path);
        [PreserveSig] int SetIconPath([MarshalAs(UnmanagedType.LPWStr)] string value, ref Guid ctx);
        [PreserveSig] int GetGroupingParam(out Guid group);
        [PreserveSig] int SetGroupingParam(ref Guid group, ref Guid ctx);
        [PreserveSig] int RegisterAudioSessionNotification(IntPtr events);
        [PreserveSig] int UnregisterAudioSessionNotification(IntPtr events);
    }

    // IAudioSessionControl2 EXTENDS IAudioSessionControl, so its vtable begins
    // with all nine methods above - flattened here rather than expressed as C#
    // inheritance, because the flat form IS the slot order.
    [ComImport, Guid("BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IAudioSessionControl2
    {
        [PreserveSig] int GetState(out int state);
        [PreserveSig] int GetDisplayName([MarshalAs(UnmanagedType.LPWStr)] out string name);
        [PreserveSig] int SetDisplayName([MarshalAs(UnmanagedType.LPWStr)] string value, ref Guid ctx);
        [PreserveSig] int GetIconPath([MarshalAs(UnmanagedType.LPWStr)] out string path);
        [PreserveSig] int SetIconPath([MarshalAs(UnmanagedType.LPWStr)] string value, ref Guid ctx);
        [PreserveSig] int GetGroupingParam(out Guid group);
        [PreserveSig] int SetGroupingParam(ref Guid group, ref Guid ctx);
        [PreserveSig] int RegisterAudioSessionNotification(IntPtr events);
        [PreserveSig] int UnregisterAudioSessionNotification(IntPtr events);
        // ---- C2 additions
        [PreserveSig] int GetSessionIdentifier([MarshalAs(UnmanagedType.LPWStr)] out string id);
        [PreserveSig] int GetSessionInstanceIdentifier([MarshalAs(UnmanagedType.LPWStr)] out string id);
        [PreserveSig] int GetProcessId(out uint pid);
        [PreserveSig] int IsSystemSoundsSession();
        [PreserveSig] int SetDuckingPreference([MarshalAs(UnmanagedType.Bool)] bool optOut);
    }

    [ComImport, Guid("87CE5498-68D6-44E5-9215-6DA47EF883D8"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface ISimpleAudioVolume
    {
        [PreserveSig] int SetMasterVolume(float level, ref Guid ctx);
        [PreserveSig] int GetMasterVolume(out float level);
        [PreserveSig] int SetMute([MarshalAs(UnmanagedType.Bool)] bool mute, ref Guid ctx);
        [PreserveSig] int GetMute([MarshalAs(UnmanagedType.Bool)] out bool mute);
    }

    // 🔴 IPolicyConfig IS UNDOCUMENTED. There is no public API to change the
    // default playback device - Microsoft ships the capability only inside the
    // Settings app. This is the interface every third-party audio switcher
    // uses and it has been stable since Windows 7, but it is not a contract: a
    // future build may move the slots or drop it, and the correct response is
    // to fail soft and leave the row inert, never to throw.
    //
    // SetDefaultEndpoint is the ELEVENTH slot, so all ten predecessors are
    // spelled out. Their pointer arguments are IntPtr rather than real types
    // (WAVEFORMATEX, DeviceShareMode) because they are never called and only
    // the argument SIZE matters for the stack frame.
    [ComImport, Guid("870AF99C-171D-4F9E-AF0D-E63DF40C2BC9")]
    private class PolicyConfigClient { }

    [ComImport, Guid("F8679F50-850A-41CF-9C72-430F290290C8"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IPolicyConfig
    {
        [PreserveSig] int GetMixFormat([MarshalAs(UnmanagedType.LPWStr)] string id, out IntPtr format);
        [PreserveSig] int GetDeviceFormat([MarshalAs(UnmanagedType.LPWStr)] string id, int isDefault, out IntPtr format);
        [PreserveSig] int ResetDeviceFormat([MarshalAs(UnmanagedType.LPWStr)] string id);
        [PreserveSig] int SetDeviceFormat([MarshalAs(UnmanagedType.LPWStr)] string id, IntPtr endpointFormat, IntPtr mixFormat);
        [PreserveSig] int GetProcessingPeriod([MarshalAs(UnmanagedType.LPWStr)] string id, int isDefault,
                                out long defaultPeriod, out long minimumPeriod);
        [PreserveSig] int SetProcessingPeriod([MarshalAs(UnmanagedType.LPWStr)] string id, ref long period);
        [PreserveSig] int GetShareMode([MarshalAs(UnmanagedType.LPWStr)] string id, IntPtr mode);
        [PreserveSig] int SetShareMode([MarshalAs(UnmanagedType.LPWStr)] string id, IntPtr mode);
        [PreserveSig] int GetPropertyValue([MarshalAs(UnmanagedType.LPWStr)] string id,
                                           ref PROPERTYKEY key, out PROPVARIANT value);
        [PreserveSig] int SetPropertyValue([MarshalAs(UnmanagedType.LPWStr)] string id,
                                           ref PROPERTYKEY key, ref PROPVARIANT value);
        [PreserveSig] int SetDefaultEndpoint([MarshalAs(UnmanagedType.LPWStr)] string id, int role);
        [PreserveSig] int SetEndpointVisibility([MarshalAs(UnmanagedType.LPWStr)] string id, int visible);
    }

    // ---- constants ------------------------------------------------------

    private const int ERender = 0;                 // EDataFlow::eRender
    private const int RoleConsole = 0, RoleMultimedia = 1, RoleCommunications = 2;
    private const int DeviceStateActive = 1;       // DEVICE_STATE_ACTIVE
    private const int StgmRead = 0;                // STGM_READ
    private const int ClsCtxAll = 23;
    private const int SessionExpired = 2;          // AudioSessionState::AudioSessionStateExpired
    private const ushort VtLpwstr = 31;

    private static readonly PROPERTYKEY PkeyDeviceFriendlyName = new()
    {
        fmtid = new Guid("a45c254e-df1c-4efd-8020-67d146a850e0"),
        pid = 14
    };

    // Core Audio wants an event-context GUID so a control can ignore its own
    // change notifications. Nothing here subscribes, so an empty one is fine.
    private static Guid _ctx = Guid.Empty;

    // 🔴 SUCCESS IS hr >= 0, NOT hr == 0. Core Audio returns non-zero SUCCESS
    // codes, and testing `!= 0` reads them as failure. Measured live on this
    // stack: GetProcessId returns AUDCLNT_S_NO_SINGLE_PROCESS (0x0889000D) for
    // a session that spans processes - and STILL writes a valid pid - so the
    // `!= 0` form threw away a real process id, forced it to 0, and turned a
    // running app's second session into a duplicate row labelled "System".
    //
    // IsSystemSoundsSession is the one deliberate exception below: there S_OK
    // vs S_FALSE IS the answer, so it must keep testing == 0.
    private static bool Ok(int hr) => hr >= 0;

    private static IMMDeviceEnumerator? Enumerator()
    {
        // The exception is KEPT, not discarded: "the enumerator would not build"
        // is not a diagnosis, and this is the one call every other function in
        // the file depends on.
        try { return (IMMDeviceEnumerator)(object)new MMDeviceEnumerator(); }
        catch (Exception ex) { LastError = ex.GetType().Name + ": " + ex.Message; return null; }
    }

    // ---- output devices -------------------------------------------------

    /// <summary>
    /// Every ACTIVE render endpoint, with the current system default flagged.
    /// Disabled and unplugged endpoints are excluded - offering to switch to a
    /// device that is not there produces a switch that silently does nothing.
    ///
    /// BLOCKING: enumerates endpoints and opens a property store per device.
    /// Call it off the UI thread.
    /// </summary>
    /// <summary>
    /// The last thing that went wrong in here, for the panel to show.
    ///
    /// 🔴 A SILENT EMPTY LIST IS UNDEBUGGABLE. Every failure path in this file
    /// swallows its HRESULT and returns an empty list, which reaches the user as
    /// a section that simply is not there - indistinguishable from a machine
    /// that genuinely has one output and nothing playing. One string, set on the
    /// way out, turns that into a stated fact.
    /// </summary>
    public static string LastError = "";

    public static List<AudioDevice> OutputDevices()
    {
        var list = new List<AudioDevice>();
        try
        {
            var en = Enumerator();
            if (en is null) { if (LastError == "") LastError = "no enumerator"; return list; }

            // Resolved separately rather than read off the collection: the
            // collection has no "is default" concept at all.
            string defaultId = "";
            if (Ok(en.GetDefaultAudioEndpoint(ERender, RoleMultimedia, out var def)) && def is not null
                && Ok(def.GetId(out string did)) && !string.IsNullOrEmpty(did))
                defaultId = did;

            int hrEnum = en.EnumAudioEndpoints(ERender, DeviceStateActive, out var coll);
            if (!Ok(hrEnum) || coll is null) { LastError = $"EnumAudioEndpoints 0x{hrEnum:X8}"; return list; }
            int hrCount = coll.GetCount(out uint n);
            if (!Ok(hrCount)) { LastError = $"GetCount 0x{hrCount:X8}"; return list; }
            LastError = n == 0 ? "no active render endpoints" : "";

            for (uint i = 0; i < n; i++)
            {
                try
                {
                    if (!Ok(coll.Item(i, out var dev)) || dev is null) continue;
                    if (!Ok(dev.GetId(out string id)) || string.IsNullOrEmpty(id)) continue;

                    string name = FriendlyName(dev);
                    // An endpoint with no friendly name is still a real, usable
                    // device - dropping it would silently hide an output.
                    if (string.IsNullOrWhiteSpace(name)) name = "Audio device";

                    list.Add(new AudioDevice(
                        id, name, string.Equals(id, defaultId, StringComparison.OrdinalIgnoreCase)));
                }
                catch (Exception ex) { LastError = "endpoint: " + ex.Message; }
            }
            if (list.Count == 0 && n > 0 && LastError == "") LastError = $"{n} endpoints, none readable";
        }
        catch (Exception ex) { LastError = ex.Message; }
        return list;
    }

    private static string FriendlyName(IMMDevice dev)
    {
        var pv = default(PROPVARIANT);
        bool owned = false;
        try
        {
            if (!Ok(dev.OpenPropertyStore(StgmRead, out var store)) || store is null) return "";
            var key = PkeyDeviceFriendlyName;
            if (!Ok(store.GetValue(ref key, out pv))) return "";
            owned = true;
            if (pv.vt != VtLpwstr || pv.p == IntPtr.Zero) return "";
            string? s = Marshal.PtrToStringUni(pv.p);
            return string.IsNullOrEmpty(s) ? "" : s;
        }
        catch { return ""; }
        // Clear only what GetValue actually filled: clearing an untouched
        // PROPVARIANT is harmless, clearing a half-written one is not.
        finally { if (owned) { try { CoreAudio.PropVariantClear(ref pv); } catch { } } }
    }

    /// <summary>
    /// Make <paramref name="deviceId"/> the system default output.
    ///
    /// 🔴 ALL THREE ROLES, ALWAYS. Windows keeps a separate default for
    /// console, multimedia and communications; switching one leaves apps split
    /// across two devices - game audio in the headset, voice chat still in the
    /// monitor - which reads as "the switch half worked".
    ///
    /// BLOCKING: the audio engine re-routes every stream. Call it off the UI
    /// thread. Fails soft - see the IPolicyConfig note above.
    /// </summary>
    public static bool SetDefaultOutput(string deviceId)
    {
        if (string.IsNullOrWhiteSpace(deviceId)) return false;
        try
        {
            var cfg = (IPolicyConfig)(object)new PolicyConfigClient();
            bool ok = true;
            for (int role = RoleConsole; role <= RoleCommunications; role++)
            {
                int hr = cfg.SetDefaultEndpoint(deviceId, role);
                // eCommunications is allowed to fail: HDMI and S/PDIF endpoints
                // are legitimately not valid comms devices, and playback still
                // moved - reporting failure there would be a lie.
                if (!Ok(hr) && role != RoleCommunications) ok = false;
            }
            return ok;
        }
        catch { return false; }
    }

    // ---- per-app sessions -----------------------------------------------

    /// <summary>
    /// One live mixer row, still holding the COM objects it was read through.
    /// Never stored beyond the call that produced it.
    /// </summary>
    private readonly struct Row
    {
        public readonly string Id;
        public readonly uint Pid;
        public readonly bool Sys;
        public readonly IAudioSessionControl2 Ctl;
        public readonly ISimpleAudioVolume Vol;
        public Row(string id, uint pid, bool sys, IAudioSessionControl2 ctl, ISimpleAudioVolume vol)
        { Id = id; Pid = pid; Sys = sys; Ctl = ctl; Vol = vol; }
    }

    /// <summary>
    /// Walks the default endpoint's session enumerator once.
    ///
    /// 🔴 THE RESULT IS VALID FOR THIS CALL ONLY. Sessions die under you - an
    /// app closing mid-poll invalidates its control - so no caller may hold
    /// these pointers between calls. Every public entry point re-walks.
    ///
    /// BLOCKING.
    /// </summary>
    private static List<Row> Walk()
    {
        var rows = new List<Row>();
        var en = Enumerator();
        if (en is null) return rows;
        if (!Ok(en.GetDefaultAudioEndpoint(ERender, RoleMultimedia, out var dev)) || dev is null) return rows;

        var iid = typeof(IAudioSessionManager2).GUID;
        if (!Ok(dev.Activate(ref iid, ClsCtxAll, IntPtr.Zero, out object o))) return rows;
        if (o is not IAudioSessionManager2 mgr) return rows;
        if (!Ok(mgr.GetSessionEnumerator(out var sessions)) || sessions is null) return rows;
        if (!Ok(sessions.GetCount(out int count))) return rows;

        for (int i = 0; i < count; i++)
        {
            try
            {
                if (!Ok(sessions.GetSession(i, out var ctl)) || ctl is null) continue;

                // QueryInterface, not a managed cast: the process id and the
                // instance identifier only exist on the C2 vtable.
                if (ctl is not IAudioSessionControl2 c2) continue;
                if (ctl is not ISimpleAudioVolume vol) continue;

                // An expired session is an app that already closed. Windows
                // keeps the object around briefly; showing it is a dead row
                // with a slider that controls nothing.
                if (Ok(c2.GetState(out int state)) && state == SessionExpired) continue;

                if (!Ok(c2.GetSessionInstanceIdentifier(out string sid)) || string.IsNullOrEmpty(sid)) continue;
                // AUDCLNT_S_NO_SINGLE_PROCESS is a SUCCESS code that still
                // yields the pid that created the session - only a real
                // failure (hr < 0) leaves us with nothing to attribute to.
                if (!Ok(c2.GetProcessId(out uint pid))) pid = 0;

                // S_OK (0) means yes here and S_FALSE (1) means no - the return
                // IS the answer, not an error code.
                bool sys = c2.IsSystemSoundsSession() == 0;

                rows.Add(new Row(sid, pid, sys, c2, vol));
            }
            catch { }   // a session torn down mid-read must not empty the mixer
        }
        return rows;
    }

    /// <summary>
    /// The per-app mixer: one row per application currently able to make sound
    /// on the default output.
    ///
    /// BLOCKING: enumerates sessions and resolves process names. Call it off
    /// the UI thread.
    /// </summary>
    public static List<AudioSession> Sessions()
    {
        var result = new List<AudioSession>();
        try
        {
            // 🔴 DEDUPE BY PROCESS. A browser opens a session per tab and a
            // game can open several for music and effects; without this the
            // mixer is ten identical rows and is simply broken. The loudest
            // wins so the row shows the level the user can actually hear, and
            // first-seen breaks ties to keep the order stable across repaints.
            var order = new List<string>();
            var best = new Dictionary<string, (Row Row, int Vol, bool Muted)>();

            foreach (var r in Walk())
            {
                try
                {
                    if (!Ok(r.Vol.GetMasterVolume(out float level))) continue;
                    int pct = Math.Clamp((int)Math.Round(level * 100), 0, 100);
                    bool muted = Ok(r.Vol.GetMute(out bool m)) && m;

                    // System sounds get their own bucket: the session can
                    // report the pid of whatever raised the beep, and merging
                    // it into that app's row would relabel the app.
                    // pid 0 shares this bucket because NameFor renders it as
                    // "System" too - splitting them produced two rows the user
                    // cannot tell apart, which is the exact duplication this
                    // dedupe exists to prevent.
                    string key = r.Sys || r.Pid == 0 ? "system" : r.Pid.ToString();

                    if (!best.TryGetValue(key, out var cur)) order.Add(key);
                    else if (pct <= cur.Vol) continue;

                    best[key] = (r, pct, muted);
                }
                catch { }
            }

            foreach (string key in order)
            {
                if (!best.TryGetValue(key, out var e)) continue;
                result.Add(new AudioSession(e.Row.Id, NameFor(e.Row), e.Vol, e.Muted, e.Row.Pid));
            }
        }
        catch { }
        return result;
    }

    /// <summary>
    /// 🔴 THE DISPLAY NAME IS USUALLY EMPTY. Ordinary apps never call
    /// SetDisplayName, so the mixer name has to come from the process - which
    /// is exactly what the Windows mixer does. Resolved AFTER dedupe, so a
    /// ten-session browser costs one process lookup rather than ten.
    /// </summary>
    private static string NameFor(Row r)
    {
        // pid 0 and the system-sounds session are the same thing to a user:
        // Windows' own beeps, which belong to no application.
        if (r.Sys || r.Pid == 0) return "System";

        try
        {
            using var p = Process.GetProcessById((int)r.Pid);
            string title = p.MainWindowTitle;
            if (!string.IsNullOrWhiteSpace(title)) return title;
            string name = p.ProcessName;
            if (!string.IsNullOrWhiteSpace(name)) return name;
        }
        catch { }   // exited between the walk and here, or access denied

        try
        {
            if (Ok(r.Ctl.GetDisplayName(out string dn)) && !string.IsNullOrWhiteSpace(dn)) return dn;
        }
        catch { }

        // A nameless row still beats a missing one: the sound is real, and the
        // user can mute it whether or not we can say what it is.
        return "Unknown";
    }

    /// <summary>
    /// Set one app's volume, 0..100 (clamped, so a caller can add a step
    /// blindly). BLOCKING: re-walks the session list. Call it off the UI thread.
    /// </summary>
    public static bool SetSessionVolume(string sessionId, int percent)
        => WithSession(sessionId, vol =>
        {
            float v = Math.Clamp(percent, 0, 100) / 100f;
            // Same rule as the master control in Volume.cs: raising a muted app
            // un-mutes it, or "louder" does nothing audible and the control
            // looks broken while it is working perfectly.
            if (percent > 0) vol.SetMute(false, ref _ctx);
            return Ok(vol.SetMasterVolume(v, ref _ctx));
        });

    /// <summary>
    /// Mute or un-mute one app. BLOCKING: re-walks the session list. Call it
    /// off the UI thread.
    /// </summary>
    public static bool SetSessionMute(string sessionId, bool mute)
        => WithSession(sessionId, vol => Ok(vol.SetMute(mute, ref _ctx)));

    /// <summary>
    /// Re-enumerates and matches on the session instance identifier.
    ///
    /// 🔴 NEVER CACHE THE POINTER BETWEEN CALLS. The identifier is the key
    /// precisely because it survives across walks while the COM object does
    /// not - a session that died since the last read would otherwise be a
    /// stale pointer and a crash, rather than a clean false.
    /// </summary>
    private static bool WithSession(string sessionId, Func<ISimpleAudioVolume, bool> act)
    {
        if (string.IsNullOrEmpty(sessionId)) return false;
        try
        {
            foreach (var r in Walk())
                if (string.Equals(r.Id, sessionId, StringComparison.Ordinal))
                    return act(r.Vol);
            return false;
        }
        catch { return false; }
    }
}
