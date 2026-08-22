using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Runtime.InteropServices;
using System.Text;

namespace RDR2_RPF_Tool.Core
{
    /// <summary>
    /// Minimal, self-contained RPF8 (Red Dead Redemption 2) archive reader.
    ///
    /// Layout, verified byte-for-byte against the 24 shipping archives:
    ///   0x000  u32 magic 'RPF8' (0x52504638)
    ///   0x004  i32 entryCount
    ///   0x008  i32 namesLength
    ///   0x00C  u16 decryptionTag   (0xFF == archive TOC is NOT encrypted)
    ///   0x00E  u16 platformId      ('y' = 121 = PC, 'o' = 111 = PS4)
    ///   0x010  256-byte RSA signature
    ///   0x110  entryCount * 24 bytes of entries      (TFIT-encrypted when tag != 0xFF)
    ///   ...    file bodies
    ///   EOF-namesLength  NUL-separated path table    (TFIT-encrypted when tag != 0xFF)
    ///
    /// Both encrypted regions follow RAGE's habit of only transforming whole 16-byte
    /// blocks (len &amp; ~15) and leaving the trailing remainder in the clear -- which is
    /// exactly why fragments like "pack/row" and "ifest_tu.xml" are visible in the raw
    /// name tables of an encrypted archive.
    /// </summary>
    public class Rpf8Reader : IDisposable
    {
        public const uint RPF8_MAGIC = 0x52504638;

        public struct Header
        {
            public uint Magic;
            public int EntryCount;
            public int NamesLength;
            public ushort DecryptionTag;
            public Platform PlatformId;
        }

        public class Entry
        {
            public ulong Val1, Val2, Val3;
            public Platform platform;

            public uint GetHash() => (uint)Val1;
            public byte GetEncryptionConfig() => (byte)((Val1 >> 32) & 255UL);
            public byte GetEncryptionKeyId() => (byte)((Val1 >> 40) & 255UL);
            public byte GetFileExtId() => (byte)((Val1 >> 48) & 255UL);
            public bool IsResource => ((Val1 >> 56) & 1UL) != 0;
            public bool IsSignatureProtected => ((Val1 >> 57) & 1UL) != 0;

            public long GetOnDiskSize() => (long)(Val2 & 268435455UL) << 4;
            public long GetOffset() => (long)((Val2 >> 28) & 2147483647UL) << 4;
            public Compressorid GetCompressorId() => (Compressorid)((Val2 >> 59) & 31UL);

            public int GetOrignalSize()
            {
                if (!IsResource) return (int)Val3;
                unchecked
                {
                    return (int)(Val3 & (ulong)-16L) + (int)((Val3 >> 32) & (ulong)-16L);
                }
            }

            public GetResourceType GetResourceType() => (GetResourceType)((Val3 >> 32) & 15UL);
        }

        // ---- RAGE file-extension table (# is replaced by the platform char) ----
        static readonly string[] BaseRageExts = {
            "rpf","#mf","#dr","#ft","#dd","#td","#bn","#bd","#pd","#bs","#sd","#mt","#sc","#cs" };
        static readonly string[] ExtraRageExts = {
            "mrf","cut","gfx","#cd","#ld","#pmd","#pm","#ed","#pt","#map","#typ","#ch","#ldb",
            "#jd","#ad","#nv","#hn","#pl","#nd","#vr","#wr","#nh","#fd","#as" };

        public static string GetFileExt(int id, Platform platform)
        {
            if (id >= 0 && id < BaseRageExts.Length) return "." + BaseRageExts[id].Replace('#', (char)platform);
            if (id >= 64 && id <= 87) return "." + ExtraRageExts[id - 64].Replace('#', (char)platform);
            return "";
        }

        public static int GetFileExtId(string ext, Platform platform)
        {
            ext = ext.TrimStart('.').Trim();
            for (int i = 0; i < BaseRageExts.Length; i++)
                if (string.Equals(BaseRageExts[i].Replace('#', (char)platform), ext, StringComparison.OrdinalIgnoreCase)) return i;
            for (int j = 0; j < ExtraRageExts.Length; j++)
                if (string.Equals(ExtraRageExts[j].Replace('#', (char)platform), ext, StringComparison.OrdinalIgnoreCase)) return j + 64;
            return 255;
        }

