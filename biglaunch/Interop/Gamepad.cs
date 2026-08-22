using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Windows.Threading;

namespace BigLaunch.Interop;

public enum Pad
{
    None, Up, Down, Left, Right,
    A, B, X, Y,
    LB, RB, LT, RT,
    Start, Back, Guide
}

/// <summary>Which device the on-screen button prompts should be drawn for.</summary>
public enum PadKind { Keyboard, Xbox, Ps4, Ps5 }

/// <summary>
/// Which controller is actually plugged in, by USB VID/PID.
///
/// 🔴 XInput CANNOT ANSWER THIS. It reports a "gamepad" and nothing else — by
/// design, since its whole job is to make every pad look like an Xbox one. A
/// DualSense driven through DS4Windows arrives as a perfect Xbox pad, so asking
/// XInput would print A/B/X/Y to somebody holding ✕/○/□/△. The legacy joystick
/// API is the one that still reports the real manufacturer and product ids, and
/// it enumerates the Sony pads XInput hides — so it answers both questions the
/// other backend cannot.
/// </summary>
public static class PadIdentity
{
    private const ushort VidSony = 0x054C;

    // Sony's own product ids. DualSense first: an unknown Sony pad is far more
    // likely to be a newer PlayStation model than an older one, and ✕/○/□/△ are
    // identical across both — only the shoulder labels differ.
    private static readonly ushort[] Ps5Pids = { 0x0CE6, 0x0DF2 };            // DualSense, Edge
    private static readonly ushort[] Ps4Pids = { 0x05C4, 0x09CC, 0x0BA0 };    // DS4 v1/v2, dongle

    /// <summary>The connected pad's family, or null when no pad is present.</summary>
    public static PadKind? Detect()
    {
        for (int i = 0; i < 16; i++)
        {
            var jc = new JOYCAPS();
            int rc;
            try { rc = joyGetDevCaps(i, ref jc, Marshal.SizeOf<JOYCAPS>()); }
            catch { break; }
            if (rc != 0) continue;

            if (jc.wMid == VidSony)
            {
                if (Array.IndexOf(Ps5Pids, jc.wPid) >= 0) return PadKind.Ps5;
                if (Array.IndexOf(Ps4Pids, jc.wPid) >= 0) return PadKind.Ps4;
                return PadKind.Ps5;                      // a Sony pad we do not have an id for
            }
            // Some drivers report a blank VID but a truthful NAME.
            string n = (jc.szPname ?? "").ToUpperInvariant();
            if (n.Contains("DUALSENSE") || n.Contains("PS5")) return PadKind.Ps5;
            if (n.Contains("DUALSHOCK") || n.Contains("PS4") || n.Contains("WIRELESS CONTROLLER")) return PadKind.Ps4;
        }

        // Nothing Sony-shaped. If XInput has a pad it is Xbox-class — including
        // a Sony pad behind a remapper, which is the correct answer: that pad IS
        // presenting Xbox buttons to every game on the machine.
        for (int i = 0; i < 4; i++)
        {
            var caps = new XINPUT_CAPABILITIES();
            int rc;
            try { rc = XInputGetCaps14(i, 0, ref caps); }
            catch { try { rc = XInputGetCaps91(i, 0, ref caps); } catch { rc = -1; } }
            if (rc == 0) return PadKind.Xbox;
        }
        return null;
    }

    [DllImport("winmm.dll", CharSet = CharSet.Unicode, EntryPoint = "joyGetDevCapsW")]
    private static extern int joyGetDevCaps(int id, ref JOYCAPS caps, int size);

    [DllImport("xinput1_4.dll", EntryPoint = "XInputGetCapabilities")]
    private static extern int XInputGetCaps14(int i, int flags, ref XINPUT_CAPABILITIES c);
    [DllImport("xinput9_1_0.dll", EntryPoint = "XInputGetCapabilities")]
    private static extern int XInputGetCaps91(int i, int flags, ref XINPUT_CAPABILITIES c);

