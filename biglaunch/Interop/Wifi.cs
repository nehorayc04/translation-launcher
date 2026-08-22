using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.NetworkInformation;
using System.Runtime.InteropServices;
using System.Security;
using System.Text;

namespace BigLaunch.Interop;

/// <summary>One row of the Wi-Fi list. <c>SignalPercent</c> is already 0..100.</summary>
public sealed record WifiNetwork(string Ssid, int SignalPercent, string Security,
                                 bool Connected, bool HasProfile);

/// <summary>
/// The Wi-Fi half of the network panel, entirely on wlanapi.dll.
///
/// 🔴 WHY THIS EXISTS AT ALL: the same argument as <see cref="Volume"/>. A
/// handheld carried to a hotel or a friend's house has to join a network before
/// anything else in this shell works - the store, the translation download, the
/// update check. "Alt-tab to the Windows flyout" is exactly the thing a 10ft
/// shell exists to avoid, and on a device with no keyboard it is not reliably
/// possible at all.
///
/// It is wlanapi rather than the WinRT Wi-Fi classes because the shipped
/// artifact is ONE ~2MB file: WinRT would mean a Windows SDK target framework
/// and a much heavier exe, to reach an API that answers the same questions.
///
/// Every entry point is best-effort. A desktop with no wireless card, a laptop
/// whose driver is mid-restart, and a machine with WLAN AutoConfig disabled must
/// all report "unavailable" and let the UI omit the section - never take down
/// the shell from a background poll.
/// </summary>
public static class Wifi
{
    // ---- constants -------------------------------------------------------

    private const uint ClientVersion = 2;              // the Vista+ WLAN API

    // WLAN_INTERFACE_STATE
    private const int InterfaceNotReady = 0;
    private const int InterfaceConnected = 1;

    // WLAN_INTF_OPCODE
    private const int OpcodeRadioState = 4;
    private const int OpcodeCurrentConnection = 7;

    // DOT11_RADIO_STATE
    private const int RadioStateUnknown = 0, RadioStateOn = 1, RadioStateOff = 2;

    // WLAN_CONNECTION_MODE / DOT11_BSS_TYPE
    private const int ConnectionModeProfile = 0;
    private const int BssTypeInfrastructure = 1;

    // WlanGetAvailableNetworkList dwFlags:
    //   INCLUDE_ALL_ADHOC_PROFILES (1) | INCLUDE_ALL_MANUAL_HIDDEN_PROFILES (2).
    // Without these, a network the user has a saved profile for but which is not
    // in range right now is simply absent - so a row that should read "saved,
    // out of range" reads as if the network never existed.
    private const uint IncludeAllProfiles = 0x00000003;

    // DOT11_AUTH_ALGORITHM (windot11.h).
    //
    // 🔴 RSNA (6) IS ENTERPRISE AND RSNA_PSK (7) IS THE HOME ONE. They sit one
    // apart and are trivially transposed, and transposing them mislabels every
    // network on the list at once: ordinary WPA2 home APs all report 7, so they
    // would fall through to the unknown bucket, while the handful of corporate
    // 802.1X networks would be advertised as PSK and offered a password box they
    // cannot use.
    private const uint AuthOpen = 1, AuthSharedKey = 2, AuthWpa = 3, AuthWpaPsk = 4,
                       AuthWpaNone = 5, AuthRsna = 6, AuthRsnaPsk = 7,
                       AuthWpa3Ent192 = 8, AuthWpa3Sae = 9, AuthOwe = 10, AuthWpa3Ent = 11;

    // DOT11_CIPHER_ALGORITHM - only "is there any cipher at all" matters here.
    private const uint CipherNone = 0x00;

    // Every WLAN_*_LIST is { DWORD dwNumberOfItems; DWORD dwIndex; T items[1]; },
    // so the array always begins 8 bytes in. dwIndex is the service's own cursor
    // and means nothing to us.
    private const int ListHeaderBytes = 8;

