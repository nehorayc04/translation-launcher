using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;

namespace BigLaunch.Services;

public sealed class StreamTarget
{
    public string Name = "";
    public string Detail = "";
    public string? Exe;          // a locally installed client
    public string? Uri;          // or a web endpoint
    // 🔴 "NOT INSTALLED" AND "RUNS IN A BROWSER" ARE DIFFERENT FACTS, and
    // after Find() returns null they look identical (Exe == null either way).
    // Xbox Cloud and GeForce NOW have no desktop client to miss - telling the
    // user they are "not installed" would be simply untrue.
    public bool WebOnly;
    public bool Installed => Exe is { Length: > 0 } && File.Exists(Exe);
    public bool Available => Installed || Uri is { Length: > 0 };
}

/// <summary>
/// Cloud gaming + PC streaming, as a LAUNCHER — never as an implementation.
///
/// The report lists xCloud / GeForce Now / PS Remote Play / Moonlight /
/// Sunshine / Chiaki. Every one of those is somebody else's client or service:
/// the honest, legal and genuinely useful thing a shell can do is find the
/// ones already on this machine and open them from the couch. We do not
/// re-implement streaming, and we ship no third-party binary.
/// </summary>
public static class Streaming
{
    private static string? Find(params string[] candidates)
    {
        foreach (string c in candidates)
        {
            try { if (File.Exists(c)) return c; } catch { }
        }
        return null;
    }

    private static string PF => Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
    private static string PF86 => Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
    private static string LAD => Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);

    public static List<StreamTarget> Targets()
    {
        var list = new List<StreamTarget>
        {
            new()
            {
                Name = "Moonlight",
                Detail = "סטרימינג מ-PC אחר (NVIDIA / Sunshine)",
                Exe = Find(Path.Combine(PF, "Moonlight Game Streaming", "Moonlight.exe"),
                           Path.Combine(PF86, "Moonlight Game Streaming", "Moonlight.exe")),
                Uri = "https://moonlight-stream.org/",
            },
            new()
            {
                Name = "Sunshine",
                Detail = "שרת סטרימינג במחשב הזה",
                Exe = Find(Path.Combine(PF, "Sunshine", "sunshine.exe")),
                // Sunshine's own console is a local web UI — the natural way in.
                Uri = "https://localhost:47990/",
            },
            new()
            {
                Name = "Chiaki",
                Detail = "PlayStation Remote Play (קוד פתוח)",
                Exe = Find(Path.Combine(PF, "Chiaki", "chiaki.exe")),
                Uri = "https://git.sr.ht/~thestr4ng3r/chiaki",
            },
            new()
            {
                Name = "PS Remote Play",
                Detail = "אפליקציית Remote Play הרשמית",
                Exe = Find(Path.Combine(PF, "Sony", "PS Remote Play", "RemotePlay.exe"),
                           Path.Combine(PF86, "Sony", "PS Remote Play", "RemotePlay.exe")),
                Uri = "https://remoteplay.dl.playstation.net/remoteplay/",
            },
            new()
            {
                Name = "Parsec",
                Detail = "סטרימינג בין מחשבים",
                Exe = Find(Path.Combine(LAD, "Parsec", "parsecd.exe")),
                Uri = "https://parsec.app/",
            },
            new()
            {
                Name = "Xbox Cloud Gaming",
                Detail = "משחק בענן דרך הדפדפן",
                WebOnly = true,
                Uri = "https://www.xbox.com/play",
            },
            new()
            {
                Name = "GeForce NOW",
                WebOnly = true,
                Detail = "משחק בענן של NVIDIA",
                Exe = Find(Path.Combine(PF, "NVIDIA Corporation", "GeForceNOW", "CEF", "GeForceNOW.exe")),
                Uri = "https://play.geforcenow.com/",
            },
        };
        return list.Where(t => t.Available).ToList();
    }

    public static bool Open(StreamTarget t)
    {
        try
        {
            string target = t.Installed ? t.Exe! : t.Uri!;
            Process.Start(new ProcessStartInfo(target)
            {
                UseShellExecute = true,
                WorkingDirectory = t.Installed ? Path.GetDirectoryName(t.Exe!) ?? "" : "",
            });
            return true;
        }
        catch { return false; }
    }
}