        public Header header;
        public byte[] RsaSignature;
        public List<Entry> Entries = new List<Entry>();
        public byte[] Names;                                   // decrypted NUL-separated path table
        public Dictionary<uint, string> HashToName = new Dictionary<uint, string>();

        Stream _s;
        bool _ownsStream;
        public string SourceLabel;

        public static Rpf8Reader Open(string path)
        {
            var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20);
            var r = new Rpf8Reader { _s = fs, _ownsStream = true, SourceLabel = path };
            r.Load();
            return r;
        }

        public static Rpf8Reader OpenBytes(byte[] data, string label)
        {
            var ms = new MemoryStream(data, false);
            var r = new Rpf8Reader { _s = ms, _ownsStream = true, SourceLabel = label };
            r.Load();
            return r;
        }

        static uint RdU32(byte[] b, int o) => BitConverter.ToUInt32(b, o);

        void Load()
        {
            byte[] hdr = ReadAt(0, 16);
            header.Magic = RdU32(hdr, 0);
            if (header.Magic != RPF8_MAGIC)
                throw new InvalidDataException($"not an RPF8 archive (magic 0x{header.Magic:X8}): {SourceLabel}");
            header.EntryCount = BitConverter.ToInt32(hdr, 4);
            header.NamesLength = BitConverter.ToInt32(hdr, 8);
            header.DecryptionTag = BitConverter.ToUInt16(hdr, 12);
            header.PlatformId = (Platform)BitConverter.ToUInt16(hdr, 14);

            RsaSignature = ReadAt(16, 256);

            byte[] entBlob = ReadAt(0x110, (long)header.EntryCount * 24);
            byte[] nameBlob = header.NamesLength > 0
                ? ReadAt(_s.Length - header.NamesLength, header.NamesLength)
                : new byte[0];

            if (header.DecryptionTag != 255)
            {
                // a FRESH cipher per region: CBC state (the IV) advances as it decrypts
                Cipher.GetCipher(header.DecryptionTag, header.PlatformId).Decode(entBlob, 0, entBlob.Length);
                if (nameBlob.Length > 0)
                    Cipher.GetCipher(header.DecryptionTag, header.PlatformId).Decode(nameBlob, 0, nameBlob.Length);
            }

            for (int i = 0; i < header.EntryCount; i++)
            {
                int o = i * 24;
                Entries.Add(new Entry
                {
                    Val1 = BitConverter.ToUInt64(entBlob, o),
                    Val2 = BitConverter.ToUInt64(entBlob, o + 8),
                    Val3 = BitConverter.ToUInt64(entBlob, o + 16),
                    platform = header.PlatformId,
                });
            }

            Names = nameBlob;
            BuildNameMap();
            // an unencrypted name table is authoritative -- share it with every other archive
            if (header.DecryptionTag == 255) NameDb.AddFromBlob(nameBlob);
        }

        /// <summary>
        /// The name table is a NUL-separated list of real paths. Entries reference them
        /// only by JOAAT hash, so rebuild the mapping by hashing each name the same way
        /// the packer did: with the extension stripped when the extension is one the
        /// format has an id for, otherwise on the full path.
        /// </summary>
        void BuildNameMap()
        {
            if (Names == null || Names.Length == 0) return;
            int start = 0;
            for (int i = 0; i <= Names.Length; i++)
            {
                if (i == Names.Length || Names[i] == 0)
                {
                    if (i > start)
                    {
                        string name = Encoding.UTF8.GetString(Names, start, i - start);
                        if (name.Length > 0 && IsPlausiblePath(name))
                        {
                            string norm = name.Replace('\\', '/');
                            string noExt = norm;
                            int dot = norm.LastIndexOf('.');
                            int slash = norm.LastIndexOf('/');
                            if (dot > slash && dot >= 0) noExt = norm.Substring(0, dot);
                            HashToName[JOAATHash.Calc(noExt)] = norm;   // ext-id path
                            HashToName[JOAATHash.Calc(norm)] = norm;    // full-path fallback
                        }
                    }
                    start = i + 1;
                }
            }
        }

        static bool IsPlausiblePath(string s)
        {
            foreach (char c in s) if (c < 0x20 || c > 0x7E) return false;
            return true;
        }

