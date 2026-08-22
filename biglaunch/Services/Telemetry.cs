using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;

namespace BigLaunch.Services;

/// <summary>
/// Live machine telemetry — the thing Winhanced's whole product is built around
/// and the one capability a plain game launcher never has.
///
/// CPU and RAM use the SAME mechanism this project's own perf_manager.py uses
/// (GetSystemTimes deltas + GlobalMemoryStatusEx): pure P/Invoke, no NuGet, no
/// WMI, and cheap enough to poll on a UI timer. GPU is the one signal Windows
/// only exposes through performance counters, so it is strictly best-effort:
/// if the category is missing or throws even once, GPU is switched off for the
/// rest of the session rather than retried every tick.
/// </summary>
public sealed class Telemetry
{
    public double CpuPercent { get; private set; }
    public double RamPercent { get; private set; }
    public double GpuPercent { get; private set; }
    public double RamUsedGb  { get; private set; }
    public double RamTotalGb { get; private set; }
    public bool   GpuKnown   { get; private set; }

    // ---------------------------------------------------------------- CPU

    [StructLayout(LayoutKind.Sequential)]
    private struct FILETIME { public uint Low; public uint High; }

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetSystemTimes(out FILETIME idle, out FILETIME kernel, out FILETIME user);

    private static ulong U(FILETIME f) => ((ulong)f.High << 32) | f.Low;

    private ulong _idle, _kernel, _user;

    private void SampleCpu()
    {
        if (!GetSystemTimes(out var i, out var k, out var u)) return;
        ulong ni = U(i), nk = U(k), nu = U(u);

        if (_kernel != 0 || _user != 0)
        {
            // kernel time INCLUDES idle, so total = (kernel + user) and the busy
            // share is 1 - idle/total. A first sample has no delta to compare
            // against — which is why perf_manager primes itself at import; here
            // the first tick simply reports the previous value (0).
            double dIdle = ni - _idle, dKernel = nk - _kernel, dUser = nu - _user;
            double total = dKernel + dUser;
            if (total > 0)
                CpuPercent = Math.Clamp((1.0 - dIdle / total) * 100.0, 0, 100);
        }
        _idle = ni; _kernel = nk; _user = nu;
    }

    // ---------------------------------------------------------------- RAM

    [StructLayout(LayoutKind.Sequential)]
    private class MEMORYSTATUSEX
    {
        public uint  dwLength = (uint)Marshal.SizeOf(typeof(MEMORYSTATUSEX));
        public uint  dwMemoryLoad;
        public ulong ullTotalPhys, ullAvailPhys;
        public ulong ullTotalPageFile, ullAvailPageFile;
        public ulong ullTotalVirtual, ullAvailVirtual, ullAvailExtendedVirtual;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GlobalMemoryStatusEx([In, Out] MEMORYSTATUSEX m);

    private void SampleRam()
    {
        var m = new MEMORYSTATUSEX();
        if (!GlobalMemoryStatusEx(m) || m.ullTotalPhys == 0) return;
        const double GB = 1024d * 1024 * 1024;
        RamTotalGb = m.ullTotalPhys / GB;
        RamUsedGb  = (m.ullTotalPhys - m.ullAvailPhys) / GB;
        RamPercent = Math.Clamp(m.dwMemoryLoad, 0, 100);
    }

    // ---------------------------------------------------------------- GPU

    private PerformanceCounter[]? _gpu;
    private bool _gpuDead;
    private int  _gpuRescan;

    /// <summary>
    /// Consecutive failures before the GPU chip is given up on for the session.
    ///
    /// 🔴🔴 ONE FAILURE IS NOT ENOUGH — measured, not theorised. The old policy
    /// was "a machine without the counter will never grow one mid-session", and
    /// that reasoning is sound for a machine that genuinely lacks it. It is
    /// wrong for a TRANSIENT failure, and a transient failure is exactly what a
    /// fresh process meets: the perf-counter subsystem, the "GPU Engine"
    /// category enumeration and the first NextValue() on a brand-new rate
    /// counter are all racy in the first seconds of a run.
    ///
    /// The proof was two runs on THIS machine minutes apart: the shell started
    /// at 23:15 showed the GPU chip for its whole life, the one started at 23:35
    /// never showed it at all. A permanent per-machine absence cannot behave
    /// differently between two runs on the same box — so a blip was being
    /// promoted to a session-long missing feature.
    ///
    /// Five tries at roughly one per second is bounded and cheap, and it still
    /// honours the original concern: a machine that really has no counter stops
    /// probing within a few seconds and never burns CPU to report CPU.
    /// </summary>
    private const int GpuGiveUpAfter = 5;
    private int _gpuFails;

