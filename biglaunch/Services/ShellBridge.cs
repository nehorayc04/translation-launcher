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
/// The four things the console can only learn from the desktop launcher:
/// who is signed in, what they bought, which plugins are installed, whether a
/// newer launcher exists, and the beta opt-in.
///
/// 🔴 IT DOES NOT RE-IMPLEMENT ANY OF THEM, and the account one it MUST NOT.
/// The signed-in token lives in session.enc, encrypted with a key held in the
/// Windows credential store and reachable only through the launcher's own auth
/// stack. A C# copy would mean a second implementation of the crypto AND a
/// second place a token can leak. The rest is the same argument one notch
/// weaker: the beta opt-in has a per-mod override that outranks the global
/// switch, and the plugin registry has a host that must be told to re-read its
/// state - editing their JSON from another process works right up until one of
/// those rules changes.
///
/// So this is ModBridge's sibling: run the launcher headlessly, read the JSON
/// line it prints, render it. One implementation, two front ends.
/// </summary>
public static class ShellBridge
{
    /// <summary>
    /// True when the installed launcher understands --shell.
    ///
    /// 🔴 THIS NEEDS ITS OWN PROBE - ModBridge's answer is NOT transferable.
    /// A launcher can have --mod and not --shell (every build before this
    /// feature), and on that build an unknown switch does not error: main_qt
    /// falls through and OPENS THE DESKTOP WINDOW. That would break the one
    /// rule the console is built around - that the only way back is the single
    /// button in Settings - so the console has to know BEFORE it offers a card.
    ///
    /// Probed lazily (the first time Settings is opened, not at startup) and
    /// remembered on disk against the launcher's identity, so an old build
    /// costs one killed process ever, not one per session.
    /// </summary>
    public static bool Available() => _available == true;

    private static bool? _available;
    private static Task? _probe;
    private static readonly object _gate = new();

