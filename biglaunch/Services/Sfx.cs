using System;
using System.Collections.Generic;
using System.IO;
using System.Media;

namespace BigLaunch.Services;

public enum Sound { Navigate, Select, Back, DeadEnd, Launch, Startup, Sleep, Wake, Shutter, Warning }

/// <summary>
/// The shell's sound layer — the report's seven audio events, SYNTHESISED.
///
/// 🔴 Deliberate: Winhanced ships 7 .wav assets (Startup, wake_from_sleep,
/// device_sleep, Navigation_taps, Option_select, back_plus_deadend,
/// camerashutter). Those are its assets and copying them is exactly what the
/// project's legal map forbids. So each cue is GENERATED here from sine
/// partials + an envelope: same design decision (a soft, tonal, non-intrusive
/// console feedback set), our own bytes, zero files to ship, zero licensing.
///
/// Everything is pre-rendered once into memory at startup, so pressing a
/// direction never allocates or hits the disk on the input path.
/// </summary>
public static class Sfx
{
    private const int Rate = 44100;

    private static readonly Dictionary<Sound, SoundPlayer> Players = new();
    private static double _volume = 0.35;
    private static bool _enabled = true;
    private static bool _built;

    public static void Configure(bool enabled, double volume)
    {
        bool revolume = Math.Abs(volume - _volume) > 0.001;
        _enabled = enabled;
        _volume = Math.Clamp(volume, 0, 1);
        if (!_built || revolume) Build();
    }

    /// <summary>Fire and forget. Never throws, never blocks the UI thread.</summary>
    public static void Play(Sound s)
    {
        if (!_enabled) return;
        try { if (Players.TryGetValue(s, out var p)) p.Play(); }
        catch { /* an audio device that vanished is not a crash */ }
    }

    // ------------------------------------------------------------ synthesis

    private static void Build()
    {
        foreach (var p in Players.Values) { try { p.Dispose(); } catch { } }
        Players.Clear();

        // A console UI wants short, soft, tonal cues with no attack click —
        // hence a raised-cosine attack and an exponential tail on every voice.
        Add(Sound.Navigate, Render(0.055, (t, d) => Voice(t, d, 1180, 0.55, 0.004)));
        Add(Sound.Select,   Render(0.16,  (t, d) => Voice(t, d, 880, 0.65, 0.006)
                                                  + Voice(t, d, 1320, 0.35, 0.006, delay: 0.045)));
        Add(Sound.Back,     Render(0.14,  (t, d) => Glide(t, d, 760, 460, 0.6)));
        Add(Sound.DeadEnd,  Render(0.12,  (t, d) => Voice(t, d, 190, 0.7, 0.01)
                                                  + Voice(t, d, 143, 0.4, 0.01)));
        Add(Sound.Launch,   Render(0.55,  (t, d) => Glide(t, d, 320, 880, 0.55)
                                                  + Voice(t, d, 1760, 0.18, 0.02, delay: 0.28)));
        Add(Sound.Startup,  Render(0.95,  (t, d) => Voice(t, d, 392, 0.5, 0.05)
                                                  + Voice(t, d, 523, 0.45, 0.05, delay: 0.16)
                                                  + Voice(t, d, 659, 0.4,  0.05, delay: 0.32)
                                                  + Voice(t, d, 784, 0.5,  0.30, delay: 0.48)));
        Add(Sound.Sleep,    Render(0.75,  (t, d) => Glide(t, d, 620, 180, 0.5)));
        Add(Sound.Wake,     Render(0.75,  (t, d) => Glide(t, d, 220, 700, 0.5)));
        Add(Sound.Shutter,  Render(0.13,  (t, d) => Noise(t, d, 0.5, 0.004)
                                                  + Noise(t, d, 0.35, 0.004, delay: 0.055)));
        Add(Sound.Warning,  Render(0.42,  (t, d) => Voice(t, d, 660, 0.5, 0.02)
                                                  + Voice(t, d, 660, 0.5, 0.02, delay: 0.22)));
        _built = true;
    }

    private static void Add(Sound s, byte[] wav)
    {
        try
        {
            var p = new SoundPlayer(new MemoryStream(wav));
            p.Load();                       // decode now, not on the first press
            Players[s] = p;
        }
        catch { }
    }

    /// <summary>One decaying sine partial, optionally starting later in the cue.</summary>
    private static double Voice(double t, double dur, double freq, double amp,
                                double decay, double delay = 0)
    {
        double u = t - delay;
        if (u < 0) return 0;
        return Math.Sin(2 * Math.PI * freq * u) * amp * Env(u, dur - delay, decay);
    }

    /// <summary>A pitch sweep — "forward" rises, "back" falls.</summary>
    private static double Glide(double t, double dur, double f0, double f1, double amp)
    {
        double k = Math.Clamp(t / dur, 0, 1);
        double f = f0 + (f1 - f0) * k;
        return Math.Sin(2 * Math.PI * f * t) * amp * Env(t, dur, 0.02);
    }

    private static readonly Random Rng = new(1337);   // fixed: the shutter is identical every time

    private static double Noise(double t, double dur, double amp, double decay, double delay = 0)
    {
        double u = t - delay;
        if (u < 0) return 0;
        return (Rng.NextDouble() * 2 - 1) * amp * Env(u, dur - delay, decay) * 0.6;
    }

    /// <summary>Raised-cosine attack (no click) + exponential release.</summary>
    private static double Env(double t, double dur, double attack)
    {
        if (t < 0 || t > dur) return 0;
        double a = attack <= 0 ? 1 : Math.Min(1, t / attack);
        a = 0.5 - 0.5 * Math.Cos(Math.PI * a);
        double rel = Math.Exp(-3.2 * t / Math.Max(dur, 0.001));
        return a * rel;
    }

    /// <summary>Render a mono 16-bit PCM WAV entirely in memory.</summary>
    private static byte[] Render(double seconds, Func<double, double, double> voice)
    {
        int n = (int)(Rate * seconds);
        var ms = new MemoryStream(44 + n * 2);
        var w = new BinaryWriter(ms);

        void Ascii(string s) { foreach (char c in s) w.Write((byte)c); }
        Ascii("RIFF"); w.Write(36 + n * 2); Ascii("WAVE");
        Ascii("fmt "); w.Write(16); w.Write((short)1); w.Write((short)1);
        w.Write(Rate); w.Write(Rate * 2); w.Write((short)2); w.Write((short)16);
        Ascii("data"); w.Write(n * 2);

        for (int i = 0; i < n; i++)
        {
            double t = i / (double)Rate;
            double v = voice(t, seconds) * _volume;
            // A soft clip keeps a stacked chord from ever wrapping around.
            v = Math.Tanh(v * 1.15);
            w.Write((short)Math.Clamp(v * 26000, short.MinValue, short.MaxValue));
        }
        w.Flush();
        return ms.ToArray();
    }
}
