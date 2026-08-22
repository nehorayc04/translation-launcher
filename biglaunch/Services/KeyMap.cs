using System.Collections.Generic;
using System.Text;

namespace BigLaunch.Services;

/// <summary>
/// 🔴🔴 THE KEYBOARD LAYOUT DECIDES WHAT A KEYPRESS TYPES, AND THIS USER'S IS
/// HEBREW. Every game in the library is named in Latin ("Far Cry 5"), so
/// physically pressing F-A-R puts "כשר" in the field and the search finds
/// nothing — while the user is convinced they typed the name correctly. On a
/// couch, with a controller in hand, "switch your Windows layout first" is not
/// an answer.
///
/// So we search the raw text AND its physical-key transliteration: the Hebrew
/// (Standard) layout puts כ on the F key, ש on A, ר on R, so "כשר" maps back to
/// "far" and Far Cry 5 appears. It works the other way too — an English layout
/// can still reach a Hebrew-named entry.
/// </summary>
public static class KeyMap
{
    // The Hebrew (Standard) letter rows, in physical QWERTY order. Anything not
    // listed (digits, space, punctuation) is already identical on both layouts.
    private const string Lat = "qwertyuiopasdfghjkl;zxcvbnm,.";
    private const string Heb = "/'קראטוןםפשדגכעיחלךףזסבהנמצתץ";

    private static readonly Dictionary<char, char> _toLat = Build(Heb, Lat);
    private static readonly Dictionary<char, char> _toHeb = Build(Lat, Heb);

    private static Dictionary<char, char> Build(string from, string to)
    {
        var d = new Dictionary<char, char>();
        for (int i = 0; i < from.Length && i < to.Length; i++) d[from[i]] = to[i];
        return d;
    }

    private static string Map(string s, Dictionary<char, char> table)
    {
        var sb = new StringBuilder(s.Length);
        bool hit = false;
        foreach (char c in s)
        {
            if (table.TryGetValue(char.ToLowerInvariant(c), out char m)) { sb.Append(m); hit = true; }
            else sb.Append(c);
        }
        return hit ? sb.ToString() : "";
    }

    /// <summary>Hebrew keystrokes re-read as the Latin letters on the same keys ("" when nothing mapped).</summary>
    public static string ToLatin(string s) => Map(s, _toLat);

    /// <summary>Latin keystrokes re-read as the Hebrew letters on the same keys ("" when nothing mapped).</summary>
    public static string ToHebrew(string s) => Map(s, _toHeb);
}
