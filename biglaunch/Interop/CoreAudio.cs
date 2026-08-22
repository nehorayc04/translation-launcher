using System;
using System.Runtime.InteropServices;

namespace BigLaunch.Interop;

/// <summary>
/// The Core Audio COM surface that MORE THAN ONE file needs — declared ONCE.
///
/// 🔴🔴 A CLSID/IID MAY BE DECLARED ONLY ONE TIME IN AN ASSEMBLY. Volume.cs and
/// AudioMixer.cs each used to carry their own private copy of
/// MMDeviceEnumerator and IMMDeviceEnumerator, on the stated reasoning that a
/// vtable is easier to audit beside the code that calls it. That reasoning is
/// sound and the result was still broken: two [ComImport] types with the same
/// GUID are two DIFFERENT managed types claiming one COM identity, the runtime
/// binds the identity to whichever it sees first, and the loser's activation
/// dies with the unreadable
///
///     InvalidCastException: Unable to cast object of type 'MMDeviceEnumerator'
///     to type 'MMDeviceEnumerator'.
///
/// It failed silently for exactly as long as the failure had nowhere to be seen:
/// every call site swallowed it and returned an empty list, so the audio panel
/// simply rendered without its output-device and per-app sections — a missing
/// feature, not an error. What found it was giving the failure a place to
/// appear (AudioMixer.LastError, shown in the panel), not more reading.
///
/// The vtable discipline is unchanged and still applies to every interface
/// here: declare EVERY method that precedes the ones actually called, in exact
/// IDL order, with [PreserveSig] on all of them. A missing slot dispatches to
/// the wrong function pointer, and a missing [PreserveSig] makes every `hr != 0`
/// check read a zero-initialised hidden retval instead of the real HRESULT.
/// </summary>
internal static class CoreAudio
{
    internal const int ERender = 0;              // EDataFlow::eRender
    internal const int RoleConsole = 0, RoleMultimedia = 1, RoleCommunications = 2;
    internal const int DeviceStateActive = 1;    // DEVICE_STATE_ACTIVE
    internal const int StgmRead = 0;             // STGM_READ
    internal const int ClsCtxAll = 23;
    internal const ushort VtLpwstr = 31;

    /// <summary>A PROPVARIANT owns whatever it points at, so a friendly-name
    /// read without this leaks a string per device per refresh.</summary>
    [DllImport("ole32.dll")]
    internal static extern int PropVariantClear(ref PROPVARIANT pv);
}

[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
internal class MMDeviceEnumerator { }

[ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
internal interface IMMDeviceEnumerator
{
    [PreserveSig] int EnumAudioEndpoints(int dataFlow, int stateMask, out IMMDeviceCollection devices);
    [PreserveSig] int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice device);
    // unused, but the slots have to exist
    [PreserveSig] int GetDevice([MarshalAs(UnmanagedType.LPWStr)] string id, out IMMDevice device);
    [PreserveSig] int RegisterEndpointNotificationCallback(IntPtr client);
    [PreserveSig] int UnregisterEndpointNotificationCallback(IntPtr client);
}

[ComImport, Guid("0BD7A1BE-7A1A-44DB-8397-CC5392387B5E"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
internal interface IMMDeviceCollection
{
    [PreserveSig] int GetCount(out uint count);
    [PreserveSig] int Item(uint index, out IMMDevice device);
}

[ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
internal interface IMMDevice
{
    [PreserveSig] int Activate(ref Guid iid, int clsCtx, IntPtr activationParams,
                               [MarshalAs(UnmanagedType.IUnknown)] out object iface);
    [PreserveSig] int OpenPropertyStore(int access, out IPropertyStore store);
    [PreserveSig] int GetId([MarshalAs(UnmanagedType.LPWStr)] out string id);
    [PreserveSig] int GetState(out int state);
}

[ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
internal interface IPropertyStore
{
    [PreserveSig] int GetCount(out uint count);
    [PreserveSig] int GetAt(uint index, out PROPERTYKEY key);
    [PreserveSig] int GetValue(ref PROPERTYKEY key, out PROPVARIANT value);
    [PreserveSig] int SetValue(ref PROPERTYKEY key, ref PROPVARIANT value);
    [PreserveSig] int Commit();
}

[StructLayout(LayoutKind.Sequential)]
internal struct PROPERTYKEY
{
    public Guid fmtid;
    public uint pid;
}

// Sequential rather than Explicit on purpose: the four ushorts pack to exactly
// the 8-byte header, and natural IntPtr alignment then puts the union at offset
// 8 on x86 AND x64 - the same place the real union starts. Two pointer-sized
// fields cover the widest member we could ever be handed (a counted array is
// pointer + count), so the struct's total size matches what the callee writes
// and nothing is smeared past it.
[StructLayout(LayoutKind.Sequential)]
internal struct PROPVARIANT
{
    public ushort vt;
    public ushort r1, r2, r3;
    public IntPtr p;    // VT_LPWSTR lives here
    public IntPtr p2;
}
