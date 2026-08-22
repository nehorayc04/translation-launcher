"""LZO1x decompress for Dunia scheme-2 entries, via the lzallright Rust binding."""
import lzallright

_D = lzallright.LZOCompressor()


def lzo_decompress(comp, unc_size):
    out = _D.decompress(bytes(comp), unc_size)
    return bytes(out)
