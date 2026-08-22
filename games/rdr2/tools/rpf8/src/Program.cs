using System.Linq;
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using RDR2_RPF_Tool.Core;

namespace Rpf8Cli
{
    /// <summary>
    /// Standalone command-line extractor for Red Dead Redemption 2's RPF8 archives.
    /// No OpenIV, no GUI, no automation -- it decrypts (TFIT2 white-box CBC) and
    /// decompresses (Oodle / raw deflate) on its own.
    ///
    ///   rpf8 info    &lt;archive.rpf&gt;
    ///   rpf8 list    &lt;archive.rpf&gt;
    ///   rpf8 extract &lt;archive.rpf&gt; &lt;outdir&gt; [--recursive]
    ///   rpf8 unpack  &lt;folder&gt; [--inplace] [--dry-run]
    ///        walk a folder, and for every .rpf turn it into a same-named FOLDER of its
    ///        decrypted contents, recursing into nested archives. With --inplace the
    ///        original .rpf is deleted only AFTER its replacement folder is complete.
    /// </summary>
    static class Program
    {
        static int totalFiles = 0, totalArchives = 0, totalErrors = 0;
        static long totalBytes = 0;

        static int Main(string[] args)
        {
            Console.OutputEncoding = Encoding.UTF8;
            if (args.Length < 2) { Usage(); return 2; }

            string cmd = args[0].ToLowerInvariant();
            try
            {
                LoadNameDb(args);
                switch (cmd)
                {
                    case "info": return CmdInfo(args[1]);
                    case "list": return CmdList(args[1]);
                    case "names": return CmdNames(args[1]);
                    case "nametest": return CmdNameTest(args[1]);
                    case "extract":
                        {
                            if (args.Length < 3) { Usage(); return 2; }
                            bool rec = Array.IndexOf(args, "--recursive") >= 0;
                            ExtractArchiveFile(args[1], args[2], rec, 0);
                            Summary();
                            return totalErrors == 0 ? 0 : 1;
                        }
                    case "unpack":
                        {
                            bool inplace = Array.IndexOf(args, "--inplace") >= 0;
                            bool dry = Array.IndexOf(args, "--dry-run") >= 0;
                            return CmdUnpack(args[1], inplace, dry);
                        }
                    case "du": return CmdDu(args[1]);
                    case "probe": return CmdProbe(args[1], args.Length > 2 ? args[2] : null);
                    case "namedb": return CmdNameDb(args[1], args.Length > 2 ? args[2] : "names.txt");
                    default: Usage(); return 2;
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("FATAL: " + ex.Message);
                return 1;
            }
        }

        /// <summary>
        /// Load path names for hash resolution: an explicit --names file, else a names.txt
        /// sitting next to the executable. Purely optional -- without it entries are named
        /// by their hash, which still extracts correctly.
        /// </summary>
        static void LoadNameDb(string[] args)
        {
            int i = Array.IndexOf(args, "--names");
            string file = (i >= 0 && i + 1 < args.Length) ? args[i + 1] : null;
            if (file == null)
            {
                string side = Path.Combine(AppContext.BaseDirectory, "names.txt");
                if (File.Exists(side)) file = side;
            }
            if (file != null && File.Exists(file))
                Console.WriteLine($"[names] {NameDb.LoadTextFile(file)} path(s) from {file} -> {NameDb.Map.Count} hashes");
        }

        /// <summary>
        /// Build a names.txt from the game's own RPFC/pfm.dat mount cache (inside
        /// appdata0_update.rpf), which lists real archive paths in the clear.
        /// </summary>
        static int CmdNameDb(string gameFolderOrRpf, string outFile)
        {
            string rpf = Directory.Exists(gameFolderOrRpf)
                ? Path.Combine(gameFolderOrRpf, "appdata0_update.rpf")
                : gameFolderOrRpf;
            if (!File.Exists(rpf)) { Console.Error.WriteLine("not found: " + rpf); return 2; }

            var found = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
            using (var r = Rpf8Reader.Open(rpf))
            {
                foreach (var e in r.Entries)
                {
                    byte[] data;
                    try { data = r.GetFile(e); } catch { continue; }
                    int start = -1;
                    for (int i = 0; i <= data.Length; i++)
                    {
                        byte b = i < data.Length ? data[i] : (byte)0;
                        bool pr = b >= 0x20 && b < 0x7F;
                        if (pr) { if (start < 0) start = i; }
                        else
                        {
                            if (start >= 0 && i - start >= 6)
                            {
                                string s = Encoding.ASCII.GetString(data, start, i - start);
                                if (s.IndexOf('/') >= 0 && s.IndexOf('.') > 0) found.Add(s);
                            }
                            start = -1;
                        }
                    }
                }
            }
            File.WriteAllLines(outFile, found);
            Console.WriteLine($"wrote {found.Count} path(s) -> {outFile}");
            return 0;
        }

        // ------------------------------------------------------------------------ du
        //
        // How much disk would a FULL recursive unpack cost? Answer it from the TOCs alone,
        // writing nothing: a plain file contributes its original size, a nested archive is
        // read into memory and its own TOC walked. First-level sizes lie badly here --
        // nested archives are stored uncompressed, so a one-level sum reports ~1.0x while
        // the real cost is several times that.

        const long DU_MAX_NESTED = 1500L * 1024 * 1024;   // don't materialise a huge nested archive

        static long DuArchive(Rpf8Reader r, int depth, ref int files, ref int arcs)
        {
            arcs++;
            long total = 0;
            foreach (var e in r.Entries)
            {
                long osz = e.GetOrignalSize();
                string nm = r.GetEntryName(e);
                bool looksRpf = e.GetFileExtId() == 0 || nm.EndsWith(".rpf", StringComparison.OrdinalIgnoreCase);
                if (looksRpf && osz > 16 && osz <= DU_MAX_NESTED)
                {
                    try
                    {
                        byte[] data = r.GetFile(e);
                        if (data.Length >= 4 && BitConverter.ToUInt32(data, 0) == Rpf8Reader.RPF8_MAGIC)
                        {
                            using (var inner = Rpf8Reader.OpenBytes(data, r.SourceLabel + "/" + nm))
                                total += DuArchive(inner, depth + 1, ref files, ref arcs);
                            continue;
                        }
                    }
                    catch { /* unreadable -> fall through and count it at face value */ }
                }
                total += osz;
                files++;
            }
            return total;
        }

        static int CmdDu(string pathOrFolder)
        {
            var list = new List<string>();
            if (Directory.Exists(pathOrFolder))
            {
                foreach (var f in Directory.EnumerateFiles(pathOrFolder, "*.rpf", SearchOption.AllDirectories))
                {
                    try
                    {
                        using (var fs = new FileStream(f, FileMode.Open, FileAccess.Read, FileShare.Read))
                        {
                            byte[] m = new byte[4];
                            if (fs.Read(m, 0, 4) == 4 && BitConverter.ToUInt32(m, 0) == Rpf8Reader.RPF8_MAGIC)
                                list.Add(f);
                        }
                    }
                    catch { }
                }
            }
            else list.Add(pathOrFolder);

            const double GB = 1024.0 * 1024 * 1024;
            long grandArc = 0, grandExt = 0;
            int grandFiles = 0, grandArcs = 0;
            list.Sort((a, b) => new FileInfo(b).Length.CompareTo(new FileInfo(a).Length));
            foreach (var f in list)
            {
                long arch = new FileInfo(f).Length;
                int files = 0, arcs = 0;
                long ext;
                try
                {
                    using (var r = Rpf8Reader.Open(f)) ext = DuArchive(r, 0, ref files, ref arcs);
                }
                catch (Exception ex) { Console.Error.WriteLine($"  !! {Path.GetFileName(f)}: {ex.Message}"); continue; }
                grandArc += arch; grandExt += ext; grandFiles += files; grandArcs += arcs;
                Console.WriteLine($"  {Path.GetFileName(f),-42} {arch / GB,7:F2}GB -> {ext / GB,7:F2}GB  x{(double)ext / Math.Max(arch, 1),5:F2}" +
                                  $"  ({files:N0} files in {arcs:N0} archives)");
            }
            Console.WriteLine();
            Console.WriteLine($"archives      : {grandArc / GB,8:F2} GB   ({list.Count} top-level, {grandArcs:N0} incl. nested)");
            Console.WriteLine($"unpacked      : {grandExt / GB,8:F2} GB   ({grandFiles:N0} files)");
            Console.WriteLine($"ratio         : x{(double)grandExt / Math.Max(grandArc, 1):F2}");
            Console.WriteLine($"NET growth if unpacked --inplace: {(grandExt - grandArc) / GB:+0.00;-0.00} GB");
            return 0;
        }

        // ---------------------------------------------------------------------- probe
        //
        // Why did ONE entry fail? Dump its exact decrypt plan and try the competing
        // hypotheses on the real bytes -- guessing from the format spec is how the earlier
        // key scans were lost.
        static int CmdProbe(string archive, string hashHex)
        {
            using (var r = Rpf8Reader.Open(archive))
            {
                foreach (var e in r.Entries)
                {
                    string nm = r.GetEntryName(e);
                    if (hashHex != null &&
                        !nm.Contains(hashHex, StringComparison.OrdinalIgnoreCase) &&
                        !e.GetHash().ToString("X8").Equals(hashHex.TrimStart('0', 'x', 'X'), StringComparison.OrdinalIgnoreCase))
                        continue;

                    long rawSize = e.GetOnDiskSize(), offset = e.GetOffset();
                    if (e.IsSignatureProtected) { rawSize -= 256; offset += 256; }
                    if (e.IsResource) { offset += 16; rawSize -= 16; }
                    int usize = e.GetOrignalSize();
                    bool comp = e.GetCompressorId() > Compressorid.None;
                    long chunk = e.IsResource ? (comp ? 524288L : usize) : (comp ? 8192L : 4096L);
                    byte cfg = e.GetEncryptionConfig();
                    long hl = 0, bl = 0, bs = 0;
                    typeof(StridedCipher).GetMethod("UnpackConfig",
                        System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static)
                        ?.Invoke(null, new object[] { cfg, hl, bl, bs });
                    var ranges = StridedCipher.UnpackConfig(cfg, rawSize, chunk);

                    Console.WriteLine($"{nm}");
                    Console.WriteLine($"  usize={usize:N0} rawSize={rawSize:N0} comp={e.GetCompressorId()} key={e.GetEncryptionKeyId()} res={e.IsResource}");
                    Console.WriteLine($"  cfg=0x{cfg:X2}  head_cfg={cfg & 3} len_cfg={(cfg >> 2) & 7} stride_cfg={(cfg >> 5) & 7}" +
                                      $"  => head={(((cfg & 3) > 0) ? 1024L << ((cfg & 3) * 2) : 0)}" +
                                      $" block_len={((((cfg >> 2) & 7) != 0) ? 1024L << ((cfg >> 2) & 7) : 0)}" +
                                      $" stride={((((cfg >> 2) & 7) != 0) ? (long)((((cfg >> 5) & 7) + 1)) << 16 : 0)}  chunk={chunk:N0}");
                    Console.WriteLine($"  encrypted ranges ({ranges.Count}):");
                    long covered = 0;
                    foreach (var g in ranges) { Console.WriteLine($"    [{g[0]:N0} .. {g[1]:N0})"); covered += g[1] - g[0]; }
                    Console.WriteLine($"  covered {covered:N0} of {rawSize:N0} bytes ({100.0 * covered / rawSize:F1}%)");
                    Console.WriteLine($"  Val1=0x{e.Val1:X16} Val2=0x{e.Val2:X16} Val3=0x{e.Val3:X16}");
                    Console.WriteLine($"    virt(low32)={(uint)e.Val3:N0}  phys(high32)={(uint)(e.Val3 >> 32):N0}  resType={(int)e.GetResourceType()}");
                    byte[] h16 = ReadRange(archive, offset - 16, 16);
                    Console.Write("    16-byte resource header: ");
                    foreach (var bb in h16) Console.Write(bb.ToString("x2"));
                    Console.WriteLine();

                    byte[] raw = ReadRange(archive, offset, rawSize);

                    void TryIt(string label, Func<byte[], byte[]> prep)
                    {
                        try
                        {
                            byte[] b = prep((byte[])raw.Clone());
                            byte[] outp = Compression.DecompressFile(b, usize, e.GetCompressorId());
                            Console.WriteLine($"    {label,-34} OK  -> {outp.Length:N0} bytes");
                        }
                        catch (Exception ex) { Console.WriteLine($"    {label,-34} fail: {ex.Message}"); }
                    }

                    _ = (Func<byte[], byte[]>)(b => b); // (TryIt kept for other probes)
                    // How much raw output does this compressed stream actually yield? Sweep
                    // the requested size -- Oodle decodes a prefix when rawLen lands on a
                    // block boundary, so the largest value that succeeds IS the real size.
                    byte[] dec = Cipher.DecodeBlock((byte[])raw.Clone(), e);
                    // Does the 256-byte "signature" skip / the 16-byte resource skip actually
                    // belong to this entry? Try every combination on the real bytes.
                    Console.WriteLine("  header-skip variants (decrypt strided, then decompress):");
                    foreach (var v in new[] { ("as-is", 0L, 0L), ("no 256 skip", -256L, 256L),
                                              ("no 16 skip", -16L, 16L), ("no skips", -272L, 272L),
                                              ("256 at END", -256L, 0L) })
                    {
                        long o4 = offset + v.Item2, l4 = rawSize + v.Item3;
                        if (v.Item1 == "no 256 skip" && !e.IsSignatureProtected) continue;
                        if (v.Item1 == "no 16 skip" && !e.IsResource) continue;
                        if (o4 < 0 || l4 <= 0) continue;
                        try
                        {
                            byte[] b4 = Cipher.DecodeBlock(ReadRange(archive, o4, l4), e);
                            byte[] r4 = Compression.OodleDecompressUpTo(b4, usize, out int _);
                            Console.WriteLine($"    {v.Item1,-14} off{v.Item2,+5} len{v.Item3,+5} -> " +
                                              (r4.Length == 0 ? "FAIL" : $"OK {r4.Length:N0}"));
                        }
                        catch (Exception ex) { Console.WriteLine($"    {v.Item1,-14} -> {ex.Message}"); }
                    }
                    Console.WriteLine("  output-size sweep (strided-decrypted input, fuzzSafe=YES):");
                    foreach (int want in new[] { 262144, 524288, 786432, 1048576, 1310720, 1400912, 2097152 })
                    {
                        byte[] o = Compression.OodleDecompressUpTo((byte[])dec.Clone(), want, out int _);
                        Console.WriteLine($"    want {want,9:N0} -> {(o.Length == 0 ? "FAIL" : o.Length.ToString("N0"))}");
                    }
                    Console.WriteLine("  same sweep, WITHOUT decryption:");
                    foreach (int want in new[] { 524288, 1400912 })
                    {
                        byte[] o = Compression.OodleDecompressUpTo((byte[])raw.Clone(), want, out int _);
                        Console.WriteLine($"    want {want,9:N0} -> {(o.Length == 0 ? "FAIL" : o.Length.ToString("N0"))}");
                    }
                    // THE SUSPECT: the decompiled `flag3` shortcut jumps `offset` to
                    // block_stride, which swallows part of the 1 KB tail range. Decrypt the
                    // head + the FULL 1 KB tail instead and see whether Oodle is happy.
                    {
                        var c2 = Cipher.GetCipher(e.GetEncryptionKeyId(), e.platform);
                        byte[] b = (byte[])raw.Clone();
                        long headLen = ((cfg & 3) > 0) ? 1024L << ((cfg & 3) * 2) : 0;
                        if (headLen > 0) b = c2.Decode(b, 0, (int)Math.Min(headLen, b.Length));
                        long tailOff = rawSize - 1024;
                        if (tailOff > headLen) b = c2.Decode(b, (int)tailOff, (int)(rawSize - tailOff));
                        byte[] o = Compression.OodleDecompressUpTo(b, usize, out int _);
                        Console.WriteLine($"  head + FULL 1KB tail (no flag3 jump) -> {(o.Length == 0 ? "FAIL" : o.Length.ToString("N0"))}");
                    }
                    // ...and the same with a fresh cipher per range (CBC state not carried)
                    {
                        byte[] b = (byte[])raw.Clone();
                        long headLen = ((cfg & 3) > 0) ? 1024L << ((cfg & 3) * 2) : 0;
                        if (headLen > 0)
                            b = Cipher.GetCipher(e.GetEncryptionKeyId(), e.platform).Decode(b, 0, (int)Math.Min(headLen, b.Length));
                        long tailOff = rawSize - 1024;
                        if (tailOff > headLen)
                            b = Cipher.GetCipher(e.GetEncryptionKeyId(), e.platform).Decode(b, (int)tailOff, (int)(rawSize - tailOff));
                        byte[] o = Compression.OodleDecompressUpTo(b, usize, out int _);
                        Console.WriteLine($"  head + FULL tail, fresh IV per range -> {(o.Length == 0 ? "FAIL" : o.Length.ToString("N0"))}");
                    }
                    Console.WriteLine($"  declared usize {usize:N0}; low32={(uint)e.Val3:N0} high32={(uint)(e.Val3 >> 32):N0} " +
                                      $"raw-sum={(long)(uint)e.Val3 + (long)(uint)(e.Val3 >> 32):N0}");

                    // How many COMPRESSED bytes do the 5 decodable blocks actually consume?
                    // If that is less than rawSize, the remainder is data for the last block
                    // and the failure is our decode, not a truncated archive.
                    {
                        int fullBlocks = (usize / 262144) * 262144;
                        int lo = 1, hi = dec.Length, need = -1;
                        while (lo <= hi)
                        {
                            int mid = lo + (hi - lo) / 2;
                            byte[] cut = new byte[mid];
                            Array.Copy(dec, cut, mid);
                            byte[] o = Compression.OodleDecompressUpTo(cut, fullBlocks, out int _);
                            if (o.Length == fullBlocks) { need = mid; hi = mid - 1; } else lo = mid + 1;
                        }
                        Console.WriteLine($"  {fullBlocks:N0} raw bytes need {need:N0} compressed bytes of {dec.Length:N0}" +
                                          $"  -> {dec.Length - need:N0} bytes left, tail raw would be {usize - fullBlocks:N0}");
                    }
                    // read-ahead slack for the final partial block
                    foreach (int pad in new[] { 64, 256, 1024 })
                    {
                        byte[] b = new byte[dec.Length + pad];
                        Array.Copy(dec, b, dec.Length);
                        byte[] o = Compression.OodleDecompressUpTo(b, usize, out int _);
                        Console.WriteLine($"  input +{pad}B zero pad -> {(o.Length == 0 ? "FAIL" : o.Length.ToString("N0"))}");
                    }
                    // Sweep the size of the FINAL partial block. Oodle only accepts the exact
                    // raw length, so whatever value succeeds IS the true uncompressed size --
                    // which tells us whether GetOrignalSize() is simply wrong for this entry.
                    {
                        int full = (usize / 262144) * 262144;
                        int found = -1;
                        for (int k = 16; k <= 262144; k += 16)
                        {
                            byte[] o = Compression.OodleDecompressUpTo((byte[])dec.Clone(), full + k, out int _);
                            if (o.Length == full + k) { found = full + k; break; }
                        }
                        Console.WriteLine($"  last-block sweep (16-aligned): {(found < 0 ? "NO SIZE DECODES" : found.ToString("N0"))}" +
                                          $"   declared {usize:N0}");
                    }
                    // 🔑 Both observed failures have a COMPRESSED size just over chunk_size
                    // (524,288). Hypothesis: the compressed stream is cut into independent
                    // Oodle pieces on 524,288-byte boundaries -- which is also exactly what
                    // the strided cipher's chunk_size and stride are describing.
                    {
                        var outMs = new MemoryStream();
                        long piece = 524288;
                        bool ok = true;
                        for (long p = 0; p < dec.Length; p += piece)
                        {
                            int len = (int)Math.Min(piece, dec.Length - p);
                            byte[] slice = new byte[len];
                            Array.Copy(dec, p, slice, 0, len);
                            int wantLeft = usize - (int)outMs.Length;
                            byte[] o = Compression.OodleDecompressUpTo(slice, wantLeft, out int _);
                            if (o.Length == 0)
                            {
                                // a piece may itself be several 256 KB Oodle blocks -> try the
                                // largest block-multiple this piece can yield
                                for (int blk = (wantLeft / 262144) * 262144; blk > 0; blk -= 262144)
                                {
                                    o = Compression.OodleDecompressUpTo((byte[])slice.Clone(), blk, out int _);
                                    if (o.Length > 0) break;
                                }
                            }
                            if (o.Length == 0) { ok = false; break; }
                            outMs.Write(o, 0, o.Length);
                            if (outMs.Length >= usize) break;
                        }
                        Console.WriteLine($"  524KB-piece decode -> {(ok ? "" : "STALLED ")}{outMs.Length:N0} of {usize:N0}" +
                                          $"  {(outMs.Length == usize ? "*** EXACT MATCH ***" : "")}");
                    }
                    // Hypothesis 2: independent Oodle streams packed BACK-TO-BACK. Decode as
                    // much as a stream will give, binary-search how many input bytes that
                    // took, advance by exactly that, repeat.
                    {
                        var outMs = new MemoryStream();
                        int pos = 0;
                        bool progress = true;
                        while (outMs.Length < usize && pos < dec.Length && progress)
                        {
                            progress = false;
                            byte[] slice = new byte[dec.Length - pos];
                            Array.Copy(dec, pos, slice, 0, slice.Length);
                            int remaining = usize - (int)outMs.Length;
                            int got = 0;
                            // exact remainder first, then the largest 256 KB multiple
                            foreach (int want in Enumerable.Range(0, remaining / 262144 + 1)
                                                           .Select(i => i == 0 ? remaining : (remaining / 262144 - i + 1) * 262144)
                                                           .Where(v => v > 0).Distinct())
                            {
                                byte[] o = Compression.OodleDecompressUpTo((byte[])slice.Clone(), want, out int _);
                                if (o.Length > 0) { outMs.Write(o, 0, o.Length); got = o.Length; break; }
                            }
                            if (got == 0) break;
                            int lo = 1, hi = slice.Length, need = slice.Length;
                            while (lo <= hi)
                            {
                                int mid = lo + (hi - lo) / 2;
                                byte[] cut = new byte[mid];
                                Array.Copy(slice, cut, mid);
                                byte[] o = Compression.OodleDecompressUpTo(cut, got, out int _);
                                if (o.Length == got) { need = mid; hi = mid - 1; } else lo = mid + 1;
                            }
                            Console.WriteLine($"    stream @{pos:N0}: {got:N0} raw from {need:N0} bytes");
                            pos += need; progress = true;
                        }
                        Console.WriteLine($"  back-to-back streams -> {outMs.Length:N0} of {usize:N0}" +
                                          $"  {(outMs.Length == usize ? "*** EXACT MATCH ***" : "")}");

                        // Where does the NEXT stream begin? Sweep every 16-aligned offset in
                        // the unconsumed tail and ask whether a stream there yields exactly
                        // the missing bytes. If none does, no packing rule can explain it.
                        int missing = usize - (int)outMs.Length;
                        if (missing > 0)
                        {
                            int hit = -1;
                            for (int off2 = ((int)outMs.Length > 0 ? 479856 : 0) & ~15; off2 + 16 < dec.Length; off2 += 16)
                            {
                                byte[] sl = new byte[dec.Length - off2];
                                Array.Copy(dec, off2, sl, 0, sl.Length);
                                byte[] o = Compression.OodleDecompressUpTo(sl, missing, out int _);
                                if (o.Length == missing) { hit = off2; break; }
                            }
                            Console.WriteLine($"  next-stream offset sweep for {missing:N0} raw bytes -> " +
                                              (hit < 0 ? "NONE in the whole tail" : $"FOUND at {hit:N0}"));
                        }
                    }
                    // last resort: is some part of the tail region still encrypted?
                    foreach (var t in new[] { ("whole file", 0L, rawSize), ("from 5-block end", 479856L, rawSize - 479856L) })
                    {
                        byte[] b = (byte[])raw.Clone();
                        b = Cipher.GetCipher(e.GetEncryptionKeyId(), e.platform).Decode(b, (int)t.Item2, (int)t.Item3);
                        byte[] o = Compression.OodleDecompressUpTo(b, usize, out int _);
                        byte[] o5 = Compression.OodleDecompressUpTo((byte[])b.Clone(), 1310720, out int _);
                        Console.WriteLine($"  decrypt {t.Item1,-18} -> full:{(o.Length == 0 ? "FAIL" : o.Length.ToString("N0"))}" +
                                          $"  5-block:{(o5.Length == 0 ? "FAIL" : o5.Length.ToString("N0"))}");
                    }
                    Console.WriteLine("  input-window sweep (want = full usize):");
                    foreach (var iv in new[] { (-16, 16), (0, -16), (-16, 0) })
                    {
                        long o2 = offset + iv.Item1, l2 = rawSize + iv.Item2;
                        if (o2 < 0 || l2 <= 0) continue;
                        try
                        {
                            byte[] b2 = Cipher.DecodeBlock(ReadRange(archive, o2, l2), e);
                            byte[] o3 = Compression.OodleDecompressUpTo(b2, usize, out int _);
                            Console.WriteLine($"    off{iv.Item1,+4} len{iv.Item2,+4} -> {(o3.Length == 0 ? "FAIL" : o3.Length.ToString("N0"))}");
                        }
                        catch (Exception ex) { Console.WriteLine($"    off{iv.Item1,+4} len{iv.Item2,+4} -> {ex.Message}"); }
                    }
                    Console.WriteLine();
                    if (hashHex != null) return 0;
                }
            }
            return 0;
        }

        static byte[] ReadRange(string path, long off, long len)
        {
            byte[] b = new byte[len];
            using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read))
            {
                fs.Position = off;
                int got = 0;
                while (got < len) { int n = fs.Read(b, got, (int)(len - got)); if (n <= 0) break; got += n; }
            }
            return b;
        }