    [StructLayout(LayoutKind.Sequential)]
    private struct XINPUT_CAPABILITIES
    {
        public byte Type, SubType; public ushort Flags;
        public ushort wButtons; public byte bLeftTrigger, bRightTrigger;
        public short sThumbLX, sThumbLY, sThumbRX, sThumbRY;
        public ushort wLeftMotorSpeed, wRightMotorSpeed;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct JOYCAPS
    {
        public ushort wMid, wPid;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string szPname;
        public int wXmin, wXmax, wYmin, wYmax, wZmin, wZmax;
        public int wNumButtons, wPeriodMin, wPeriodMax;
        public int wRmin, wRmax, wUmin, wUmax, wVmin, wVmax;
        public int wCaps, wMaxAxes, wNumAxes, wMaxButtons;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string szRegKey;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string szOEMVxD;
    }
}

/// <summary>
/// Controller input for the 10ft shell.
///
/// Two backends, polled together — the lesson from the overlay work:
/// XInput sees genuine Xbox-class pads ONLY. A PlayStation DualSense/DualShock
/// in its native mode is invisible to XInput and only shows up through the
/// legacy winmm joystick API. Polling just XInput is why "my controller isn't
/// detected" happens with a Sony pad.
///
/// Two behaviours that make it feel right rather than merely work:
///  * TYPEMATIC repeat — hold a direction and it repeats after an initial
///    delay, then faster, like a keyboard. Without it you must tap per tile.
///  * HYSTERESIS — the stick must return well inside the dead zone before it
///    can fire again, otherwise a resting thumb machine-guns the list.
/// </summary>
public sealed class Gamepad : IDisposable
{
    // ---- XInput -------------------------------------------------------
    [StructLayout(LayoutKind.Sequential)]
    private struct XINPUT_GAMEPAD
    {
        public ushort wButtons;
        public byte bLeftTrigger, bRightTrigger;
        public short sThumbLX, sThumbLY, sThumbRX, sThumbRY;
    }
    [StructLayout(LayoutKind.Sequential)]
    private struct XINPUT_STATE { public uint dwPacketNumber; public XINPUT_GAMEPAD Gamepad; }

    [DllImport("xinput1_4.dll", EntryPoint = "XInputGetState")]
    private static extern uint XInputGetState14(uint i, out XINPUT_STATE s);
    [DllImport("xinput9_1_0.dll", EntryPoint = "XInputGetState")]
    private static extern uint XInputGetState91(uint i, out XINPUT_STATE s);

    private static bool _useLegacyXInput;
    private static uint XGet(uint i, out XINPUT_STATE s)
    {
        if (!_useLegacyXInput)
        {
            try { return XInputGetState14(i, out s); }
            catch (DllNotFoundException) { _useLegacyXInput = true; }
            catch (EntryPointNotFoundException) { _useLegacyXInput = true; }
        }
        try { return XInputGetState91(i, out s); }
        catch { s = default; return 1; }
    }

    // ---- legacy joystick (Sony pads, generic HID) ----------------------
    [StructLayout(LayoutKind.Sequential)]
    private struct JOYINFOEX
    {
        public int dwSize, dwFlags;
        public int dwXpos, dwYpos, dwZpos, dwRpos, dwUpos, dwVpos;
        public int dwButtons, dwButtonNumber, dwPOV, dwReserved1, dwReserved2;
    }
    [DllImport("winmm.dll")] private static extern int joyGetPosEx(int id, ref JOYINFOEX pji);
    private const int JOY_RETURNALL = 0x000000FF;

    // XInput button bits
    private const ushort UP = 0x0001, DOWN = 0x0002, LEFT = 0x0004, RIGHT = 0x0008,
                         START = 0x0010, BACK = 0x0020, LB = 0x0100, RB = 0x0200,
                         A = 0x1000, B = 0x2000, X = 0x4000, Y = 0x8000;

    private const short DEAD = 12000;   // fire above this
    private const short REARM = 7000;   // must fall below this to fire again

