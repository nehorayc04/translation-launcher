using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace BigLaunch.Services;

/// <summary>
/// Installs and removes Hebrew translations from inside the console.
///
/// 🔴 IT DOES NOT IMPLEMENT ANY OF IT. The desktop launcher owns every applier -
/// the per-game backups, the journals, the "the game was patched, so this backup
/// is stale" checks and the purchase gate - and a second copy of that in C#
/// would drift from the Python one the first time a game shipped an update. So
/// this runs the launcher HEADLESSLY ("--mod install --game X"), reads the JSON
/// lines it prints, and renders them. One implementation, two front ends.
///
/// The worker exits when it is done, so it never collides with a running
/// launcher window: it short-circuits before the single-instance guard.
/// </summary>
public static class ModBridge
{
    public readonly record struct Tick(string Phase, double Pct, string Message);

    /// <summary>
    /// True when the installed launcher is new enough to be driven this way.
    /// An older build has no --mod switch and would open its WINDOW instead of
    /// doing the work - so the console must know BEFORE it offers a button.
    ///
    /// 🔴 NEVER PROBE ON THE UI THREAD. Answering this means starting the
    /// launcher headlessly, which loads its whole backend and takes seconds; a
    /// blocking check here would freeze the shell every time a blade opened.
    /// So the answer is computed once in the background (ProbeAsync, at
    /// startup) and remembered ON DISK against the launcher's own identity, so
    /// it is paid at most once per launcher build rather than once per session.
    /// </summary>
    public static bool Available() => _available == true;

    private static bool? _available;

