#!/usr/bin/env python3
"""Pure-python LZO1X decompressor (port of lzo1x_decompress_safe from the LZO reference).
Needed because the community BFR mods (Thai / Ukrainian) store their forge chunks LZO1X-
compressed, not Oodle, so the project's Oodle path cannot read them."""


def decompress(src, dst_len=None):
    ip = 0
    out = bytearray()
    n = len(src)

    def lit(t):
        nonlocal ip
        out.extend(src[ip:ip + t])
        ip += t

    def match(m_pos, t):
        for _ in range(t):
            out.append(out[m_pos])
            m_pos += 1

    state = 0
    t = 0
    if src[ip] > 17:
        t = src[ip] - 17
        ip += 1
        if t < 4:
            state = 1                      # goto match_next
        else:
            lit(t)
            state = 2                      # goto first_literal_run
    while True:
        if state == 0:
            t = src[ip]; ip += 1
            if t < 16:
                if t == 0:
                    while src[ip] == 0:
                        t += 255; ip += 1
                    t += 15 + src[ip]; ip += 1
                lit(t + 3)
                state = 2
            else:
                state = 3                  # goto match
        if state == 2:                     # first_literal_run
            t = src[ip]; ip += 1
            if t >= 16:
                state = 3
            else:
                m = len(out) - (1 + 0x0800) - (t >> 2) - (src[ip] << 2)
                ip += 1
                match(m, 3)
                state = 4                  # match_done
        while state in (3, 4, 1):
            if state == 3:                 # match
                if t >= 64:
                    m = len(out) - 1 - ((t >> 2) & 7) - (src[ip] << 3)
                    ip += 1
                    t = (t >> 5) - 1
                    match(m, t + 2)
                elif t >= 32:
                    t &= 31
                    if t == 0:
                        while src[ip] == 0:
                            t += 255; ip += 1
                        t += 31 + src[ip]; ip += 1
                    m = len(out) - 1 - ((src[ip] >> 2) + (src[ip + 1] << 6))
                    ip += 2
                    match(m, t + 2)
                elif t >= 16:
                    m = len(out) - ((t & 8) << 11)
                    t &= 7
                    if t == 0:
                        while src[ip] == 0:
                            t += 255; ip += 1
                        t += 7 + src[ip]; ip += 1
                    m -= (src[ip] >> 2) + (src[ip + 1] << 6)
                    ip += 2
                    if m == len(out):
                        return bytes(out)          # EOF
                    m -= 0x4000
                    match(m, t + 2)
                else:
                    m = len(out) - 1 - (t >> 2) - (src[ip] << 2)
                    ip += 1
                    match(m, 2)
                state = 4
            if state == 4:                 # match_done
                t = src[ip - 2] & 3
                if t == 0:
                    state = 0
                    break
                state = 1
            if state == 1:                 # match_next
                lit(t)
                t = src[ip]; ip += 1
                state = 3
        if ip >= n:
            return bytes(out)


if __name__ == "__main__":
    import sys
    d = decompress(open(sys.argv[1], "rb").read())
    sys.stdout.write("%d bytes\n" % len(d))