    private readonly DispatcherTimer _timer;
    private Pad _held = Pad.None;
    private DateTime _heldSince;
    private DateTime _lastRepeat;
    private bool _stickArmed = true;

    public event Action<Pad>? Pressed;
    /// <summary>True while any pad is actually connected.</summary>
    public bool Connected { get; private set; }

    public Gamepad()
    {
        // 16 ms is the right cadence for input - but ONLY once something is
        // actually plugged in. See ScanDue() for why an empty slot is expensive.
        _timer = new DispatcherTimer(DispatcherPriority.Input)
        {
            Interval = TimeSpan.FromMilliseconds(16)
        };
        _timer.Tick += (_, _) => Poll();
        _timer.Start();
    }

    /// <summary>
    /// One slot when we know which, all of them only on a discovery tick.
    /// </summary>
    private Pad ReadPads()
    {
        if (_slot >= 0)
        {
            if (XGet((uint)_slot, out var st) == 0)
            {
                Connected = true;
                return FromState(st);
            }
            // It went away: fall through to a sweep and let the next tick settle.
            _slot = -1;
            Connected = false;
        }

        if (!ScanDue()) return Pad.None;

        Connected = false;
        Pad now = ReadXInput();
        if (now == Pad.None && !Connected) now = ReadLegacy();
        return now;
    }

    private Pad ReadXInput()
    {
        for (uint i = 0; i < 4; i++)
        {
            if (XGet(i, out var st) != 0) continue;
            Connected = true;
            _slot = (int)i;
            return FromState(st);
        }
        return Pad.None;
    }

    /// <summary>Decode one XInput frame. Split out of the scan so the fast path
    /// (one known slot) and the discovery path share exactly one reading of the
    /// buttons - two copies would drift the moment either is touched.</summary>
    private Pad FromState(XINPUT_STATE st)
    {
        var g = st.Gamepad;

        if ((g.wButtons & A) != 0) return Pad.A;
        if ((g.wButtons & B) != 0) return Pad.B;
        if ((g.wButtons & X) != 0) return Pad.X;
        if ((g.wButtons & Y) != 0) return Pad.Y;
        if ((g.wButtons & LB) != 0) return Pad.LB;
        if ((g.wButtons & RB) != 0) return Pad.RB;
        if ((g.wButtons & START) != 0) return Pad.Start;
        if ((g.wButtons & BACK) != 0) return Pad.Back;
        if (g.bLeftTrigger > 160) return Pad.LT;
        if (g.bRightTrigger > 160) return Pad.RT;

        if ((g.wButtons & UP) != 0) return Pad.Up;
        if ((g.wButtons & DOWN) != 0) return Pad.Down;
        if ((g.wButtons & LEFT) != 0) return Pad.Left;
        if ((g.wButtons & RIGHT) != 0) return Pad.Right;

        // Stick, with hysteresis so a resting thumb cannot repeat.
        int ax = Math.Abs((int)g.sThumbLX), ay = Math.Abs((int)g.sThumbLY);
        if (ax < REARM && ay < REARM) _stickArmed = true;
        if (_stickArmed && (ax > DEAD || ay > DEAD))
        {
            if (ax > ay) return g.sThumbLX > 0 ? Pad.Right : Pad.Left;
            return g.sThumbLY > 0 ? Pad.Up : Pad.Down;
        }
        return Pad.None;
    }

