using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;

namespace BigLaunch.Services;

/// <summary>
/// A local mirror for remote box art.
///
/// 🔴 WHY THIS EXISTS: the shell's image loader is deliberately file-only
/// (BitmapImage + CacheOption.OnLoad, so a Steam cache file is never locked).
/// The Hebrew hub's catalog, however, hands out ABSOLUTE https cover URLs — so
/// every non-Steam title silently fell through the File.Exists gate and drew
/// the fallback plate. The library looked half-empty and the cause was
/// invisible, because "no art" and "art we refuse to fetch" render identically.
///
/// So: remote URLs are mirrored to disk ONCE, then they are ordinary files and
/// the existing loader works unchanged. No image ever downloads on the UI
/// thread, and a failure is remembered so a dead URL is not retried on every
/// single render pass.
///
/// Deliberately NOT a general HTTP image loader: it only writes into its own
/// folder, never overwrites, and treats any non-image response as a miss.
/// </summary>
public static class ArtCache
{
    private static readonly string Dir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "BigLaunch", "art");

    /// <summary>Where the mirrored art actually lives - the ONE answer, so a
    /// maintenance screen can measure and clear the folder that is really
    /// growing rather than one that shares its name.</summary>
    public static string Folder => Dir;

    /// <summary>Forget which URLs were already tried, so a clear is followed by
    /// real re-fetches instead of an hour of "we decided this one was dead".</summary>
    public static void ForgetAttempts() => Tried.Clear();

    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(20) };

    /// <summary>URLs already fetched (or proven dead) this session — one attempt each.</summary>
    private static readonly ConcurrentDictionary<string, byte> Tried = new();

    /// <summary>Raised once a URL has landed on disk, so the view can refresh that one tile.</summary>
    public static event Action<string>? Arrived;

    static ArtCache()
    {
        try { Directory.CreateDirectory(Dir); } catch { }
    }

    private static string PathFor(string url)
    {
        // Content-addressed: the same cover shared by two titles is stored once,
        // and a changed URL naturally becomes a new file instead of a stale hit.
        byte[] h = SHA256.HashData(Encoding.UTF8.GetBytes(url));
        return Path.Combine(Dir, Convert.ToHexString(h, 0, 10) + Path.GetExtension(new Uri(url).AbsolutePath is { Length: > 0 } p && p.Contains('.') ? p : ".img"));
    }

    /// <summary>
    /// Resolve a catalog art reference to a LOCAL path.
    /// Returns null for a remote URL that is not mirrored yet, and starts the
    /// fetch in the background — the caller draws its fallback and gets an
    /// <see cref="Arrived"/> callback when the real art is ready.
    /// </summary>
    public static string? Resolve(string? reference)
    {
        if (string.IsNullOrWhiteSpace(reference)) return null;

        // A plain path is already local — the overwhelmingly common case
        // (everything Steam caches), so it costs nothing.
        if (!reference.StartsWith("http", StringComparison.OrdinalIgnoreCase))
            return File.Exists(reference) ? reference : null;

        string local;
        try { local = PathFor(reference); }
        catch { return null; }

        if (File.Exists(local)) return local;
        if (!Tried.TryAdd(reference, 0)) return null;   // in flight, or already failed

        _ = FetchAsync(reference, local);
        return null;
    }

    private static async Task FetchAsync(string url, string local)
    {
        try
        {
            using var res = await Http.GetAsync(url).ConfigureAwait(false);
            if (!res.IsSuccessStatusCode) return;

            string? type = res.Content.Headers.ContentType?.MediaType;
            if (type is not null && !type.StartsWith("image/", StringComparison.OrdinalIgnoreCase)) return;

            byte[] bytes = await res.Content.ReadAsByteArrayAsync().ConfigureAwait(false);
            if (bytes.Length < 256) return;   // an error page, not a cover

            // Write via a temp file + move: a half-written cover would be
            // cached forever as a corrupt image, and File.Exists cannot tell.
            string tmp = local + ".tmp";
            await File.WriteAllBytesAsync(tmp, bytes).ConfigureAwait(false);
            try { File.Move(tmp, local, overwrite: true); }
            catch { try { File.Delete(tmp); } catch { } return; }

            Arrived?.Invoke(url);
        }
        catch
        {
            // Stays in Tried, so a dead URL is attempted once per session and
            // never turns a render pass into a network stall.
        }
    }
}