    private static string StampFile =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                     "BigLaunch", "shellbridge.txt");

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

    /// <summary>Probe once per launcher build; safe to call repeatedly.</summary>
    public static Task EnsureProbedAsync()
    {
        lock (_gate)
        {
            if (_available is not null) return Task.CompletedTask;
            return _probe ??= ProbeAsync();
        }
    }

    /// <summary>
    /// Forget the cached answer so the next call probes again.
    ///
    /// 🔴 WITHOUT THIS, "check again" CANNOT SEE A LAUNCHER THAT WAS JUST
    /// UPDATED. The whole reason the console tells you an update exists is that
    /// you will go and install it - and the very next thing you do is come back
    /// and press refresh. A probe cached for the life of the process answers
    /// from before the update and reports the new launcher as too old, which is
    /// the exact moment this feature is supposed to start working. The on-disk
    /// stamp is keyed to the exe's identity, so re-probing after a real update
    /// costs one run and after a no-op costs nothing.
    /// </summary>
    public static void Reset()
    {
        lock (_gate) { _available = null; _probe = null; }
    }

    private static async Task ProbeAsync()
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
            // "beta" is the right probe: read-only, no network, answers in the
            // time it takes to start the launcher (measured: ~1.2s). An old
            // build prints nothing on stdout, so the timeout IS the negative
            // answer - hence a budget far larger than the real cost.
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(60));
            var r = await RunAsync("beta", null, null, null, cts.Token).ConfigureAwait(false);
            ok = r.Ok;
        }
        catch { ok = false; }

        _available = ok;

        // 🔴 ONLY A "YES" IS WRITTEN DOWN. A capability probe can fail for
        // reasons that have nothing to do with the capability - an antivirus
        // scanning a freshly-installed exe on its first run is the obvious one,
        // and it happens exactly once, at exactly the moment this is first
        // asked. Persisting that "no" would disable the feature for as long as
        // the launcher file stayed unchanged, which is forever. A "no" is
        // simply re-asked next session; the cost is one short-lived process.
        if (!ok) return;
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(StampFile)!);
            await File.WriteAllTextAsync(StampFile, id + "\n1").ConfigureAwait(false);
        }
        catch { }
    }

    public readonly record struct Result(bool Ok, string Message, string Raw);

    /// <summary>
    /// One headless call. `verb` is account|plugins|beta|update; the rest are
    /// the optional selectors the Python side takes.
    /// </summary>
    public static async Task<Result> RunAsync(string verb, string? game, string? id, string? set,
                                              CancellationToken ct)
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
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        psi.ArgumentList.Add("--shell");
        psi.ArgumentList.Add(verb);
        if (!string.IsNullOrEmpty(game)) { psi.ArgumentList.Add("--game"); psi.ArgumentList.Add(game); }
        if (!string.IsNullOrEmpty(id)) { psi.ArgumentList.Add("--id"); psi.ArgumentList.Add(id); }
        if (!string.IsNullOrEmpty(set)) { psi.ArgumentList.Add("--set"); psi.ArgumentList.Add(set); }

        var sb = new StringBuilder();
        bool ok = false;
        string message = "";

        try
        {
            using var p = new Process { StartInfo = psi, EnableRaisingEvents = true };
            if (!p.Start()) return new Result(false, "הפעלת הלאנצ׳ר נכשלה", "");

            // The kill on cancel is what makes the probe above safe on a build
            // that does not know --shell: it would sit there being a window.
            using var reg = ct.Register(() => { try { p.Kill(true); } catch { } });

            while (!p.StandardOutput.EndOfStream)
            {
                string? line = await p.StandardOutput.ReadLineAsync().ConfigureAwait(false);
                if (line is null) break;
                line = line.Trim();
                if (line.Length == 0 || line[0] != '{') continue;   // ordinary log noise
                sb.AppendLine(line);
                try
                {
                    using var doc = JsonDocument.Parse(line);
                    if (doc.RootElement.TryGetProperty("ok", out var okEl))
                    {
                        ok = okEl.ValueKind == JsonValueKind.True;
                        if (doc.RootElement.TryGetProperty("message", out var mm))
                            message = mm.GetString() ?? "";
                    }
                }
                catch { }
            }

            await p.WaitForExitAsync(CancellationToken.None).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            return new Result(false, ex.Message, sb.ToString());
        }

        return new Result(ok, message, sb.ToString());
    }

    // ---- typed reads -------------------------------------------------------

    public sealed class Account
    {
        public string Name = "";
        public string Email = "";
        public string Avatar = "";
        public bool SignedIn;
        /// <summary>Purchased titles, newest first: (game id, Hebrew title).</summary>
        public List<(string Id, string Title)> Purchases = new();
        /// <summary>Why purchases are empty, when the launcher could say.</summary>
        public string Reason = "";
    }

    /// <summary>Everything, in ONE launcher start. See the Python side's note.</summary>
    public sealed record Snapshot(Account? Account, PluginList? Plugins,
                                  BetaPrefs? Beta, UpdateInfo? Update);

    public static async Task<Snapshot?> AllAsync(CancellationToken ct)
    {
        var r = await RunAsync("all", null, null, null, ct).ConfigureAwait(false);
        if (!r.Ok) return null;
        try
        {
            using var doc = JsonDocument.Parse(LastLine(r.Raw));
            var root = doc.RootElement;
            return new Snapshot(
                Sub(root, "account", ParseAccount),
                Sub(root, "plugins", ParsePluginList),
                Sub(root, "beta", ParseBetaPrefs),
                Sub(root, "update", ParseUpdate));
        }
        catch { return null; }
    }

    /// <summary>
    /// Read one member and parse it, treating an absent, null or malformed
    /// member as "unknown" — the Python side sends null for a section that
    /// threw, and one failed section must not blank the other three.
    /// </summary>
    private static T? Sub<T>(JsonElement root, string name, Func<JsonElement, T?> parse) where T : class
    {
        try
        {
            return root.TryGetProperty(name, out var el) && el.ValueKind == JsonValueKind.Object
                ? parse(el) : null;
        }
        catch { return null; }
    }

    public static async Task<Account?> AccountAsync(CancellationToken ct)
    {
        var r = await RunAsync("account", null, null, null, ct).ConfigureAwait(false);
        if (!r.Ok) return null;
        try
        {
            using var doc = JsonDocument.Parse(LastLine(r.Raw));
            return ParseAccount(doc.RootElement);
        }
        catch { return null; }
    }

    private static Account ParseAccount(JsonElement root)
    {
        {
            var a = new Account();
            if (root.TryGetProperty("user", out var u) && u.ValueKind == JsonValueKind.Object)
            {
                a.SignedIn = true;
                a.Name = Str(u, "fullName");
                a.Email = Str(u, "email");
                a.Avatar = Str(u, "avatarUrl");
                if (a.Name.Length == 0) a.Name = a.Email;
            }
            // 🔴 "ok" IS A SUCCESS SENTINEL, NOT A REASON. The launcher reports
            // "ok" when the purchase lookup SUCCEEDED, so leaking it through as
            // a reason makes a user who genuinely owns nothing see "could not
            // load your purchases · ok" - the exact false alarm the empty-vs-
            // failed distinction exists to prevent, just inverted. A successful
            // read has nothing to explain.
            a.Reason = Str(root, "reason");
            if (a.Reason.Equals("ok", StringComparison.OrdinalIgnoreCase)) a.Reason = "";
            if (root.TryGetProperty("purchases", out var ps) && ps.ValueKind == JsonValueKind.Array)
            {
                foreach (var p in ps.EnumerateArray())
                {
                    // 🔴 ONLY A COMPLETED PURCHASE IS A PURCHASE. A row can also
                    // be pending or refunded, and listing either as something
                    // the user owns is the app making a claim about their money
                    // that the server would not back. A row with no status at
                    // all is kept - that is a shape question, not a refund.
                    string st = Str(p, "status");
                    if (st.Length > 0 && !st.Equals("completed", StringComparison.OrdinalIgnoreCase))
                        continue;

                    string gid = Str(p, "game_id");
                    string title = gid;
                    if (p.TryGetProperty("games", out var g) && g.ValueKind == JsonValueKind.Object)
                    {
                        string he = Str(g, "title_he"), en = Str(g, "title_en");
                        title = he.Length > 0 ? he : (en.Length > 0 ? en : gid);
                    }
                    if (gid.Length > 0) a.Purchases.Add((gid, title));
                }
            }
            return a;
        }
    }

    public sealed class PluginInfo
    {
        public string Id = "", Name = "", Tagline = "", Icon = "", Accent = "";
        public bool Installed, Enabled;
    }

    public sealed class PluginList
    {
        public bool SignedIn, Entitled;
        public List<PluginInfo> Items = new();
    }

    public static async Task<PluginList?> PluginsAsync(CancellationToken ct)
    {
        var r = await RunAsync("plugins", null, null, null, ct).ConfigureAwait(false);
        return ParsePlugins(r);
    }

    /// <summary>
    /// Flip a plugin. Returns the new state, or the launcher's OWN reason for
    /// refusing - "you need to own a translation to use plugins" is an answer
    /// the user can act on, and a generic "it failed" is not.
    /// </summary>
    public static async Task<(PluginList? List, string Message)> SetPluginAsync(
        string id, bool on, CancellationToken ct)
    {
        var r = await RunAsync("plugins", null, id, on ? "on" : "off", ct).ConfigureAwait(false);
        return (ParsePlugins(r), r.Message);
    }

    private static PluginList? ParsePlugins(Result r)
    {
        if (!r.Ok) return null;
        try
        {
            using var doc = JsonDocument.Parse(LastLine(r.Raw));
            return doc.RootElement.TryGetProperty("result", out var res)
                ? ParsePluginList(res) : null;
        }
        catch { return null; }
    }

    private static PluginList ParsePluginList(JsonElement res)
    {
        {
            var list = new PluginList
            {
                SignedIn = Bool(res, "signedIn"),
                Entitled = Bool(res, "entitled"),
            };
            if (res.TryGetProperty("plugins", out var arr) && arr.ValueKind == JsonValueKind.Array)
            {
                foreach (var p in arr.EnumerateArray())
                    list.Items.Add(new PluginInfo
                    {
                        Id = Str(p, "id"),
                        Name = Str(p, "name"),
                        Tagline = Str(p, "tagline"),
                        Icon = Str(p, "icon"),
                        Accent = Str(p, "accent"),
                        Installed = Bool(p, "installed"),
                        Enabled = Bool(p, "enabled"),
                    });
            }
            return list;
        }
    }

    public sealed class BetaPrefs
    {
        public bool Channel;
        /// <summary>Per-mod overrides that outrank the global switch.</summary>
        public Dictionary<string, bool> Overrides = new(StringComparer.OrdinalIgnoreCase);

        /// <summary>Effective answer for one game: the override if it has one.</summary>
        public bool For(string gameId) =>
            Overrides.TryGetValue(gameId, out bool v) ? v : Channel;

        public bool HasOverride(string gameId) => Overrides.ContainsKey(gameId);
    }

    public static async Task<BetaPrefs?> BetaAsync(CancellationToken ct)
        => ParseBeta(await RunAsync("beta", null, null, null, ct).ConfigureAwait(false));

    public static async Task<BetaPrefs?> SetBetaAsync(bool on, CancellationToken ct)
        => ParseBeta(await RunAsync("beta", null, null, on ? "on" : "off", ct).ConfigureAwait(false));

    /// <summary>null clears the override, so the game follows the global switch again.</summary>
    public static async Task<BetaPrefs?> SetBetaOverrideAsync(string gameId, bool? on, CancellationToken ct)
        => ParseBeta(await RunAsync("beta", gameId, null,
                                    on is null ? "auto" : (on.Value ? "on" : "off"), ct).ConfigureAwait(false));

    private static BetaPrefs? ParseBeta(Result r)
    {
        if (!r.Ok) return null;
        try
        {
            using var doc = JsonDocument.Parse(LastLine(r.Raw));
            return doc.RootElement.TryGetProperty("result", out var res)
                ? ParseBetaPrefs(res) : null;
        }
        catch { return null; }
    }

    private static BetaPrefs ParseBetaPrefs(JsonElement res)
    {
        var b = new BetaPrefs { Channel = Bool(res, "betaChannel") };
        if (res.TryGetProperty("betaOverrides", out var ov) && ov.ValueKind == JsonValueKind.Object)
            foreach (var kv in ov.EnumerateObject())
                if (kv.Value.ValueKind is JsonValueKind.True or JsonValueKind.False)
                    b.Overrides[kv.Name] = kv.Value.ValueKind == JsonValueKind.True;
        return b;
    }

    public sealed class UpdateInfo
    {
        public string Current = "", Latest = "", Notes = "";
        public bool Available;
        public double SizeMb;
    }

    public static async Task<UpdateInfo?> UpdateAsync(CancellationToken ct)
    {
        var r = await RunAsync("update", null, null, null, ct).ConfigureAwait(false);
        if (!r.Ok) return null;
        try
        {
            using var doc = JsonDocument.Parse(LastLine(r.Raw));
            return doc.RootElement.TryGetProperty("result", out var res)
                ? ParseUpdate(res) : null;
        }
        catch { return null; }
    }

    private static UpdateInfo ParseUpdate(JsonElement res) => new()
    {
        Current = Str(res, "currentVersion"),
        Latest = Str(res, "latestVersion"),
        Notes = Str(res, "notes"),
        Available = Bool(res, "updateAvailable"),
        SizeMb = res.TryGetProperty("sizeMb", out var s) && s.TryGetDouble(out double d) ? d : 0,
    };

    // ---- helpers -----------------------------------------------------------

    /// <summary>
    /// The protocol is one object per line and the ANSWER is the last one -
    /// anything before it is progress. Parsing the first line would read a
    /// progress tick as the result.
    /// </summary>
    private static string LastLine(string raw)
    {
        var lines = raw.Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        return lines.Length == 0 ? "{}" : lines[^1];
    }

    private static string Str(JsonElement e, string name)
        => e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? (v.GetString() ?? "") : "";

    private static bool Bool(JsonElement e, string name)
        => e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.True;
}