    private Pad ReadLegacy()
    {
        var ji = new JOYINFOEX { dwSize = Marshal.SizeOf<JOYINFOEX>(), dwFlags = JOY_RETURNALL };
        for (int id = 0; id < 4; id++)
        {
            if (joyGetPosEx(id, ref ji) != 0) continue;
            Connected = true;

            // POV hat = the d-pad on most HID pads (values in hundredths of a degree)
            if (ji.dwPOV != -1 && (ji.dwPOV & 0xFFFF) != 0xFFFF)
            {
                int deg = ji.dwPOV / 100;
                if (deg >= 315 || deg < 45) return Pad.Up;
                if (deg is >= 45 and < 135) return Pad.Right;
                if (deg is >= 135 and < 225) return Pad.Down;
                if (deg is >= 225 and < 315) return Pad.Left;
            }

            // Axes are 0..65535 with 32767 centre.
            int cx = ji.dwXpos - 32767, cy = ji.dwYpos - 32767;
            int ax = Math.Abs(cx), ay = Math.Abs(cy);
            if (ax < REARM && ay < REARM) _stickArmed = true;
            if (_stickArmed && (ax > DEAD || ay > DEAD))
            {
                if (ax > ay) return cx > 0 ? Pad.Right : Pad.Left;
                return cy > 0 ? Pad.Down : Pad.Up;   // legacy Y is inverted vs XInput
            }

            // Buttons are brand-dependent on the legacy path; map the common
            // DualSense/DualShock layout (✕ ◯ □ △ L1 R1 Share Options).
            int b = ji.dwButtons;
            if ((b & 0x0001) != 0) return Pad.X;      // □
            if ((b & 0x0002) != 0) return Pad.A;      // ✕  = confirm
            if ((b & 0x0004) != 0) return Pad.B;      // ◯  = back
            if ((b & 0x0008) != 0) return Pad.Y;      // △
            if ((b & 0x0010) != 0) return Pad.LB;
            if ((b & 0x0020) != 0) return Pad.RB;
            if ((b & 0x0100) != 0) return Pad.Back;
            if ((b & 0x0200) != 0) return Pad.Start;
            return Pad.None;
        }
        return Pad.None;
    }

    // Ticks since the last full discovery sweep, and the slot that answered it.
    private int _ticks;
    private int _slot = -1;

    /// <summary>
    /// 🔴🔴 QUERYING AN EMPTY CONTROLLER SLOT IS NOT FREE, AND THIS LOOP USED TO
    /// DO IT 480 TIMES A SECOND.
    ///
    /// The old comment here said polling "costs nothing measurable when no pad
    /// is attached (we early-out)" - but the early-out is the RESULT of the
    /// call, not a way to avoid it: every 16ms tick asked XInput about all four
    /// slots and then winmm's joyGetPosEx about four more, and a query to a slot
    /// with nothing in it goes all the way down to the device layer. Microsoft's
    /// own guidance is to poll disconnected slots at a much slower rate for
    /// exactly this reason. Measured on this machine with no pad connected: the
    /// shell idled at ~100% of one core, and it was still ~85% with every
    /// animation in the app turned off - which is what ruled out the visuals and
    /// pointed here.
    ///
    /// So: a full sweep runs about twice a second, which is fast enough for
    /// "I just switched my controller on"; once a slot answers, that ONE slot is
    /// read at the full 16ms so input stays instant.
    /// </summary>
    private bool ScanDue() => (_ticks % 30) == 0;

    private void Poll()
    {
        _ticks++;
        Pad now = ReadPads();

        var t = DateTime.UtcNow;

        if (now == Pad.None) { _held = Pad.None; return; }

        if (now != _held)
        {
            _held = now;
            _heldSince = t;
            _lastRepeat = t;
            if (now is Pad.Up or Pad.Down or Pad.Left or Pad.Right) _stickArmed = false;
            Pressed?.Invoke(now);
            return;
        }

        // Typematic: only directions repeat. A held "A" must never re-fire.
        if (_held is not (Pad.Up or Pad.Down or Pad.Left or Pad.Right)) return;

        double sinceDown = (t - _heldSince).TotalMilliseconds;
        double sinceRep = (t - _lastRepeat).TotalMilliseconds;
        if (sinceDown < 420) return;                    // initial delay
        double rate = sinceDown > 1600 ? 55 : 110;      // accelerate while held
        if (sinceRep < rate) return;
        _lastRepeat = t;
        Pressed?.Invoke(_held);
    }