    // ---- structures ------------------------------------------------------
    //
    // 🔴 CharSet.Unicode IS LOAD-BEARING ON EVERY STRUCT BELOW THAT HAS A
    // ByValTStr. Without it the marshaller lays the fixed name buffer out as 256
    // ANSI bytes instead of 256 WCHARs, every field after it shifts by 256
    // bytes, and the result is not an error - it is a plausible-looking list of
    // garbage SSIDs and nonsense signal values.

    [StructLayout(LayoutKind.Sequential)]
    private struct DOT11_SSID
    {
        public uint uSSIDLength;                       // valid bytes in ucSSID, 0..32
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 32)] public byte[]? ucSSID;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WLAN_INTERFACE_INFO
    {
        public Guid InterfaceGuid;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string? strInterfaceDescription;
        public int isState;
    }

    /// <summary>
    /// Laid out exactly as WLAN_AVAILABLE_NETWORK (628 bytes). The BOOL fields
    /// are declared as <c>int</c> rather than marshalled bools purely so the
    /// size arithmetic stays readable - a wrong size here walks the array off
    /// its stride and every entry past the first is junk.
    /// </summary>
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WLAN_AVAILABLE_NETWORK
    {
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string? strProfileName;
        public DOT11_SSID dot11Ssid;
        public uint dot11BssType;
        public uint uNumberOfBssids;
        public int bNetworkConnectable;
        public uint wlanNotConnectableReason;
        public uint uNumberOfPhyTypes;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 8)] public uint[]? dot11PhyTypes;
        public int bMorePhyTypes;
        public uint wlanSignalQuality;                 // ALREADY 0..100, not dBm
        public int bSecurityEnabled;
        public uint dot11DefaultAuthAlgorithm;
        public uint dot11DefaultCipherAlgorithm;
        public uint dwFlags;
        public uint dwReserved;
    }

    /// <summary>
    /// The head of WLAN_CONNECTION_ATTRIBUTES. The nested association block is
    /// flattened to its FIRST member: the SSID is all we want, and a struct's
    /// first member sits at the struct's own offset, so this is layout-identical
    /// to declaring the whole tree - with far less to get wrong.
    /// </summary>
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WLAN_CONNECTION_ATTRIBUTES
    {
        public int isState;
        public int wlanConnectionMode;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string? strProfileName;
        public DOT11_SSID dot11Ssid;                   // wlanAssociationAttributes.dot11Ssid
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct WLAN_PHY_RADIO_STATE
    {
        public uint dwPhyIndex;
        public int dot11SoftwareRadioState;
        public int dot11HardwareRadioState;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WLAN_CONNECTION_PARAMETERS
    {
        public int wlanConnectionMode;
        [MarshalAs(UnmanagedType.LPWStr)] public string? strProfile;
        public IntPtr pDot11Ssid;                      // NULL when connecting by profile
        public IntPtr pDesiredBssidList;               // NULL = let the driver pick the BSS
        public int dot11BssType;
        public uint dwFlags;
    }

    // ---- imports ---------------------------------------------------------

    [DllImport("wlanapi.dll")]
    private static extern int WlanOpenHandle(uint clientVersion, IntPtr reserved,
                                             out uint negotiatedVersion, out IntPtr clientHandle);
    [DllImport("wlanapi.dll")]
    private static extern int WlanCloseHandle(IntPtr clientHandle, IntPtr reserved);
    [DllImport("wlanapi.dll")]
    private static extern void WlanFreeMemory(IntPtr memory);
    [DllImport("wlanapi.dll")]
    private static extern int WlanEnumInterfaces(IntPtr clientHandle, IntPtr reserved, out IntPtr list);
    [DllImport("wlanapi.dll")]
    private static extern int WlanGetAvailableNetworkList(IntPtr clientHandle, ref Guid interfaceGuid,
                                                          uint flags, IntPtr reserved, out IntPtr list);
    [DllImport("wlanapi.dll")]
    private static extern int WlanScan(IntPtr clientHandle, ref Guid interfaceGuid,
                                       IntPtr dot11Ssid, IntPtr ieData, IntPtr reserved);
    [DllImport("wlanapi.dll")]
    private static extern int WlanQueryInterface(IntPtr clientHandle, ref Guid interfaceGuid, int opCode,
                                                 IntPtr reserved, out uint dataSize, out IntPtr data,
                                                 IntPtr valueType);
    [DllImport("wlanapi.dll")]
    private static extern int WlanSetInterface(IntPtr clientHandle, ref Guid interfaceGuid, int opCode,
                                               uint dataSize, IntPtr data, IntPtr reserved);
    [DllImport("wlanapi.dll")]
    private static extern int WlanConnect(IntPtr clientHandle, ref Guid interfaceGuid,
                                          ref WLAN_CONNECTION_PARAMETERS parameters, IntPtr reserved);
    [DllImport("wlanapi.dll")]
    private static extern int WlanDisconnect(IntPtr clientHandle, ref Guid interfaceGuid, IntPtr reserved);
    [DllImport("wlanapi.dll", CharSet = CharSet.Unicode)]
    private static extern int WlanSetProfile(IntPtr clientHandle, ref Guid interfaceGuid, uint flags,
                                             [MarshalAs(UnmanagedType.LPWStr)] string profileXml,
                                             [MarshalAs(UnmanagedType.LPWStr)] string? allUserSecurity,
                                             [MarshalAs(UnmanagedType.Bool)] bool overwrite,
                                             IntPtr reserved, out uint reasonCode);

    // ---- handle + interface plumbing -------------------------------------

    /// <summary>
    /// Opens a client handle, runs <paramref name="body"/>, and closes it on
    /// every path.
    ///
    /// 🔴 EVERY BUFFER wlanapi HANDS BACK IS THE CALLER'S TO RELEASE with
    /// WlanFreeMemory - the interface list, the network list, every query
    /// result. This panel refreshes on a timer, so a missed free is not a
    /// one-off leak, it is a leak per tick for as long as the shell is open.
    /// That is why every buffer below lives inside its own try/finally.
    /// </summary>
    private static T WithHandle<T>(Func<IntPtr, T> body, T fallback)
    {
        IntPtr h = IntPtr.Zero;
        try
        {
            if (WlanOpenHandle(ClientVersion, IntPtr.Zero, out _, out h) != 0 || h == IntPtr.Zero)
                return fallback;
            return body(h);
        }
        // A machine with no wireless stack need not ship a usable wlanapi.dll at
        // all, so the P/Invoke itself can throw. That is the answer ("no Wi-Fi
        // here"), not an error worth propagating.
        catch { return fallback; }
        finally
        {
            if (h != IntPtr.Zero) { try { WlanCloseHandle(h, IntPtr.Zero); } catch { } }
        }
    }

    /// <summary>
    /// As <see cref="WithHandle{T}"/>, but also resolves the interface to work
    /// on: the first one that is not <c>wlan_interface_state_not_ready</c>.
    /// Nothing is cached - a USB dongle can appear or vanish between two
    /// refreshes, and a stale GUID would address an adapter that is gone.
    ///
    /// 🔴 <paramref name="anyState"/> EXISTS BECAUSE A RADIO THAT IS OFF REPORTS
    /// not_ready. Scanning and connecting genuinely need a ready adapter, so they
    /// leave it false. The RADIO calls must not: with the radio switched off the
    /// one adapter on the machine is not_ready, so a picker that skips not_ready
    /// finds nothing, and the toggle that turned Wi-Fi off can never turn it back
    /// on - it reports a hardware kill switch instead, which is the exact wrong
    /// answer <see cref="RadioOn"/> is written to avoid. A ready interface is
    /// still preferred when one exists, so every call keeps addressing the same
    /// adapter on a machine that has two.
    /// </summary>
    private static T WithInterface<T>(Func<IntPtr, Guid, T> body, T fallback, bool anyState = false)
        => WithHandle(h =>
        {
            IntPtr list = IntPtr.Zero;
            try
            {
                if (WlanEnumInterfaces(h, IntPtr.Zero, out list) != 0 || list == IntPtr.Zero)
                    return fallback;

                int count = Marshal.ReadInt32(list, 0);
                int stride = Marshal.SizeOf<WLAN_INTERFACE_INFO>();
                Guid? firstAny = null;

                for (int i = 0; i < count; i++)
                {
                    var info = Marshal.PtrToStructure<WLAN_INTERFACE_INFO>(
                        IntPtr.Add(list, ListHeaderBytes + i * stride));
                    firstAny ??= info.InterfaceGuid;
                    if (info.isState == InterfaceNotReady) continue;
                    return body(h, info.InterfaceGuid);
                }

                if (anyState && firstAny is Guid only) return body(h, only);
                return fallback;
            }
            finally { if (list != IntPtr.Zero) WlanFreeMemory(list); }
        }, fallback);

    // ---- queries ---------------------------------------------------------

    /// <summary>
    /// True when a WLAN adapter exists at all - the gate for showing the whole
    /// Wi-Fi section. A desktop on an ethernet cable with no wireless card must
    /// answer false so the UI omits the block, rather than render an empty list
    /// that reads as a scan that failed.
    ///
    /// Deliberately counts interfaces in ANY state, unlike the picker above: an
    /// adapter that is present but not ready should still show its section (with
    /// the radio reported off), not disappear.
    /// </summary>
    public static bool Available() => WithHandle(h =>
    {
        IntPtr list = IntPtr.Zero;
        try
        {
            if (WlanEnumInterfaces(h, IntPtr.Zero, out list) != 0 || list == IntPtr.Zero) return false;
            return Marshal.ReadInt32(list, 0) > 0;
        }
        finally { if (list != IntPtr.Zero) WlanFreeMemory(list); }
    }, false);

    /// <summary>
    /// True when the radio is usable. The software state must be explicitly ON;
    /// the hardware state only has to not be explicitly OFF.
    ///
    /// 🔴 The asymmetry is deliberate. Some drivers report the hardware state as
    /// <c>unknown</c> when the machine has no RF kill switch to report on, and
    /// demanding a literal "on" from both would then print "Wi-Fi is off" over a
    /// working, connected adapter - the worst kind of wrong, because the user
    /// then toggles a switch that was never the problem. Only an explicit
    /// hardware OFF (a real kill switch) vetoes.
    ///
    /// Reads the adapter in ANY state: an adapter whose radio is off reports
    /// not_ready, and answering from a fallback instead of from the radio would
    /// also mean a freshly re-enabled radio still read as off for the seconds the
    /// interface takes to leave not_ready - i.e. a successful toggle that looks
    /// like a failed one.
    /// </summary>
    public static bool RadioOn() => WithInterface((h, guid) =>
    {
        IntPtr data = IntPtr.Zero;
        try
        {
            if (WlanQueryInterface(h, ref guid, OpcodeRadioState, IntPtr.Zero,
                                   out _, out data, IntPtr.Zero) != 0 || data == IntPtr.Zero)
                return false;

            // WLAN_RADIO_STATE = { DWORD dwNumberOfPhys; WLAN_PHY_RADIO_STATE[64] },
            // so phy 0 begins 4 bytes in.
            if (Marshal.ReadInt32(data, 0) < 1) return false;
            var phy = Marshal.PtrToStructure<WLAN_PHY_RADIO_STATE>(IntPtr.Add(data, 4));
            return phy.dot11SoftwareRadioState == RadioStateOn
                && phy.dot11HardwareRadioState != RadioStateOff;
        }
        finally { if (data != IntPtr.Zero) WlanFreeMemory(data); }
    }, false, anyState: true);

    /// <summary>
    /// Switches the SOFTWARE radio. Returns false when the stack refuses.
    ///
    /// 🔴 THE HARDWARE RADIO CANNOT BE CHANGED FROM SOFTWARE. A laptop whose
    /// physical RF switch is off keeps reporting off no matter what is written
    /// here, and this shell runs asInvoker, so on a standard account the write
    /// itself can be denied outright. Both cases return an honest false rather
    /// than reporting success and leaving a toggle that silently springs back -
    /// the caller should re-read <see cref="RadioOn"/> and show what the adapter
    /// actually says.
    ///
    /// 🔴 WRITES TO THE ADAPTER IN ANY STATE, and that is what makes the toggle
    /// two-way. Switching the radio off puts the interface into not_ready, so a
    /// picker that skips not_ready would find no adapter to switch back ON: the
    /// call would fail without ever reaching the driver, the shell would blame a
    /// hardware kill switch, and the user would be left offline inside a console
    /// whose only remaining control is the toggle that just refused.
    /// </summary>
    public static bool SetRadio(bool on) => WithInterface((h, guid) =>
    {
        var state = new WLAN_PHY_RADIO_STATE
        {
            dwPhyIndex = 0,
            dot11SoftwareRadioState = on ? RadioStateOn : RadioStateOff,
            // Ignored on a set - the API takes the whole struct, but only the
            // software field is writable.
            dot11HardwareRadioState = RadioStateUnknown
        };

        int size = Marshal.SizeOf<WLAN_PHY_RADIO_STATE>();
        IntPtr buf = Marshal.AllocHGlobal(size);
        try
        {
            Marshal.StructureToPtr(state, buf, false);
            return WlanSetInterface(h, ref guid, OpcodeRadioState, (uint)size, buf, IntPtr.Zero) == 0;
        }
        finally { Marshal.FreeHGlobal(buf); }
    }, false, anyState: true);

    /// <summary>The SSID currently associated, or null when not connected.</summary>
    public static string? ConnectedSsid()
        => WithInterface((h, guid) => ConnectedSsidCore(h, ref guid), null);

    private static string? ConnectedSsidCore(IntPtr h, ref Guid guid)
    {
        IntPtr data = IntPtr.Zero;
        try
        {
            // Returns a failure code (not an empty struct) when the interface is
            // not associated, so the status check covers "not connected" too.
            if (WlanQueryInterface(h, ref guid, OpcodeCurrentConnection, IntPtr.Zero,
                                   out _, out data, IntPtr.Zero) != 0 || data == IntPtr.Zero)
                return null;

            var a = Marshal.PtrToStructure<WLAN_CONNECTION_ATTRIBUTES>(data);
            if (a.isState != InterfaceConnected) return null;
            string ssid = SsidOf(a.dot11Ssid);
            return ssid.Length == 0 ? null : ssid;
        }
        catch { return null; }
        finally { if (data != IntPtr.Zero) WlanFreeMemory(data); }
    }

    /// <summary>
    /// Asks the driver to re-scan. Returns as soon as the request is queued -
    /// the scan itself takes roughly four seconds and the results only show up
    /// in a LATER <see cref="Networks"/> call, so the caller must re-poll rather
    /// than read straight after this returns.
    ///
    /// The call into the WLAN service can still block briefly: run it off the UI
    /// thread.
    /// </summary>
    public static bool Scan() => WithInterface(
        (h, guid) => WlanScan(h, ref guid, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero) == 0, false);

    /// <summary>
    /// The visible networks, strongest first, with the connected one pinned to
    /// the top. Reads the driver's cached scan results - call <see cref="Scan"/>
    /// first for fresh ones.
    ///
    /// Enumerates through the WLAN service, so run it off the UI thread.
    /// </summary>
    public static List<WifiNetwork> Networks() => WithInterface((h, guid) =>
    {
        IntPtr list = IntPtr.Zero;
        try
        {
            if (WlanGetAvailableNetworkList(h, ref guid, IncludeAllProfiles,
                                            IntPtr.Zero, out list) != 0 || list == IntPtr.Zero)
                return new List<WifiNetwork>();

            string? current = ConnectedSsidCore(h, ref guid);
            int count = Marshal.ReadInt32(list, 0);
            int stride = Marshal.SizeOf<WLAN_AVAILABLE_NETWORK>();

            // 🔴 THE LIST ARRIVES ONE ENTRY PER BSSID. A mesh or a dual-band
            // router publishes the same SSID three or five times, and a picker
            // showing one name five times reads as a broken picker. Keep the
            // strongest sighting per SSID - that is the radio the driver would
            // associate with anyway.
            var best = new Dictionary<string, WifiNetwork>(StringComparer.Ordinal);

            for (int i = 0; i < count; i++)
            {
                var n = Marshal.PtrToStructure<WLAN_AVAILABLE_NETWORK>(
                    IntPtr.Add(list, ListHeaderBytes + i * stride));

                string ssid = SsidOf(n.dot11Ssid);
                // A blank SSID is a hidden network's beacon. It cannot be joined
                // from a list - there is nothing to show and nothing to tap - so
                // listing it only produces an unusable row.
                if (ssid.Length == 0) continue;

                var row = new WifiNetwork(
                    ssid,
                    (int)Math.Min(n.wlanSignalQuality, 100u),
                    SecurityLabel(n.dot11DefaultAuthAlgorithm, n.dot11DefaultCipherAlgorithm,
                                  n.bSecurityEnabled != 0),
                    string.Equals(ssid, current, StringComparison.Ordinal),
                    !string.IsNullOrEmpty(n.strProfileName));

                if (best.TryGetValue(ssid, out var prev))
                {
                    // The same SSID can arrive twice with only ONE copy carrying
                    // the profile name (once as the saved profile, once as a bare
                    // sighting). Dropping that flag on the weaker copy would hide
                    // that the network is saved and prompt for a password we hold.
                    bool hasProfile = prev.HasProfile || row.HasProfile;
                    if (row.SignalPercent > prev.SignalPercent)
                        best[ssid] = row with { HasProfile = hasProfile };
                    else if (hasProfile != prev.HasProfile)
                        best[ssid] = prev with { HasProfile = hasProfile };
                }
                else best[ssid] = row;
            }

            return best.Values
                       .OrderByDescending(n => n.Connected)
                       .ThenByDescending(n => n.SignalPercent)
                       .ThenBy(n => n.Ssid, StringComparer.CurrentCultureIgnoreCase)
                       .ToList();
        }
        finally { if (list != IntPtr.Zero) WlanFreeMemory(list); }
    }, new List<WifiNetwork>());

    // ---- actions ---------------------------------------------------------

    /// <summary>
    /// Joins a network, creating a profile from <paramref name="password"/> when
    /// one does not already exist. A null or empty password builds an OPEN
    /// profile.
    ///
    /// 🔴 A true return means the request was ACCEPTED, not that the network is
    /// joined - WlanConnect is asynchronous. The caller polls
    /// <see cref="ConnectedSsid"/> to find out whether it actually worked, and a
    /// wrong password surfaces there as "never connected" rather than as a
    /// failure here.
    ///
    /// Writes a profile through the WLAN service and can block for a moment: run
    /// it off the UI thread.
    /// </summary>
    public static bool Connect(string ssid, string? password)
    {
        if (string.IsNullOrEmpty(ssid)) return false;

        return WithInterface((h, guid) =>
        {
            // Reuse the network's OWN profile name when it has one: Windows names
            // profiles after the SSID by default, but an imported or
            // policy-pushed profile need not, and connecting by the wrong name
            // fails with nothing to show for it.
            var (existingProfile, auth) = LookupProfile(h, ref guid, ssid);
            string profileName = string.IsNullOrEmpty(existingProfile) ? ssid : existingProfile;

            if (string.IsNullOrEmpty(existingProfile))
            {
                string xml = ProfileXml(ssid, password, auth);
                if (WlanSetProfile(h, ref guid, 0 /* all-user profile */, xml, null,
                                   true /* overwrite */, IntPtr.Zero, out _) != 0)
                    return false;
            }

            var p = new WLAN_CONNECTION_PARAMETERS
            {
                wlanConnectionMode = ConnectionModeProfile,
                strProfile = profileName,
                pDot11Ssid = IntPtr.Zero,
                pDesiredBssidList = IntPtr.Zero,
                dot11BssType = BssTypeInfrastructure,
                dwFlags = 0
            };
            return WlanConnect(h, ref guid, ref p, IntPtr.Zero) == 0;
        }, false);
    }

    /// <summary>Drops the current association. Asynchronous, like Connect.</summary>
    public static bool Disconnect() => WithInterface(
        (h, guid) => WlanDisconnect(h, ref guid, IntPtr.Zero) == 0, false);

    /// <summary>
    /// True when a wired link is up. It lives beside the Wi-Fi calls because it
    /// is the answer to "why does this Wi-Fi list look irrelevant" - a machine
    /// on ethernet already has working internet, and the panel should say so
    /// instead of pushing the user to join a network they do not need.
    /// </summary>
    public static bool EthernetConnected()
    {
        try { return NetworkInterface.GetAllNetworkInterfaces().Any(IsLiveWiredLink); }
        catch { return false; }
    }

    /// <summary>
    /// 🔴 "UP AND OF TYPE ETHERNET" IS NOT A CABLE. Hyper-V switches, VMware and
    /// VirtualBox host-only adapters, Bluetooth PAN and TAP drivers all report
    /// <c>Ethernet</c> + <c>Up</c> forever, whether or not anything is plugged
    /// in - this very machine carries a VirtualBox host-only adapter that is
    /// permanently up. Counting one makes the panel announce "wired - connected"
    /// on a handheld with no cable AND suppress the "no network" warning, which
    /// is the one line that explains why nothing is downloading.
    ///
    /// A DEFAULT GATEWAY is what separates them: a real wired LAN always has one
    /// and a host-only or point-to-point virtual link has none. That is also the
    /// question actually being asked here - not "is a NIC awake" but "does this
    /// machine already have internet". Windows lists an all-zero gateway on some
    /// idle adapters, so those are not counted either.
    ///
    /// Guarded per adapter: <c>GetIPProperties</c> throws on some virtual
    /// devices, and letting that escape would fail the whole enumeration and
    /// report no ethernet at all on a machine that has one.
    /// </summary>
    private static bool IsLiveWiredLink(NetworkInterface n)
    {
        try
        {
            if (n.OperationalStatus != OperationalStatus.Up) return false;

            // Loopback and tunnels are excluded by construction: neither is one
            // of the three wired types.
            if (n.NetworkInterfaceType is not (NetworkInterfaceType.Ethernet
                                            or NetworkInterfaceType.GigabitEthernet
                                            or NetworkInterfaceType.FastEthernetT))
                return false;

            foreach (var gw in n.GetIPProperties().GatewayAddresses)
            {
                IPAddress? a = gw.Address;
                if (a is null || a.Equals(IPAddress.Any) || a.Equals(IPAddress.IPv6Any)) continue;
                return true;
            }
            return false;
        }
        catch { return false; }
    }

    // ---- helpers ---------------------------------------------------------

    /// <summary>
    /// The existing profile name (null when there is none) and the auth
    /// algorithm the AP advertises, in one pass over the network list.
    /// </summary>
    private static (string? Profile, uint Auth) LookupProfile(IntPtr h, ref Guid guid, string ssid)
    {
        IntPtr list = IntPtr.Zero;
        try
        {
            if (WlanGetAvailableNetworkList(h, ref guid, IncludeAllProfiles,
                                            IntPtr.Zero, out list) != 0 || list == IntPtr.Zero)
                return (null, 0);

            int count = Marshal.ReadInt32(list, 0);
            int stride = Marshal.SizeOf<WLAN_AVAILABLE_NETWORK>();
            uint auth = 0;

            for (int i = 0; i < count; i++)
            {
                var n = Marshal.PtrToStructure<WLAN_AVAILABLE_NETWORK>(
                    IntPtr.Add(list, ListHeaderBytes + i * stride));
                if (!string.Equals(SsidOf(n.dot11Ssid), ssid, StringComparison.Ordinal)) continue;

                if (auth == 0) auth = n.dot11DefaultAuthAlgorithm;
                // Keep scanning past a bare sighting: the entry carrying the
                // profile name can come later in the list than one that does not.
                if (!string.IsNullOrEmpty(n.strProfileName))
                    return (n.strProfileName, n.dot11DefaultAuthAlgorithm);
            }
            return (null, auth);
        }
        catch { return (null, 0); }
        finally { if (list != IntPtr.Zero) WlanFreeMemory(list); }
    }

    /// <summary>
    /// A minimal WLAN profile. Both the SSID and the password are XML-escaped:
    /// an ampersand in a Wi-Fi password is not exotic, and unescaped it produces
    /// invalid XML that WlanSetProfile rejects with a reason code no user could
    /// act on.
    /// </summary>
    private static string ProfileXml(string ssid, string? password, uint auth)
    {
        string name = SecurityElement.Escape(ssid) ?? ssid;

        string security;
        if (string.IsNullOrEmpty(password))
        {
            security = "<authEncryption><authentication>open</authentication>"
                     + "<encryption>none</encryption><useOneX>false</useOneX></authEncryption>";
        }
        else
        {
            // WPA2PSK/AES also joins a WPA2/WPA3 transition-mode AP, so it is the
            // right default. A WPA3-ONLY AP rejects it, so honour what the scan
            // advertised - otherwise the list would label a network "WPA3-SAE"
            // and then hand it a profile that can never connect.
            string algo = auth == AuthWpa3Sae ? "WPA3SAE" : "WPA2PSK";
            string pw = SecurityElement.Escape(password) ?? password;
            security = "<authEncryption><authentication>" + algo + "</authentication>"
                     + "<encryption>AES</encryption><useOneX>false</useOneX></authEncryption>"
                     + "<sharedKey><keyType>passPhrase</keyType><protected>false</protected>"
                     + "<keyMaterial>" + pw + "</keyMaterial></sharedKey>";
        }

        return "<?xml version=\"1.0\"?>"
             + "<WLANProfile xmlns=\"http://www.microsoft.com/networking/WLAN/profile/v1\">"
             + "<name>" + name + "</name>"
             + "<SSIDConfig><SSID><name>" + name + "</name></SSID></SSIDConfig>"
             + "<connectionType>ESS</connectionType>"
             + "<connectionMode>auto</connectionMode>"
             + "<MSM><security>" + security + "</security></MSM>"
             + "</WLANProfile>";
    }

    /// <summary>
    /// 802.11 SSIDs are raw octets with an explicit length, NOT a terminated
    /// string - the buffer past uSSIDLength is undefined, so reading all 32
    /// bytes appends garbage to the name.
    /// </summary>
    private static string SsidOf(DOT11_SSID s)
    {
        if (s.ucSSID is null) return "";
        int len = (int)Math.Min(s.uSSIDLength, 32u);
        if (len <= 0) return "";
        return Encoding.UTF8.GetString(s.ucSSID, 0, len).TrimEnd('\0');
    }

    private static string SecurityLabel(uint auth, uint cipher, bool secured) => auth switch
    {
        // Open + a cipher is legacy WEP, which authenticates as "open" and then
        // encrypts anyway; calling that "Open" would tell the user no password is
        // needed when one is.
        AuthOpen => cipher == CipherNone ? "Open" : "WEP",
        AuthSharedKey => "WEP",
        AuthWpa => "WPA-Enterprise",
        AuthWpaPsk or AuthWpaNone => "WPA-PSK",
        AuthRsna => "WPA2-Enterprise",
        AuthRsnaPsk => "WPA2-PSK",
        AuthWpa3Ent192 or AuthWpa3Ent => "WPA3-Enterprise",
        AuthWpa3Sae => "WPA3-SAE",
        AuthOwe => "Enhanced Open",
        // An IHV-specific algorithm we have no name for. Say "Secured" rather
        // than guess - the only thing the UI needs from this is whether to ask
        // for a key.
        _ => secured ? "Secured" : "Open"
    };
}
