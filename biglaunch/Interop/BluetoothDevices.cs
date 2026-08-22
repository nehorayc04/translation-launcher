using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace BigLaunch.Interop;

/// <summary>
/// One Bluetooth device, in the only four terms the shell can act on: what to
/// call it, how to address it, whether it is live right now, and whether
/// Windows already knows it. Everything else bthprops reports (class-of-device,
/// last-seen timestamps) answers a question a 10ft UI never asks.
/// </summary>
public sealed record BtDevice(string Name, ulong Address, bool Connected, bool Paired);

/// <summary>
/// The DEVICE half of the Bluetooth panel — list, discover, pair, forget.
///
/// 🔴 WHY THIS EXISTS AT ALL: the reason a controller-driven shell needs
/// Bluetooth is the controller. A pad that drops mid-session cannot be
/// re-paired from a couch through the Windows Settings app — you would need the
/// keyboard the shell exists to make unnecessary, and you cannot navigate to it
/// with the device that just disconnected. So the one flow that must work
/// without a mouse is exactly this one.
///
/// SystemStatus.BluetoothOn() already answers "is a radio switched on" and
/// holds its own cache for the header pill; this file deliberately does not
/// duplicate that. RadioPresent() here answers the different question the panel
/// asks — "is there hardware at all", i.e. should this screen exist.
///
/// Every entry point is best-effort. A machine with no Bluetooth stack does not
/// ship bthprops.cpl at all, so the P/Invoke itself throws DllNotFoundException
/// on the FIRST call — that is the correct answer (no devices), not an error,
/// and it must never reach a background poll's caller.
/// </summary>
public static class BluetoothDevices
{
    // ---- native layout ---------------------------------------------------
    //
    // Field ORDER is the contract: these are marshalled straight onto the C
    // structs, so a reordered or missing field silently shifts every field
    // after it and the API reads garbage rather than failing.
    //
    // No explicit Pack: bthdef.h uses no #pragma pack, so the natural
    // alignment the marshaller applies is exactly what the SDK compiles to.
    // Forcing Pack = 1 here would MISALIGN the 8-byte fields, not fix anything.

#pragma warning disable CS0649, CS0169
    // Native fills these; C# only ever reads them (or not at all — several exist
    // purely to hold the layout together), so the compiler would otherwise warn
    // that they are never assigned.

    [StructLayout(LayoutKind.Sequential)]
    private struct BLUETOOTH_FIND_RADIO_PARAMS
    {
        public uint dwSize;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct SYSTEMTIME
    {
        public ushort wYear, wMonth, wDayOfWeek, wDay;
        public ushort wHour, wMinute, wSecond, wMilliseconds;
    }

    /// <summary>
    /// The five "fReturn*" fields are FILTERS, not projections: they decide
    /// which devices come back, never which fields get populated. fConnected on
    /// the result is filled either way.
    /// </summary>
    [StructLayout(LayoutKind.Sequential)]
    private struct BLUETOOTH_DEVICE_SEARCH_PARAMS
    {
        public uint dwSize;
        // 🔴 Win32 BOOL is a 4-byte int. MarshalAs(Bool) spells that out, but
        // it is NOT what makes this struct correct: a bare `bool` field ALREADY
        // marshals as a 4-byte BOOL, so the layout is 40 bytes either way
        // (measured: plain and MarshalAs(Bool) give identical offsets).
        // The real trap is the mirror image of the obvious one. Anything that
        // narrows these to a byte - MarshalAs(U1), or "tidying" them away to a
        // C-looking 1-byte flag - slides every later field forward and lands
        // hRadio on rubbish, which presents as an empty device list rather than
        // a crash. Keep them 4 bytes wide; do not "optimise" them to U1.
        [MarshalAs(UnmanagedType.Bool)] public bool fReturnAuthenticated;
        [MarshalAs(UnmanagedType.Bool)] public bool fReturnRemembered;
        [MarshalAs(UnmanagedType.Bool)] public bool fReturnUnknown;
        [MarshalAs(UnmanagedType.Bool)] public bool fReturnConnected;
        [MarshalAs(UnmanagedType.Bool)] public bool fIssueInquiry;
        public byte cTimeoutMultiplier;
        public IntPtr hRadio;
    }

