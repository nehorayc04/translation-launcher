using System;
using System.Linq;
using System.Net.NetworkInformation;
using System.Runtime.InteropServices;

namespace BigLaunch.Interop;

public enum NetLink { Offline, WiFi, Wired }

/// <summary>
/// The two facts the header pill still owed the reference: is there a network,
/// and is Bluetooth on. Both are read live and both are cheap.
///
/// 🔴 A CHIP IS ONLY WORTH ITS WIDTH IF IT CAN SURPRISE YOU. That is this row's
/// standing rule, and it decides the shape of everything here: the network chip
/// is loudest when there is NO network — which is the state that explains a
/// failed download, a dead store page or a translation that will not fetch —
/// and Bluetooth appears only when a radio is actually switched on, because
/// "Bluetooth is off" on a desktop is not news. An always-lit pair of icons
/// would look like the reference and mean nothing.
/// </summary>
public static class SystemStatus
{
    // 🔴 THE HEADER PILL REBUILDS EVERY TICK, so an uncached probe here would run
    // an interface enumeration and a Bluetooth radio scan once a second, forever,
    // to answer a question that changes maybe twice a day. Both answers are held
    // for a few seconds — long enough to cost nothing, short enough that pulling
    // the ethernet cable still shows up while the user is still looking at it.
    private static readonly System.Diagnostics.Stopwatch _clock = System.Diagnostics.Stopwatch.StartNew();
    private const int NetTtlMs = 4_000, BtTtlMs = 10_000;
    private static long _netAt = -1, _btAt = -1;
    private static NetLink _netCache;
    private static bool _btCache;

    public static NetLink Network()
    {
        long now = _clock.ElapsedMilliseconds;
        if (_netAt >= 0 && now - _netAt < NetTtlMs) return _netCache;
        _netAt = now;
        return _netCache = NetworkUncached();
    }

    public static bool BluetoothOn()
    {
        long now = _clock.ElapsedMilliseconds;
        if (_btAt >= 0 && now - _btAt < BtTtlMs) return _btCache;
        _btAt = now;
        return _btCache = BluetoothUncached();
    }

    /// <summary>Wired beats wireless: if both are up, the traffic takes ethernet.</summary>
    private static NetLink NetworkUncached()
    {
        try
        {
            if (!NetworkInterface.GetIsNetworkAvailable()) return NetLink.Offline;

            var up = NetworkInterface.GetAllNetworkInterfaces()
                .Where(n => n.OperationalStatus == OperationalStatus.Up
                            // Loopback and tunnels are always "up" and carry no
                            // internet — counting them reports a link that is not
                            // there, which is worse than reporting none.
                            && n.NetworkInterfaceType != NetworkInterfaceType.Loopback
                            && n.NetworkInterfaceType != NetworkInterfaceType.Tunnel)
                .ToList();

            if (up.Any(n => n.NetworkInterfaceType is NetworkInterfaceType.Ethernet
                                                   or NetworkInterfaceType.GigabitEthernet
                                                   or NetworkInterfaceType.FastEthernetT))
                return NetLink.Wired;
            if (up.Any(n => n.NetworkInterfaceType == NetworkInterfaceType.Wireless80211))
                return NetLink.WiFi;
            return up.Count > 0 ? NetLink.Wired : NetLink.Offline;
        }
        catch { return NetLink.Wired; }   // never claim an outage we are not sure of
    }

    // ---- Bluetooth ------------------------------------------------------
    //
    // BluetoothFindFirstRadio hands back a HANDLE, so it has to be closed and
    // the find handle released — a status chip that leaks a handle per refresh
    // would be a slow leak in the one component that repaints forever.

    [StructLayout(LayoutKind.Sequential)]
    private struct BLUETOOTH_FIND_RADIO_PARAMS { public uint dwSize; }

    [DllImport("bthprops.cpl", SetLastError = true)]
    private static extern IntPtr BluetoothFindFirstRadio(ref BLUETOOTH_FIND_RADIO_PARAMS p, out IntPtr radio);
    [DllImport("bthprops.cpl", SetLastError = true)]
    private static extern bool BluetoothFindRadioClose(IntPtr find);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr h);

    /// <summary>True when a Bluetooth radio exists AND is switched on.</summary>
    private static bool BluetoothUncached()
    {
        IntPtr find = IntPtr.Zero, radio = IntPtr.Zero;
        try
        {
            var p = new BLUETOOTH_FIND_RADIO_PARAMS { dwSize = (uint)Marshal.SizeOf<BLUETOOTH_FIND_RADIO_PARAMS>() };
            find = BluetoothFindFirstRadio(ref p, out radio);
            return find != IntPtr.Zero;
        }
        // A machine with no Bluetooth stack does not ship bthprops.cpl at all,
        // so the P/Invoke itself throws. That is the answer, not an error.
        catch { return false; }
        finally
        {
            if (radio != IntPtr.Zero) CloseHandle(radio);
            if (find != IntPtr.Zero) BluetoothFindRadioClose(find);
        }
    }
}
