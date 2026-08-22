using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace RDR2_RPF_Tool.Core
{
    /// <summary>
    /// Hash -> real path resolver.
    ///
    /// RPF8 entries carry only a JOAAT hash of their path, and the in-archive name table
    /// of an ENCRYPTED archive is not recoverable with the TOC key (verified: no key tag
    /// in the whole key container turns it into ASCII) -- which is precisely why OpenIV
    /// ships its own external name database. Two sources fill the gap here:
    ///   * the name table of any archive whose TOC is NOT encrypted (tag 0xFF)
    ///   * the RPFC / pfm.dat mount cache inside appdata0_update.rpf, which lists real
    ///     archive paths in the clear (resolves the nested .rpf tree)
    /// A path is registered under every normalisation the packer might have hashed, since
    /// an entry whose extension has a format id is hashed WITHOUT that extension.
    /// </summary>
    public static class NameDb
    {
        public static readonly Dictionary<uint, string> Map = new Dictionary<uint, string>();

        public static void AddPath(string p)
        {
            if (string.IsNullOrWhiteSpace(p)) return;
            string c = p.Replace('\\', '/').Trim();
            if (c.Length < 2) return;

            AddOne(c);
            int colon = c.IndexOf(':');
            if (colon > 0 && colon < c.Length - 1)
            {
                string tail = c.Substring(colon + 1);
                AddOne(tail);
                AddOne(tail.TrimStart('/'));
            }
            // progressively drop leading path components (mount points vary per archive)
            string[] parts = c.Split('/');
            for (int i = 1; i < parts.Length; i++) AddOne(string.Join("/", parts, i, parts.Length - i));
        }

        static void AddOne(string c)
        {
            if (c.Length == 0) return;
            if (!Map.ContainsKey(JOAATHash.Calc(c))) Map[JOAATHash.Calc(c)] = c;
            int dot = c.LastIndexOf('.'), slash = c.LastIndexOf('/');
            if (dot > slash && dot > 0)
            {
                string noExt = c.Substring(0, dot);
                if (!Map.ContainsKey(JOAATHash.Calc(noExt))) Map[JOAATHash.Calc(noExt)] = c;
            }
        }

        /// <summary>Harvest printable path-looking strings out of any blob (RPFC, name table, ...).</summary>
        public static int AddFromBlob(byte[] blob)
        {
            if (blob == null || blob.Length == 0) return 0;
            int added = 0, start = -1;
            for (int i = 0; i <= blob.Length; i++)
            {
                byte b = i < blob.Length ? blob[i] : (byte)0;
                bool printable = b >= 0x20 && b < 0x7F;
                if (printable) { if (start < 0) start = i; }
                else
                {
                    if (start >= 0 && i - start >= 4)
                    {
                        string s = Encoding.ASCII.GetString(blob, start, i - start);
                        if (s.IndexOf('/') >= 0 || s.IndexOf('.') >= 0) { AddPath(s); added++; }
                    }
                    start = -1;
                }
            }
            return added;
        }

        public static int LoadTextFile(string path)
        {
            int n = 0;
            foreach (string line in File.ReadAllLines(path))
            {
                string s = line.Trim();
                if (s.Length == 0 || s[0] == '#') continue;
                AddPath(s); n++;
            }
            return n;
        }

        public static bool TryGet(uint hash, out string name) => Map.TryGetValue(hash, out name);
    }
}