    // =====================================================================
    //  WHAT IS ACTUALLY PLUGGED IN
    //
    // 🔴 THE POINT IS TO BE HONEST, NOT TO REMAP PADDLES. Winhanced's controller
    // page targets handhelds (ROG Ally, MSI Claw, Legion Go) and on an ordinary
    // PC it says "No configurable paddles on this device" - so the useful thing
    // a desktop console can tell a user on a couch is simply "your controller IS
    // seen, and here is which one". Paddle remapping needs each vendor's own SDK
    // and a device that HAS paddles; claiming it here would be a button that
    // cannot work.
    // =====================================================================

    public readonly record struct PadInfo(string Name, string Kind, bool Wireless);

    [StructLayout(LayoutKind.Sequential)]
    private struct XINPUT_CAPABILITIES
    {
        public byte Type, SubType;
        public ushort Flags;
        public XINPUT_GAMEPAD Gamepad;
        public ushort wLeftMotorSpeed, wRightMotorSpeed;
    }

    [DllImport("xinput1_4.dll", EntryPoint = "XInputGetCapabilities")]
    private static extern int XInputGetCaps14(int i, int flags, ref XINPUT_CAPABILITIES c);
    [DllImport("xinput9_1_0.dll", EntryPoint = "XInputGetCapabilities")]
    private static extern int XInputGetCaps91(int i, int flags, ref XINPUT_CAPABILITIES c);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct JOYCAPS
    {
        public ushort wMid, wPid;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string szPname;
        public int wXmin, wXmax, wYmin, wYmax, wZmin, wZmax;
        public int wNumButtons, wPeriodMin, wPeriodMax;
        public int wRmin, wRmax, wUmin, wUmax, wVmin, wVmax;
        public int wCaps, wMaxAxes, wNumAxes, wMaxButtons;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string szRegKey;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string szOEMVxD;
    }

    [DllImport("winmm.dll", CharSet = CharSet.Unicode, EntryPoint = "joyGetDevCapsW")]
    private static extern int joyGetDevCaps(int id, ref JOYCAPS caps, int size);

    private static string SubTypeName(byte st) => st switch
    {
        1 => "שלט משחק",
        2 => "הגה",
        3 => "ג׳ויסטיק ארקייד",
        4 => "ג׳ויסטיק טיסה",
        5 => "משטח ריקוד",
        6 or 7 => "גיטרה",
        8 => "תופים",
        _ => "התקן משחק",
    };

    /// <summary>
    /// Every controller Windows can see right now. XInput first (it names the
    /// KIND), then the legacy joystick API - which is the only one that sees a
    /// PlayStation pad in its native mode, and the only one that reports a
    /// product NAME.
    /// </summary>
    public static List<PadInfo> Probe()
    {
        var list = new List<PadInfo>();
        for (int i = 0; i < 4; i++)
        {
            var caps = new XINPUT_CAPABILITIES();
            int rc;
            try { rc = XInputGetCaps14(i, 0, ref caps); }
            catch { try { rc = XInputGetCaps91(i, 0, ref caps); } catch { rc = -1; } }
            if (rc != 0) continue;
            // Flags bit 0x0004 = WIRELESS in XINPUT_CAPS.
            list.Add(new PadInfo($"שלט XInput {i + 1}", SubTypeName(caps.SubType), (caps.Flags & 0x0004) != 0));
        }

        for (int i = 0; i < 16; i++)
        {
            var jc = new JOYCAPS();
            int rc;
            try { rc = joyGetDevCaps(i, ref jc, Marshal.SizeOf<JOYCAPS>()); }
            catch { break; }
            if (rc != 0 || string.IsNullOrWhiteSpace(jc.szPname)) continue;
            // An XInput pad is ALSO enumerated here; showing it twice would read
            // as two controllers. The name is the tell - a real DirectInput-only
            // device is named by its driver, an XInput one by the generic shim.
            if (jc.szPname.Contains("XBOX", System.StringComparison.OrdinalIgnoreCase) && list.Count > 0) continue;
            list.Add(new PadInfo(jc.szPname.Trim(), $"{jc.wNumButtons} כפתורים", false));
        }
        return list;
    }

    public void Dispose() => _timer.Stop();
}