    /// <summary>
    /// 🔴 CharSet.Unicode is load-bearing, not decoration. szName is WCHAR[248];
    /// ByValTStr takes its width from the STRUCT's CharSet, so the Ansi default
    /// would marshal it as 248 BYTES — the struct comes out 248 bytes short, the
    /// API rejects it on dwSize, and every name that did survive is mojibake.
    /// </summary>
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct BLUETOOTH_DEVICE_INFO
    {
        public uint dwSize;
        // BLUETOOTH_ADDRESS is a union over a 6-byte array and a ULONGLONG, so
        // it is 8 bytes wide and the top 2 bytes are ALWAYS zero. Taking it as a
        // ulong is the union's own long view — no packing to undo.
        public ulong Address;
        public uint ulClassofDevice;
        [MarshalAs(UnmanagedType.Bool)] public bool fConnected;
        [MarshalAs(UnmanagedType.Bool)] public bool fRemembered;
        [MarshalAs(UnmanagedType.Bool)] public bool fAuthenticated;
        public SYSTEMTIME stLastSeen;
        public SYSTEMTIME stLastUsed;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = BLUETOOTH_MAX_NAME_SIZE)]
        public string szName;
    }
#pragma warning restore CS0649, CS0169

    private const int BLUETOOTH_MAX_NAME_SIZE = 248;
    private const uint ERROR_SUCCESS = 0;
    private const uint ERROR_NO_MORE_ITEMS = 259;
    private const uint BLUETOOTH_SERVICE_ENABLE = 0x0001;
    private const uint MITM_PROTECTION_NOT_REQUIRED = 0;

    // A discovery that never terminates would hang the calling thread forever;
    // a paired list of thousands would be a UI bug either way. Bound both.
    private const int MaxResults = 64;

    // CharSet stays at the default on the DllImports: the export names carry no
    // W/A suffix, and the struct above already declares its own text width.
    [DllImport("bthprops.cpl", SetLastError = true)]
    private static extern IntPtr BluetoothFindFirstRadio(ref BLUETOOTH_FIND_RADIO_PARAMS p, out IntPtr radio);
    [DllImport("bthprops.cpl", SetLastError = true)]
    private static extern bool BluetoothFindRadioClose(IntPtr find);

    [DllImport("bthprops.cpl", SetLastError = true)]
    private static extern IntPtr BluetoothFindFirstDevice(ref BLUETOOTH_DEVICE_SEARCH_PARAMS p,
                                                          ref BLUETOOTH_DEVICE_INFO info);
    [DllImport("bthprops.cpl", SetLastError = true)]
    private static extern bool BluetoothFindNextDevice(IntPtr find, ref BLUETOOTH_DEVICE_INFO info);
    [DllImport("bthprops.cpl", SetLastError = true)]
    private static extern bool BluetoothFindDeviceClose(IntPtr find);

    [DllImport("bthprops.cpl", SetLastError = true)]
    private static extern uint BluetoothAuthenticateDeviceEx(IntPtr hwndParent, IntPtr radio,
                                                             ref BLUETOOTH_DEVICE_INFO info,
                                                             IntPtr oobData, uint authRequirement);

    // Takes a POINTER to the 8-byte address union, not the value.
    [DllImport("bthprops.cpl", SetLastError = true)]
    private static extern uint BluetoothRemoveDevice(ref ulong address);

    // Called twice: once with services = null to learn the count, then with a
    // buffer of that size.
    [DllImport("bthprops.cpl", SetLastError = true)]
    private static extern uint BluetoothEnumerateInstalledServices(IntPtr radio,
                                                                   ref BLUETOOTH_DEVICE_INFO info,
                                                                   ref uint count,
                                                                   [In, Out] Guid[]? services);

    [DllImport("bthprops.cpl", SetLastError = true)]
    private static extern uint BluetoothSetServiceState(IntPtr radio, ref BLUETOOTH_DEVICE_INFO info,
                                                        ref Guid service, uint serviceFlags);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr h);

    /// <summary>Both of these mean "nothing left to do", not failure.</summary>
    private static bool Ok(uint rc) => rc == ERROR_SUCCESS || rc == ERROR_NO_MORE_ITEMS;

    // ---- handle discipline ----------------------------------------------

    /// <summary>
    /// Runs <paramref name="body"/> against the first local radio and
    /// guarantees the radio handle AND the find handle are released on every
    /// path — including when the P/Invoke itself throws because the Bluetooth
    /// stack is absent. Every public entry point goes through here so that
    /// hygiene exists in exactly one place; these calls come from a UI panel
    /// that can be reopened all evening, and one leaked handle per call is a
    /// real leak.
    ///
    /// Scoped to the FIRST radio rather than passing NULL ("all radios") on
    /// purpose: the handle that found a device has to be the same one we later
    /// authenticate and enable services on, or the pair lands on a radio that
    /// never saw it.
    /// </summary>
    private static T WithRadio<T>(Func<IntPtr, T> body, T fallback)
    {
        IntPtr find = IntPtr.Zero, radio = IntPtr.Zero;
        try
        {
            var p = new BLUETOOTH_FIND_RADIO_PARAMS
            {
                dwSize = (uint)Marshal.SizeOf<BLUETOOTH_FIND_RADIO_PARAMS>()
            };
            find = BluetoothFindFirstRadio(ref p, out radio);
            if (find == IntPtr.Zero) return fallback;
            return body(radio);
        }
        catch { return fallback; }
        finally
        {
            // 🔴 A finally is NOT covered by its own catch: anything raised here
            // sails straight past the catch above and out of the public entry
            // point, which is the single thing this class promises never to do.
            // And it is reachable: P/Invoke binds per export, lazily, so
            // BluetoothFindRadioClose resolves on ITS first call - independently
            // of BluetoothFindFirstRadio having resolved a moment earlier. A
            // partial or shimmed bthprops.cpl (third-party stack, Wine, emulated
            // ARM64) throws EntryPointNotFoundException right here, into a
            // background poll. Cleanup swallows its own failures.
            Close(radio, find);
        }
    }

    /// <summary>Release the radio and find handles; never throws.</summary>
    private static void Close(IntPtr radio, IntPtr find)
    {
        if (radio != IntPtr.Zero) { try { CloseHandle(radio); } catch { /* nothing left to do */ } }
        if (find != IntPtr.Zero) { try { BluetoothFindRadioClose(find); } catch { /* ditto */ } }
    }

    /// <summary>Release a device-enumeration handle; never throws.</summary>
    private static void CloseFind(IntPtr find)
    {
        if (find != IntPtr.Zero) { try { BluetoothFindDeviceClose(find); } catch { /* ditto */ } }
    }

    /// <summary>
    /// Step the enumeration on. dwSize is re-stamped HERE, not at the tail of
    /// the loop body, so that a `continue` can never skip it: measured, this
    /// build of bthprops writes dwSize back on output and does not re-validate
    /// it on FindNextDevice, but MSDN specifies the field as caller-set and
    /// staking the device list on one build's leniency is a needless coin-flip.
    /// </summary>
    private static bool Advance(IntPtr find, ref BLUETOOTH_DEVICE_INFO info)
    {
        info.dwSize = (uint)Marshal.SizeOf<BLUETOOTH_DEVICE_INFO>();
        return BluetoothFindNextDevice(find, ref info);
    }

    // ---- enumeration -----------------------------------------------------

    private static BLUETOOTH_DEVICE_SEARCH_PARAMS Search(IntPtr radio)
        => new()
        {
            // dwSize MUST be set before every call or the API fails the whole
            // thing with ERROR_INVALID_PARAMETER — it is the version tag, not a
            // convenience.
            dwSize = (uint)Marshal.SizeOf<BLUETOOTH_DEVICE_SEARCH_PARAMS>(),
            hRadio = radio
        };

    /// <summary>
    /// Walks one search to completion. The find handle is closed on every path;
    /// results are de-duplicated by address because a duplicated row in a 10ft
    /// list reads as a broken UI.
    /// </summary>
    private static List<BtDevice> Enumerate(ref BLUETOOTH_DEVICE_SEARCH_PARAMS sp, bool dropUnnamed)
    {
        var list = new List<BtDevice>();
        var seen = new HashSet<ulong>();
        IntPtr find = IntPtr.Zero;
        try
        {
            var info = new BLUETOOTH_DEVICE_INFO
            {
                dwSize = (uint)Marshal.SizeOf<BLUETOOTH_DEVICE_INFO>()
            };

            find = BluetoothFindFirstDevice(ref sp, ref info);
            if (find == IntPtr.Zero) return list;

            // 🔴 The bound has to count ITERATIONS, not accepted rows. Every skip
            // below (unnamed, duplicate) leaves list.Count untouched, so capping
            // list.Count alone bounds nothing on the one path that actually
            // blocks the caller: Discover() drops EVERY unnamed device, and an
            // inquiry in a crowded room is mostly unnamed BLE beacons. Scan()
            // already counts iterations for exactly this reason; so must this.
            int scanned = 0;

            do
            {
                if (++scanned > MaxResults) break;

                string name = (info.szName ?? string.Empty).Trim();

                // An unnamed MAC is not something a user can identify or choose,
                // so it is noise in a discovery list. In the PAIRED list the row
                // is still actionable (it can be forgotten), so it keeps the
                // address as its label instead of rendering blank.
                if (name.Length == 0)
                {
                    if (dropUnnamed) continue;
                    name = AddressText(info.Address);
                }

                if (!seen.Add(info.Address)) continue;

                list.Add(new BtDevice(
                    name,
                    info.Address,
                    info.fConnected,
                    // "Paired" to a user means "Windows already knows this one",
                    // which covers both authenticated and merely remembered.
                    info.fAuthenticated || info.fRemembered));

                if (list.Count >= MaxResults) break;
            }
            while (Advance(find, ref info));

            return list;
        }
        catch { return list; }   // partial results beat none
        finally
        {
            CloseFind(find);
        }
    }

    // ---- public surface --------------------------------------------------

    /// <summary>
    /// True when the machine has Bluetooth hardware at all — i.e. whether the
    /// panel should exist. Not the same question as
    /// SystemStatus.BluetoothOn(), which asks whether it is switched ON.
    /// </summary>
    public static bool RadioPresent() => WithRadio(_ => true, false);

    /// <summary>
    /// Devices Windows already knows: authenticated, remembered, or connected
    /// right now. Fast — it reads the local cache and issues NO inquiry, which
    /// is the whole reason this is safe to call when the panel opens.
    /// </summary>
    public static List<BtDevice> Paired() => WithRadio(radio =>
    {
        var sp = Search(radio);
        sp.fReturnAuthenticated = true;
        sp.fReturnRemembered = true;
        sp.fReturnConnected = true;
        sp.fReturnUnknown = false;
        // 🔴 An inquiry here would make simply OPENING the panel take six
        // seconds to list devices the machine already knows by heart.
        sp.fIssueInquiry = false;
        return Enumerate(ref sp, dropUnnamed: false);
    }, new List<BtDevice>());

    /// <summary>
    /// 🔴 BLOCKS for roughly <paramref name="seconds"/> — it runs a real radio
    /// inquiry. NEVER call this on the UI thread; the shell will freeze for the
    /// entire scan.
    ///
    /// Returns nearby devices that are NOT yet paired. Unnamed results are
    /// dropped: a bare MAC address is not something anyone can pick out of a
    /// list from a couch.
    /// </summary>
    public static List<BtDevice> Discover(int seconds = 6) => WithRadio(radio =>
    {
        var sp = Search(radio);
        sp.fReturnUnknown = true;
        sp.fReturnAuthenticated = false;
        sp.fReturnRemembered = false;
        sp.fReturnConnected = false;
        sp.fIssueInquiry = true;
        sp.cTimeoutMultiplier = Multiplier(seconds);
        return Enumerate(ref sp, dropUnnamed: true);
    }, new List<BtDevice>());

    /// <summary>
    /// The inquiry timeout is expressed in 1.28-second units and the API caps
    /// it at 48 (~61s); asking for more is rejected outright rather than
    /// clamped, so the clamp happens here.
    /// </summary>
    private static byte Multiplier(int seconds)
        => (byte)Math.Clamp(seconds / 1.28, 1.0, 48.0);

    /// <summary>
    /// 🔴 BLOCKS — it may run an inquiry to locate the device and then waits on
    /// the pairing handshake. Call it off the UI thread.
    ///
    /// Modern pads and headsets negotiate Just Works / numeric comparison, which
    /// MITMProtectionNotRequired satisfies without ever asking for a PIN — so
    /// this completes with no keyboard, which is the entire point.
    /// </summary>
    public static bool Pair(ulong address) => WithRadio(radio =>
    {
        var info = FindInfo(radio, address);
        if (info is null) return false;

        var target = info.Value;
        uint rc = BluetoothAuthenticateDeviceEx(IntPtr.Zero, radio, ref target,
                                                IntPtr.Zero /* no out-of-band data */,
                                                MITM_PROTECTION_NOT_REQUIRED);
        if (!Ok(rc)) return false;

        // 🔴 AUTHENTICATING IS NOT CONNECTING. Windows will happily list the
        // device as paired and never carry a byte to it, because none of its
        // services were enabled — the classic "it says it's paired but the
        // controller does nothing" state. Turning them on is what actually
        // finishes the job.
        //
        // Best-effort by design: the pairing itself already succeeded, so a
        // failure here must not be reported as a failed pair.
        EnableServices(radio, address, target);
        return true;
    }, false);

    /// <summary>Forget a device. Cheap and non-blocking.</summary>
    public static bool Remove(ulong address)
    {
        try
        {
            ulong addr = address;   // passed by pointer; keep the caller's value intact
            return Ok(BluetoothRemoveDevice(ref addr));
        }
        catch { return false; }
    }

    /// <summary>"AA:BB:CC:DD:EE:FF" — the low 6 bytes, most significant first.</summary>
    public static string AddressText(ulong address)
    {
        try
        {
            return $"{(address >> 40) & 0xFF:X2}:{(address >> 32) & 0xFF:X2}:" +
                   $"{(address >> 24) & 0xFF:X2}:{(address >> 16) & 0xFF:X2}:" +
                   $"{(address >> 8) & 0xFF:X2}:{address & 0xFF:X2}";
        }
        catch { return string.Empty; }
    }

    // ---- pairing internals -----------------------------------------------

    /// <summary>
    /// 🔴 CAN BLOCK: falls back to a short inquiry when the address is not in
    /// the local cache.
    ///
    /// BluetoothAuthenticateDeviceEx wants a whole populated device record, not
    /// an address, so the record has to be found again. The cached pass runs
    /// first and costs nothing — after a Discover() the device is still in the
    /// cache — and the inquiry only happens when Pair() was called cold.
    /// </summary>
    private static BLUETOOTH_DEVICE_INFO? FindInfo(IntPtr radio, ulong address)
    {
        var hit = Scan(radio, address, inquiry: false);
        return hit ?? Scan(radio, address, inquiry: true);
    }

    private static BLUETOOTH_DEVICE_INFO? Scan(IntPtr radio, ulong address, bool inquiry)
    {
        IntPtr find = IntPtr.Zero;
        try
        {
            var sp = Search(radio);
            // Every category, because the caller's address may be an unpaired
            // device just discovered or one already remembered but not yet
            // authenticated.
            sp.fReturnAuthenticated = true;
            sp.fReturnRemembered = true;
            sp.fReturnUnknown = true;
            sp.fReturnConnected = true;
            sp.fIssueInquiry = inquiry;
            sp.cTimeoutMultiplier = inquiry ? Multiplier(5) : (byte)0;

            var info = new BLUETOOTH_DEVICE_INFO
            {
                dwSize = (uint)Marshal.SizeOf<BLUETOOTH_DEVICE_INFO>()
            };

            find = BluetoothFindFirstDevice(ref sp, ref info);
            if (find == IntPtr.Zero) return null;

            int guard = 0;
            do
            {
                if (info.Address == address) return info;
                if (++guard >= MaxResults) break;
            }
            while (Advance(find, ref info));

            return null;
        }
        catch { return null; }
        finally
        {
            CloseFind(find);
        }
    }

    /// <summary>
    /// Enables every service the freshly-paired device installed. Best-effort
    /// throughout: a device that exposes no enumerable services, or one service
    /// that refuses, must not undo a pairing that already worked.
    /// </summary>
    private static void EnableServices(IntPtr radio, ulong address, BLUETOOTH_DEVICE_INFO afterAuth)
    {
        try
        {
            // Re-read the record: the copy we authenticated with predates the
            // pairing, so its flags describe the device as it was BEFORE. No
            // inquiry — it is definitively in the cache by now.
            var fresh = Scan(radio, address, inquiry: false) ?? afterAuth;

            uint count = 0;
            // First pass with a null buffer only asks "how many?" — a non-zero
            // return here is normal (ERROR_MORE_DATA), so the count is what is
            // worth testing, not the code.
            BluetoothEnumerateInstalledServices(radio, ref fresh, ref count, null);
            if (count == 0 || count > 64) return;

            var services = new Guid[count];
            if (!Ok(BluetoothEnumerateInstalledServices(radio, ref fresh, ref count, services))) return;

            for (int i = 0; i < count && i < services.Length; i++)
            {
                try
                {
                    var g = services[i];
                    BluetoothSetServiceState(radio, ref fresh, ref g, BLUETOOTH_SERVICE_ENABLE);
                }
                catch { /* one stubborn service must not stop the others */ }
            }
        }
        catch { /* pairing already succeeded; this is polish */ }
    }
}