    private static string StampFile =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                     "BigLaunch", "modbridge.txt");

    /// <summary>Identity of the launcher build we last probed: path + size + write time.</summary>
    private static string? Identity()
    {
        try
        {
            string? exe = Catalog.LauncherExe();
            if (exe is null || !File.Exists(exe)) return null;
            var fi = new FileInfo(exe);
            return $"{exe}|{fi.Length}|{fi.LastWriteTimeUtc.Ticks}";
        }
        catch { return null; }
    }

    public static async Task ProbeAsync()
    {
        string? id = Identity();
        if (id is null) { _available = false; return; }

        try
        {
            if (File.Exists(StampFile))
            {
                var parts = (await File.ReadAllTextAsync(StampFile).ConfigureAwait(false)).Split('\n');
                if (parts.Length >= 2 && parts[0].Trim() == id)
                {
                    _available = parts[1].Trim() == "1";
                    return;
                }
            }
        }
        catch { }

        bool ok;
        try
        {
            // A read-only question, so a wrong answer costs nothing: "state" on
            // a game id that always exists in the catalog.
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(90));
            var r = await RunAsync("state", "gtav", null, cts.Token).ConfigureAwait(false);
            ok = r.Ok || r.Raw.Contains("\"state\"", StringComparison.Ordinal);
        }
        catch { ok = false; }

        _available = ok;
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(StampFile)!);
            await File.WriteAllTextAsync(StampFile, id + "\n" + (ok ? "1" : "0")).ConfigureAwait(false);
        }
        catch { }
    }

    /// <summary>The outcome. <paramref name="Stalled"/> separates "the worker
    /// said no" from "the worker stopped saying anything", because the two need
    /// different words in front of a user who cannot see a console.</summary>
    public readonly record struct Result(bool Ok, string Message, string Raw, bool Stalled = false, bool Canceled = false);

    /// <summary>
    /// How long the worker may go SILENT before we call it hung.
    ///
    /// Not a total budget: a 4 GB translation on a slow disk legitimately takes
    /// many minutes, and a deadline measured from the start would kill the one
    /// install that needed the time. What is never legitimate is emitting
    /// nothing at all - the worker reports a phase line on every step - so the
    /// watchdog measures the gap between lines instead.
    /// </summary>
    private static readonly TimeSpan Stall = TimeSpan.FromMinutes(4);

    /// <summary>
    /// Run one headless operation. `progress` is raised on the CALLING thread's
    /// synchronization context by the caller - this method only reports lines.
    /// </summary>
    public static Task<Result> RunAsync(string op, string gameId, Action<Tick>? progress,
                                        CancellationToken ct)
        => RunAsync(op, gameId, null, progress, ct);

    /// <summary>The last non-empty line - a traceback ends with the sentence that
    /// names the error, and the frames above it mean nothing to this user.</summary>
    private static string LastLine(string s)
    {
        using var rd = new StringReader(s);
        string last = "";
        while (rd.ReadLine() is { } line)
            if (line.Trim().Length > 0) last = line.Trim();
        return last.Length > 160 ? last[..160] + "…" : last;
    }

    public static async Task<Result> RunAsync(string op, string gameId, string? value,
                                              Action<Tick>? progress, CancellationToken ct)
    {
        string? exe = Catalog.LauncherExe();
        if (exe is null) return new Result(false, "לא נמצא הלאנצ׳ר של שולחן העבודה", "");

        var psi = new ProcessStartInfo(exe)
        {
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            WorkingDirectory = Path.GetDirectoryName(exe)!,
            // UTF-8: every message on this channel is Hebrew, and the console
            // code page would turn it into question marks.
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        psi.ArgumentList.Add("--mod");
        psi.ArgumentList.Add(op);
        psi.ArgumentList.Add("--game");
        psi.ArgumentList.Add(gameId);
        if (!string.IsNullOrEmpty(value))
        {
            psi.ArgumentList.Add("--value");
            psi.ArgumentList.Add(value);
        }

        var sb = new StringBuilder();
        var err = new StringBuilder();
        bool ok = false;
        string message = "";
        bool stalled = false;

        try
        {
            using var p = new Process { StartInfo = psi, EnableRaisingEvents = true };
            if (!p.Start()) return new Result(false, "הפעלת הלאנצ׳ר נכשלה", "");

            // 🔴🔴 A REDIRECTED PIPE NOBODY READS IS A DEADLOCK, NOT A DISCARD.
            // stderr was redirected and then never touched: the child blocks the
            // moment it writes past the pipe buffer (~4 KB), which is exactly
            // what a Python traceback does - so the ONE case that most needed a
            // message on screen was the one case that froze the console with a
            // progress bar stuck mid-way and no button that did anything. It is
            // drained on its own task, and the tail is KEPT so the failure can
            // be described instead of just announced.
            var drain = Task.Run(async () =>
            {
                try
                {
                    while (await p.StandardError.ReadLineAsync().ConfigureAwait(false) is { } e)
                        lock (err) { if (err.Length < 8192) err.AppendLine(e); }
                }
                catch { }
            });

            // The kill is the same for a user cancel and for a stall; only the
            // words afterwards differ, so one source drives both.
            using var stop = CancellationTokenSource.CreateLinkedTokenSource(ct);
            using var reg = stop.Token.Register(() => { try { p.Kill(true); } catch { } });

            // Rearmed by every line the worker prints. A worker that is working
            // is a worker that is talking.
            using var watchdog = new Timer(_ =>
            {
                stalled = true;
                try { stop.Cancel(); } catch { }
            }, null, Stall, Timeout.InfiniteTimeSpan);

            while (!p.StandardOutput.EndOfStream)
            {
                string? line = await p.StandardOutput.ReadLineAsync().ConfigureAwait(false);
                if (line is null) break;
                try { watchdog.Change(Stall, Timeout.InfiniteTimeSpan); } catch { }
                line = line.Trim();
                if (line.Length == 0 || line[0] != '{') continue;   // ignore ordinary log noise
                sb.AppendLine(line);
                try
                {
                    using var doc = JsonDocument.Parse(line);
                    var root = doc.RootElement;
                    if (root.TryGetProperty("phase", out var ph))
                    {
                        progress?.Invoke(new Tick(
                            ph.GetString() ?? "",
                            root.TryGetProperty("pct", out var pc) && pc.TryGetDouble(out double d) ? d : 0,
                            root.TryGetProperty("message", out var m) ? m.GetString() ?? "" : ""));
                    }
                    if (root.TryGetProperty("ok", out var okEl))
                    {
                        ok = okEl.ValueKind == JsonValueKind.True;
                        if (root.TryGetProperty("message", out var mm))
                            message = mm.GetString() ?? "";
                    }
                }
                catch { /* a malformed line is not a reason to abandon the install */ }
            }

            await p.WaitForExitAsync(CancellationToken.None).ConfigureAwait(false);
            await drain.ConfigureAwait(false);

            // 🔴 AN EXIT WITHOUT A VERDICT IS A FAILURE WITH A REASON, NOT A
            // BLANK ONE. A worker that crashed never prints its {"ok": …} line,
            // and the old code turned that into a bare "הפעולה נכשלה" with the
            // diagnosis sitting unread in a pipe. Now the exit code and the last
            // line of stderr come back with it.
            if (!ok && message.Length == 0)
            {
                string tail;
                lock (err) tail = err.ToString();
                tail = LastLine(tail);
                message = stalled  ? "ההתקנה נתקעה ולא הגיבה - היא בוטלה"
                        : ct.IsCancellationRequested ? "הפעולה בוטלה"
                        : tail.Length > 0 ? tail
                        : $"הפעולה נכשלה (קוד {p.ExitCode})";
            }
        }
        catch (Exception ex)
        {
            return new Result(false, ex.Message, sb.ToString());
        }

        return new Result(ok, message, sb.ToString(), stalled, ct.IsCancellationRequested);
    }
}