        static long FreeBytes(string path)
        {
            try
            {
                string root = Path.GetPathRoot(Path.GetFullPath(path));
                return new DriveInfo(root).AvailableFreeSpace;
            }
            catch { return long.MaxValue; }
        }

        static void Usage()
        {
            Console.WriteLine("rpf8 -- Red Dead Redemption 2 RPF8 archive tool (standalone, no OpenIV)");
            Console.WriteLine("  rpf8 info    <archive.rpf>");
            Console.WriteLine("  rpf8 list    <archive.rpf>");
            Console.WriteLine("  rpf8 du      <archive.rpf | folder>   how much disk a full unpack needs");
            Console.WriteLine("  rpf8 extract <archive.rpf> <outdir> [--recursive]");
            Console.WriteLine("  rpf8 unpack  <folder> [--inplace] [--dry-run]");
        }

        static void Summary()
        {
            Console.WriteLine();
            Console.WriteLine($"archives: {totalArchives}   files: {totalFiles}   bytes: {totalBytes:N0}   errors: {totalErrors}");
        }

        static int CmdInfo(string path)
        {
            using (var r = Rpf8Reader.Open(path))
            {
                Console.WriteLine($"file          : {path}");
                Console.WriteLine($"size          : {new FileInfo(path).Length:N0}");
                Console.WriteLine($"entryCount    : {r.header.EntryCount:N0}");
                Console.WriteLine($"namesLength   : {r.header.NamesLength:N0}");
                Console.WriteLine($"decryptionTag : {r.header.DecryptionTag}" +
                                  (r.header.DecryptionTag == 255 ? "  (TOC NOT encrypted)" : "  (TFIT-encrypted TOC)"));
                Console.WriteLine($"platform      : {r.header.PlatformId} ('{(char)r.header.PlatformId}')");
                Console.WriteLine($"names decoded : {r.HashToName.Count / 2} path(s)");
                int enc = 0, res = 0, rpf = 0;
                foreach (var e in r.Entries)
                {
                    if (e.GetEncryptionKeyId() != 255) enc++;
                    if (e.IsResource) res++;
                    if (e.GetFileExtId() == 0) rpf++;
                }
                Console.WriteLine($"entries       : {r.Entries.Count:N0}  (encrypted {enc}, resources {res}, nested .rpf {rpf})");
            }
            return 0;
        }

