#!/usr/bin/env python3
"""
AC2 bitmap-font atlas codec — read the DXT glyph atlas out of a *_MapDesc
resource and write a modified one back, preserving the container exactly.

A *CharacterSet/Latin/Numbers* _MapDesc resource = FILEDATA(8)+name(128) +
DataFile( prefetch + CFD1[small hdr] + CFD2[the TextureMap container] + sig ).
The CFD2 payload (big-endian-ish TextureMap/CompiledTextureMap) embeds the raw
DXT texture as  [int32 count][count bytes]  with a trailer
[PlatformVersion u32][SDKVersion u32][Width u32][Height u32][Depth u32]
[MipMapCount u32][PixelFormat int32]... .  PixelFormat 3 = DXT1(BC1), 5 = DXT5(BC3).

We replace ONLY the texture bytes (same length), re-pack CFD2 as STORED blocks,
splice the resource back together, and relocate it via Forge.write_resource.
"""
import sys, os, struct, io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import ac2_cfd, ac2_forge

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PIXFMT = {3: b"DXT1", 5: b"DXT5"}   # AC2 PixelFormat -> DDS FourCC


class Atlas:
    """Parsed font atlas: the decompressed CFD2 payload + the texture location."""
    def __init__(self, resource: bytes):
        self.resource = resource
        # locate CFD2 (the big one) inside the resource
        cfds = []
        pos = resource.find(ac2_cfd.CFD_MAGIC)
        while 0 <= pos < len(resource) - 8 and resource[pos:pos+8] == ac2_cfd.CFD_MAGIC:
            data, nxt = ac2_cfd.parse_one_cfd(resource, pos)
            cfds.append((pos, nxt, data))
            pos = nxt if resource[nxt:nxt+8] == ac2_cfd.CFD_MAGIC else resource.find(ac2_cfd.CFD_MAGIC, nxt)
        if not cfds:
            raise RuntimeError("no CFD in resource")
        self.cfd2_start, self.cfd2_end, self.payload = max(cfds, key=lambda c: len(c[2]))
        # locate the texture: int32 count whose [count bytes]+small trailer fits
        # locate the CompiledTexture: [int32 count][count bytes] followed by a
        # trailer [PlatformVersion][SDK][Width][Height][Depth][Mips][PixelFormat].
        # Validate a candidate by the trailer's W/H/pixfmt AND size == DXT(W,H,fmt).
        big = self.payload
        self.texoff = self.texsize = None
        _dxt = {3: lambda w, h: w * h // 2, 5: lambda w, h: w * h, 0: lambda w, h: w * h}
        for p in range(0, min(len(big), 2000)):
            c = struct.unpack_from("<I", big, p)[0]
            if not (4096 <= c and c % 8 == 0 and p + 4 + c + 28 <= len(big)):
                continue
            tp = p + 4 + c
            w, h, pf = (struct.unpack_from("<I", big, tp + 8)[0],
                        struct.unpack_from("<I", big, tp + 12)[0],
                        struct.unpack_from("<I", big, tp + 24)[0])
            if (w in (128, 256, 512, 1024, 2048) and h in (128, 256, 512, 1024, 2048)
                    and pf in _dxt and _dxt[pf](w, h) == c):
                self.texoff, self.texsize = p + 4, c
                break
        if self.texoff is None:
            raise RuntimeError("texture payload not found")
        tp = self.texoff + self.texsize
        (self.platform, self.sdk, self.width, self.height,
         self.depth, self.mips) = struct.unpack_from("<6I", big, tp)
        self.pixfmt = struct.unpack_from("<I", big, tp + 24)[0]

    @property
    def texture(self):
        return self.payload[self.texoff:self.texoff + self.texsize]

    @property
    def fourcc(self):
        return PIXFMT[self.pixfmt]

    def rebuild(self, new_texture: bytes) -> bytes:
        """Return a full modified resource with the texture replaced."""
        if len(new_texture) != self.texsize:
            raise ValueError(f"texture size changed {self.texsize} -> {len(new_texture)}")
        new_payload = (self.payload[:self.texoff] + new_texture
                       + self.payload[self.texoff + self.texsize:])
        new_cfd2 = ac2_cfd.encode_cfd_stored(new_payload)
        return (self.resource[:self.cfd2_start] + new_cfd2 + self.resource[self.cfd2_end:])


def load(forge_path, name):
    fg = ac2_forge.Forge(forge_path)
    i = fg.by_name(name)
    if i < 0:
        raise RuntimeError("not found: " + name)
    slot, off, nxt = fg.full_slot(i)
    return fg, i, Atlas(slot)


def dds_bytes(w, h, fourcc, body):
    hh = bytearray(128); hh[0:4] = b"DDS "
    struct.pack_into("<I", hh, 4, 124)
    struct.pack_into("<I", hh, 8, 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000)
    struct.pack_into("<I", hh, 12, h); struct.pack_into("<I", hh, 16, w)
    struct.pack_into("<I", hh, 20, len(body)); struct.pack_into("<I", hh, 28, 1)
    struct.pack_into("<I", hh, 76, 32); struct.pack_into("<I", hh, 80, 0x4)
    hh[84:88] = fourcc; struct.pack_into("<I", hh, 108, 0x1000)
    return bytes(hh) + body


def decode_image(atlas):
    """Decode the atlas texture to an RGBA PIL image."""
    from PIL import Image
    return Image.open(io.BytesIO(dds_bytes(atlas.width, atlas.height, atlas.fourcc,
                                           atlas.texture))).convert("RGBA")


if __name__ == "__main__":
    name = sys.argv[2] if len(sys.argv) > 2 else "AC2Aaux_ProBold_Latin_1_MapDesc"
    forge = sys.argv[1] if len(sys.argv) > 1 else r"D:/Games/Assassin's Creed II/DataPC_extra.forge"
    fg, i, at = load(forge, name)
    print(f"{name}: idx={i} payload={len(at.payload)} tex@{at.texoff} size={at.texsize} "
          f"{at.width}x{at.height} pixfmt={at.pixfmt}({at.fourcc.decode()})")
    # identity rebuild check
    rb = at.rebuild(at.texture)
    at2 = Atlas(rb)
    print("identity rebuild: texture match =", at2.texture == at.texture,
          "| dims match =", (at2.width, at2.height, at2.pixfmt) == (at.width, at.height, at.pixfmt))