    /// <summary>The adapter id inside a "GPU Engine" instance name ("" if absent).</summary>
    private static string AdapterOf(string instance)
    {
        int i = instance.IndexOf("luid_", StringComparison.OrdinalIgnoreCase);
        if (i < 0) return "";
        int j = instance.IndexOf("_phys", i, StringComparison.OrdinalIgnoreCase);
        return j > i ? instance[i..j] : instance[i..];
    }

    /// <summary>
    /// Forget every performance counter and start again.
    ///
    /// A COUNTER DOES NOT SURVIVE A SLEEP. The "GPU Engine" instances are keyed
    /// by process and adapter; both are gone after a resume, and the handles we
    /// held throw from then on - five throws in a row and the shell decided the
    /// machine has no GPU counter AT ALL and stopped asking for the rest of the
    /// session. Waking up is the one moment we know the old handles are stale.
    /// </summary>
    public void ResetCounters()
    {
        _gpu = null;
        _gpuDead = false;
        _gpuFails = 0;
        _gpuRescan = 0;
    }

    private void SampleGpu()
    {
        if (_gpuDead) return;
        try
        {
            // The 3D engine instances come and go with every process that
            // touches the GPU, so the set is re-read periodically rather than
            // cached forever — but not every tick, which would be expensive.
            if (_gpu is null || --_gpuRescan <= 0)
            {
                _gpuRescan = 10;
                var cat = new PerformanceCounterCategory("GPU Engine");
                _gpu = cat.GetInstanceNames()
                          .Where(n => n.Contains("engtype_3D", StringComparison.OrdinalIgnoreCase))
                          .Select(n => new PerformanceCounter("GPU Engine", "Utilization Percentage", n, true))
                          .ToArray();
            }

            // ONE MACHINE, TWO GPUs, ONE NUMBER. The instance names are
            // "pid_x_luid_0x…_0x…_phys_0_eng_0_engtype_3D": the LUID identifies
            // the ADAPTER. Summing across all of them adds a laptop's idle iGPU
            // to its busy dGPU and reports the total as "the GPU", which is both
            // wrong and unstable - it changes the moment Windows moves a window
            // compositor between the two. Per adapter, then the busiest one,
            // which is the number the user means when they ask what the GPU is
            // doing while a game runs.
            var byAdapter = new Dictionary<string, double>();
            foreach (var c in _gpu)
            {
                string luid = AdapterOf(c.InstanceName);
                byAdapter.TryGetValue(luid, out double cur);
                byAdapter[luid] = cur + c.NextValue();
            }
            double best = 0;
            foreach (var v in byAdapter.Values) if (v > best) best = v;
            GpuPercent = Math.Clamp(best, 0, 100);
            GpuKnown = true;
            _gpuFails = 0;      // a good read clears the streak
        }
        catch
        {
            // Drop the handles so the next attempt re-enumerates from scratch —
            // a counter that failed once is not worth reusing.
            _gpu = null;
            GpuKnown = false;
            if (++_gpuFails >= GpuGiveUpAfter) _gpuDead = true;
        }
    }

    /// <summary>One poll. Never throws — a telemetry read must not be able to
    /// take down the shell it is decorating.</summary>
    public void Sample()
    {
        try { SampleCpu(); } catch { }
        try { SampleRam(); } catch { }
        try { SampleGpu(); } catch { }
    }

    // ---- battery ---------------------------------------------------------

    [StructLayout(LayoutKind.Sequential)]
    private struct SYSTEM_POWER_STATUS
    {
        public byte ACLineStatus;          // 0 offline, 1 online, 255 unknown
        public byte BatteryFlag;           // 128 = no system battery
        public byte BatteryLifePercent;    // 0..100, or 255 unknown
        public byte SystemStatusFlag;
        public int BatteryLifeTime;
        public int BatteryFullLifeTime;
    }

    [DllImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetSystemPowerStatus(out SYSTEM_POWER_STATUS s);

    /// <summary>
    /// Battery charge, or null on a desktop. A handheld shell that shows a
    /// fake "100%" on a machine with no battery is worse than showing nothing,
    /// so both "no battery" (flag 128) and "unknown" (255) return null.
    /// </summary>
    public static double? Battery()
    {
        try
        {
            if (!GetSystemPowerStatus(out var s)) return null;
            if (s.BatteryFlag == 128 || s.BatteryLifePercent > 100) return null;
            return s.BatteryLifePercent;
        }
        catch { return null; }
    }

    /// <summary>True when running on battery — the shell can then bias toward
    /// quieter polling, exactly as perf_manager.py does on the Python side.</summary>
    public static bool OnBattery()
    {
        try { return GetSystemPowerStatus(out var s) && s.ACLineStatus == 0; }
        catch { return false; }
    }
}