        public string GetEntryName(Entry e)
        {
            uint h = e.GetHash();
            string n;
            if (!HashToName.TryGetValue(h, out n)) NameDb.TryGet(h, out n);
            if (n != null)
            {
                string ext = GetFileExt(e.GetFileExtId(), e.platform);
                if (ext.Length > 0 && !n.EndsWith(ext, StringComparison.OrdinalIgnoreCase)) return n + ext;
                return n;
            }
            return "0x" + h.ToString("X8") + GetFileExt(e.GetFileExtId(), e.platform);
        }

        byte[] ReadAt(long off, long len)
        {
            if (len < 0 || off < 0 || off + len > _s.Length)
                throw new InvalidDataException($"read {len} @ {off} out of range (file {_s.Length}) in {SourceLabel}");
            byte[] b = new byte[len];
            _s.Position = off;
            int got = 0;
            while (got < len)
            {
                int n = _s.Read(b, got, (int)(len - got));
                if (n <= 0) throw new EndOfStreamException();
                got += n;
            }
            return b;
        }

        /// <summary>
        /// Read one entry and decrypt it, but do NOT decompress. Used to salvage an entry
        /// whose codec refuses it, so no byte of the archive is ever lost to a failed decode.
        /// </summary>
        public byte[] GetFileRaw(Entry entry)
        {
            long rawSize = entry.GetOnDiskSize();
            long offset = entry.GetOffset();
            if (entry.IsSignatureProtected) { rawSize -= 256; offset += 256; }
            if (entry.IsResource) { offset += 16; rawSize -= 16; }
            return Cipher.DecodeBlock(ReadAt(offset, rawSize), entry);
        }

        /// <summary>
        /// Read one entry, decrypt (strided) and decompress it.
        ///
        /// 🔴 The 256-byte "signature" is NOT always a leading header. Measured on
        /// data_0/data/ui/screens.rpf, where every one of its 461 entries sets the flag:
        /// skipping 256 bytes at the FRONT makes all 461 fail, and not skipping decodes
        /// them perfectly. So the primary layout is tried first and, when it fails, the
        /// entry is retried without the leading skip. A fallback rather than a replacement,
        /// because an archive that decodes today must keep decoding.
        /// </summary>
        public byte[] GetFile(Entry entry)
        {
            Exception first = null;
            foreach (bool skipSig in entry.IsSignatureProtected ? new[] { true, false } : new[] { false })
            {
                long rawSize = entry.GetOnDiskSize();
                long offset = entry.GetOffset();
                if (skipSig)
                {
                    if (rawSize < 256) continue;
                    rawSize -= 256; offset += 256;
                }
                if (entry.IsResource)
                {
                    if (rawSize < 16) throw new InvalidDataException("resource file too small");
                    offset += 16; rawSize -= 16;
                }
                try
                {
                    byte[] bytes = Cipher.DecodeBlock(ReadAt(offset, rawSize), entry);
                    return Compression.DecompressFile(bytes, entry.GetOrignalSize(), entry.GetCompressorId());
                }
                catch (Exception ex) { first ??= ex; }
            }
            throw first ?? new InvalidDataException("entry could not be read");
        }