        /// <summary>
        /// The entry table decrypts perfectly with a fresh CBC IV, but the name table does
        /// not -- so its IV must come from somewhere else. Try every plausible source and
        /// let printable-ASCII count pick the winner (a correct name table is ~100% ASCII).
        /// </summary>
        static int CmdNameTest(string path)
        {
            byte[] hdr = new byte[16];
            long fileLen;
            byte[] entRaw, nameRaw;
            using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read))
            {
                fileLen = fs.Length;
                fs.Read(hdr, 0, 16);
                int ec = BitConverter.ToInt32(hdr, 4);
                int nl = BitConverter.ToInt32(hdr, 8);
                entRaw = new byte[ec * 24];
                fs.Position = 0x110; fs.Read(entRaw, 0, entRaw.Length);
                nameRaw = new byte[nl];
                fs.Position = fileLen - nl; fs.Read(nameRaw, 0, nl);
            }
            ushort tag = BitConverter.ToUInt16(hdr, 12);
            Platform plat = (Platform)BitConverter.ToUInt16(hdr, 14);
            Console.WriteLine($"tag={tag} plat={plat} entries={entRaw.Length}B names={nameRaw.Length}B");

            Func<byte[], int> score = b => { int n = 0; foreach (var c in b) if (c == 0 || (c >= 32 && c < 127)) n++; return n; };

            void Try(string label, Func<byte[], byte[]> f)
            {
                byte[] copy = (byte[])nameRaw.Clone();
                try
                {
                    byte[] o = f(copy);
                    var sb = new StringBuilder();
                    for (int i = 0; i < Math.Min(o.Length, 64); i++) sb.Append(o[i] >= 32 && o[i] < 127 ? (char)o[i] : '.');
                    Console.WriteLine($"  {label,-34} ascii={score(o),5}/{o.Length,-6} |{sb}|");
                }
                catch (Exception ex) { Console.WriteLine($"  {label,-34} ERROR {ex.Message}"); }
            }

            Try("raw (no decrypt)", b => b);
            Try("fresh IV", b => { Cipher.GetCipher(tag, plat).Decode(b, 0, b.Length); return b; });
            Try("continued after entries", b =>
            {
                var c = Cipher.GetCipher(tag, plat);
                c.Decode((byte[])entRaw.Clone(), 0, entRaw.Length);
                c.Decode(b, 0, b.Length);
                return b;
            });
            // names region padded at the FRONT so its length is a multiple of 16
            int pad = (16 - (nameRaw.Length % 16)) % 16;
            if (pad != 0)
            {
                Try($"front-padded by {pad} (from file)", b =>
                {
                    byte[] ext = new byte[nameRaw.Length + pad];
                    using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read))
                    { fs.Position = fileLen - nameRaw.Length - pad; fs.Read(ext, 0, ext.Length); }
                    Cipher.GetCipher(tag, plat).Decode(ext, 0, ext.Length);
                    byte[] outb = new byte[nameRaw.Length];
                    Array.Copy(ext, pad, outb, 0, outb.Length);
                    return outb;
                });
            }
            // Decisive test: if the name table is TFIT-encrypted at all, SOME key tag must
            // turn it into ASCII. Try every key the container holds, with both a fresh IV
            // and an IV continued from the entry table.
            Console.WriteLine("  -- brute force over all key tags --");
            int best = -1, bestTag = -1; string bestMode = null;
            foreach (var kv in KeysContainer.keysValues)
            {
                int t = kv.Key;
                foreach (string mode in new[] { "fresh", "cont" })
                {
                    byte[] b = (byte[])nameRaw.Clone();
                    try
                    {
                        var c = new Tfit2CbcCipher(kv.Value, KeysContainer.iv, KeysContainer.tfit2Context);
                        if (mode == "cont") c.Decode((byte[])entRaw.Clone(), 0, entRaw.Length);
                        c.Decode(b, 0, b.Length);
                        int s = score(b);
                        if (s > best) { best = s; bestTag = t; bestMode = mode; }
                    }
                    catch { }
                }
            }
            Console.WriteLine($"  best: tag={bestTag} mode={bestMode} ascii={best}/{nameRaw.Length}" +
                              $"   (raw baseline = {score(nameRaw)})");
            return 0;
        }

        static int CmdNames(string path)
        {
            using (var r = Rpf8Reader.Open(path))
            {
                Console.WriteLine($"names blob: {r.Names.Length} bytes (decrypted)");
                for (int i = 0; i < Math.Min(r.Names.Length, 512); i += 16)
                {
                    int n = Math.Min(16, r.Names.Length - i);
                    var hex = new StringBuilder();
                    var asc = new StringBuilder();
                    for (int j = 0; j < n; j++)
                    {
                        hex.Append(r.Names[i + j].ToString("x2")).Append(' ');
                        byte b = r.Names[i + j];
                        asc.Append(b >= 32 && b < 127 ? (char)b : '.');
                    }
                    Console.WriteLine($"  {i:x4}  {hex,-48} |{asc}|");
                }
                Console.WriteLine($"resolved {r.HashToName.Count / 2} name(s)");
                foreach (var e in r.Entries)
                    Console.WriteLine($"    hash={e.GetHash():X8} extId={e.GetFileExtId()} -> {r.GetEntryName(e)}");
            }
            return 0;
        }

        static int CmdList(string path)
        {
            using (var r = Rpf8Reader.Open(path))
            {
                foreach (var e in r.Entries)
                {
                    Console.WriteLine($"{r.GetEntryName(e),-70} size={e.GetOrignalSize(),12:N0} disk={e.GetOnDiskSize(),12:N0} " +
                                      $"off={e.GetOffset(),13:N0} comp={e.GetCompressorId()} key={e.GetEncryptionKeyId()} res={(e.IsResource ? 1 : 0)}");
                }
            }
            return 0;
        }

        // ---------------------------------------------------------------- extraction

        static string SafeRelative(string name)
        {
            string s = name.Replace('\\', '/').TrimStart('/');
            var parts = new List<string>();
            foreach (var p in s.Split('/'))
            {
                if (p.Length == 0 || p == ".") continue;
                if (p == "..") continue;                       // never escape the output root
                var sb = new StringBuilder(p.Length);
                foreach (char c in p) sb.Append(Array.IndexOf(Path.GetInvalidFileNameChars(), c) >= 0 ? '_' : c);
                parts.Add(sb.ToString());
            }
            return parts.Count == 0 ? "unnamed" : string.Join(Path.DirectorySeparatorChar.ToString(), parts);
        }

        static void ExtractArchiveFile(string archivePath, string outDir, bool recursive, int depth)
        {
            using (var r = Rpf8Reader.Open(archivePath))
                ExtractArchive(r, outDir, recursive, depth);
        }

        static void ExtractArchive(Rpf8Reader r, string outDir, bool recursive, int depth)
        {
            totalArchives++;
            string pad = new string(' ', depth * 2);
            Console.WriteLine($"{pad}[{r.SourceLabel}] {r.Entries.Count:N0} entries, tag={r.header.DecryptionTag}");
            Directory.CreateDirectory(outDir);

            foreach (var e in r.Entries)
            {
                string name = r.GetEntryName(e);
                string rel = SafeRelative(name);
                string dst = Path.Combine(outDir, rel);
                byte[] data;
                try
                {
                    data = r.GetFile(e);
                }
                catch (Exception ex)
                {
                    totalErrors++;
                    // Salvage: keep the decrypted-but-undecodable bytes rather than lose them.
                    // Combined with "never delete a partially-extracted source", a codec
                    // failure can never destroy data.
                    string salv = "";
                    try
                    {
                        byte[] rawb = r.GetFileRaw(e);
                        Directory.CreateDirectory(Path.GetDirectoryName(dst));
                        File.WriteAllBytes(dst + ".rpf8raw", rawb);
                        salv = $" (salvaged {rawb.Length:N0} raw bytes -> {Path.GetFileName(dst)}.rpf8raw)";
                    }
                    catch { }
                    Console.Error.WriteLine($"{pad}  !! {name}: {ex.Message}{salv}");
                    continue;
                }

                bool nested = data.Length >= 4 && BitConverter.ToUInt32(data, 0) == Rpf8Reader.RPF8_MAGIC;
                if (nested && recursive)
                {
                    // an archive inside an archive -> becomes a FOLDER of the same name
                    try
                    {
                        using (var inner = Rpf8Reader.OpenBytes(data, r.SourceLabel + "/" + name))
                            ExtractArchive(inner, dst, true, depth + 1);
                        continue;
                    }
                    catch (Exception ex)
                    {
                        totalErrors++;
                        Console.Error.WriteLine($"{pad}  !! nested {name}: {ex.Message}");
                    }
                }

                Directory.CreateDirectory(Path.GetDirectoryName(dst));
                File.WriteAllBytes(dst, data);
                totalFiles++;
                totalBytes += data.Length;
            }
        }

        // ------------------------------------------------------------------- unpack

        static int CmdUnpack(string root, bool inplace, bool dry)
        {
            root = Path.GetFullPath(root);
            if (!Directory.Exists(root)) { Console.Error.WriteLine("no such folder: " + root); return 2; }

            // archives deliberately left on disk (a partial extraction, or no room) -- they
            // would otherwise be re-found every round and loop forever
            var kept = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            int round = 0;
            while (true)
            {
                var todo = new List<string>();
                foreach (var f in Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories))
                {
                    if (kept.Contains(f)) continue;
                    try
                    {
                        if (new FileInfo(f).Length < 16) continue;
                        using (var fs = new FileStream(f, FileMode.Open, FileAccess.Read, FileShare.Read))
                        {
                            byte[] m = new byte[4];
                            if (fs.Read(m, 0, 4) != 4) continue;
                            if (BitConverter.ToUInt32(m, 0) == Rpf8Reader.RPF8_MAGIC) todo.Add(f);
                        }
                    }
                    catch { }
                }

                if (todo.Count == 0) break;
                round++;
                Console.WriteLine($"=== round {round}: {todo.Count} archive(s) to unpack ===");
                if (dry)
                {
                    foreach (var t in todo) Console.WriteLine("  " + t);
                    return 0;
                }

                foreach (var f in todo)
                {
                    string dest = f.EndsWith(".rpf", StringComparison.OrdinalIgnoreCase)
                        ? f.Substring(0, f.Length - 4)
                        : f + "_extracted";
                    string tmp = dest + ".__unpacking";
                    // A round extracts ONE level, so the exact cost is the sum of this
                    // archive's entry sizes -- read it from the TOC instead of guessing a
                    // ratio (measured ratios run from 1.0x on audio to 5.4x on textures).
                    long need;
                    try
                    {
                        long sum = 0;
                        using (var probe = Rpf8Reader.Open(f))
                            foreach (var e in probe.Entries) sum += e.GetOrignalSize();
                        need = (long)(sum * 1.05) + (1L << 30);        // +5% slack +1 GB headroom
                    }
                    catch { need = (long)(new FileInfo(f).Length * 1.6); }
                    long have = FreeBytes(dest);
                    if (have < need)
                    {
                        totalErrors++;
                        kept.Add(f);
                        Console.Error.WriteLine($"  !! {Path.GetFileName(f)}: needs ~{need / (1024.0 * 1024 * 1024):F1} GB free, " +
                                                $"only {have / (1024.0 * 1024 * 1024):F1} GB available -- skipped");
                        continue;
                    }
                    try
                    {
                        if (Directory.Exists(tmp)) Directory.Delete(tmp, true);
                        // recursive:false -- nested archives are written out as .rpf files and
                        // handled by the NEXT round, so progress is always resumable on disk
                        int before = totalErrors;
                        ExtractArchiveFile(f, tmp, false, 0);
                        int failed = totalErrors - before;
                        if (Directory.Exists(dest)) Directory.Delete(dest, true);
                        Directory.Move(tmp, dest);
                        // NEVER delete an archive that did not extract completely -- a per-entry
                        // failure would otherwise destroy the only copy of that file.
                        if (inplace && failed == 0) File.Delete(f);
                        if (failed == 0)
                            Console.WriteLine($"  ok  {Path.GetFileName(f)} -> {Path.GetFileName(dest)}{(inplace ? " (source removed)" : "")}");
                        else
                        {
                            kept.Add(f);
                            Console.WriteLine($"  PARTIAL {Path.GetFileName(f)} -> {Path.GetFileName(dest)} " +
                                              $"({failed} entr{(failed == 1 ? "y" : "ies")} failed -- SOURCE KEPT)");
                        }
                    }
                    catch (Exception ex)
                    {
                        // An archive that cannot even be OPENED (e.g. an unknown TFIT key)
                        // must be marked kept -- otherwise the next round re-finds it and the
                        // whole loop spins forever on the same file.
                        totalErrors++;
                        kept.Add(f);
                        Console.Error.WriteLine($"  !! {f}: {ex.Message}");
                    }
                }
                if (!inplace) break;   // without --inplace the sources stay, so a 2nd round would loop forever
            }
            Summary();
            if (kept.Count > 0)
            {
                Console.WriteLine();
                Console.WriteLine($"{kept.Count} archive(s) kept on disk (partial extraction or no room):");
                foreach (var k in kept) Console.WriteLine("  " + k);
            }
            return totalErrors == 0 ? 0 : 1;
        }
    }
}