        public void Dispose()
        {
            if (_ownsStream && _s != null) { _s.Dispose(); _s = null; }
        }
    }

    /// <summary>Strided-CBC decryption of a single stored file (ported call-for-call).</summary>
    public static class Cipher
    {
        public static ICipher GetCipher(int tag, Platform platform)
        {
            if (platform == Platform.Pc)
            {
                if (!KeysContainer.keysValues.TryGetValue(tag, out Tfit2CbcCipher.Tfit2Key k))
                    throw new Exception($"no TFIT2 key for tag {tag}");
                return new Tfit2CbcCipher(k, KeysContainer.iv, KeysContainer.tfit2Context);
            }
            if (platform == Platform.Ps4)
            {
                if (tag >= 163)
                {
                    if (tag != 192) throw new Exception($"no TFIT key for tag {tag}");
                    tag = 163;
                }
                return new TfitCbcCipher(KeysContainer.RDR2_PS4_TFIT_KEYS[tag], KeysContainer.RDR2_PS4_TFIT_TABLES, KeysContainer.iv);
            }
            throw new Exception("unknown platform " + (int)platform);
        }

        public static byte[] DecodeBlock(byte[] bytes, Rpf8Reader.Entry entry)
        {
            if (entry.GetEncryptionKeyId() == byte.MaxValue) return bytes;

            int size = entry.GetOrignalSize();
            long rawSize = entry.GetOnDiskSize();
            bool isCompressed = entry.GetCompressorId() > Compressorid.None;
            if (entry.IsSignatureProtected) rawSize -= 256;
            if (entry.IsResource) rawSize -= 16;

            long chunkSize = entry.IsResource
                ? (isCompressed ? 524288L : size)
                : (isCompressed ? 8192L : 4096L);

            var ranges = StridedCipher.UnpackConfig(entry.GetEncryptionConfig(), rawSize, chunkSize);
            var cipher = GetCipher(entry.GetEncryptionKeyId(), entry.platform);
            foreach (var r in ranges)
            {
                int start = (int)r[0];
                int len = (int)(r[1] - r[0]);
                if (start < 0 || len <= 0 || start + len > bytes.Length) continue;
                bytes = cipher.Decode(bytes, start, len);
            }
            return bytes;
        }
    }

    public static class Compression
    {
        [DllImport("oo2core_5_win64.dll")]
        static extern int OodleLZ_Decompress(byte[] Buffer, long BufferSize, byte[] OutputBuffer, long OutputBufferSize,
            uint a, uint b, uint c, uint d, uint e, uint f, uint g, uint h, uint i, int ThreadModule);

        /// <summary>
        /// 🔴 fuzzSafe MUST be YES (1). With fuzzSafe=NO Oodle trusts the caller's sizes and
        /// reads past the buffer on malformed input -- which killed a full unpack run with an
        /// AccessViolationException inside the native call. That is a corrupted-state
        /// exception: .NET cannot catch it, so a try/catch around the extractor does NOT
        /// help. Not crashing is only achievable by not letting Oodle run off the buffer.
        /// fuzzSafe also wants slack in the output buffer, hence the +64.
        /// </summary>
        public static byte[] OodleDecompress(byte[] data, int decompressedSize)
        {
            byte[] outBuf = new byte[(long)decompressedSize + 64];
            int n = OodleLZ_Decompress(data, data.Length, outBuf, decompressedSize, 1, 0, 0, 0, 0, 0, 0, 0, 0, 3);
            if (n != decompressedSize)
                throw new Exception($"Oodle decompress failed ({n} != {decompressedSize})");
            Array.Resize(ref outBuf, decompressedSize);
            return outBuf;
        }

        /// <summary>
        /// Decode ONE Oodle block and report how many input bytes it consumed -- used to test
        /// whether a large resource is stored as several independent 512 KB blocks.
        /// </summary>
        /// <summary>
        /// Probe-only decode. Uses fuzzSafe=YES: with fuzzSafe=NO Oodle trusts the caller's
        /// size and will HANG or run off the buffer on a mismatch (observed), which makes it
        /// useless for asking "what size is this really?".
        /// </summary>
        public static byte[] OodleDecompressUpTo(byte[] data, int want, out int consumed)
        {
            byte[] outBuf = new byte[want + 64];        // fuzzSafe wants slack
            int n = OodleLZ_Decompress(data, data.Length, outBuf, want, 1, 0, 0, 0, 0, 0, 0, 0, 0, 3);
            consumed = n <= 0 ? 0 : data.Length;
            if (n <= 0) return new byte[0];
            Array.Resize(ref outBuf, n);
            return outBuf;
        }

        public static byte[] DeflateDecompress(byte[] data)
        {
            using (var outMs = new MemoryStream())
            using (var inMs = new MemoryStream(data))
            using (var ds = new DeflateStream(inMs, CompressionMode.Decompress))
            {
                ds.CopyTo(outMs);
                return outMs.ToArray();
            }
        }

        public static byte[] DecompressFile(byte[] bytes, int usize, Compressorid id)
        {
            switch (id)
            {
                case Compressorid.None:
                    if (usize >= 0 && usize <= bytes.Length) Array.Resize(ref bytes, usize);
                    return bytes;
                case Compressorid.Deflate: return DeflateDecompress(bytes);
                case Compressorid.Oodle: return OodleDecompress(bytes, usize);
                default: throw new Exception("unknown compressor id: " + id);
            }
        }
    }
}
