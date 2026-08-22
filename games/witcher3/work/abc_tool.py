# -*- coding: utf-8 -*-
"""Minimal AS3 ABC (ActionScript Byte Code) reader for the TW3 Scaleform GFx.

Purpose: locate a method by name (e.g. `updateCurrentTimeString`) inside a DoABC tag and disassemble
its body, so a surgical IN-PLACE byte patch can be made (same code length -> the GFx/CFX/redswf
structure is untouched, which is the only safe way to edit a shipped Flash).

Only what we need is implemented: constant pool, method_info names, method bodies, and a disassembler
for the opcodes these menus actually use.
"""
import struct


# ---------------------------------------------------------------- primitives
class R:
    def __init__(self, b, p=0):
        self.b = b
        self.p = p

    def u8(self):
        v = self.b[self.p]; self.p += 1; return v

    def u16(self):
        v = struct.unpack_from("<H", self.b, self.p)[0]; self.p += 2; return v

    def u30(self):
        """7-bit varint (max 5 bytes)."""
        v = 0
        for i in range(5):
            c = self.b[self.p]; self.p += 1
            v |= (c & 0x7F) << (7 * i)
            if not (c & 0x80):
                break
        return v

    u32 = u30

    def s32(self):
        return self.u30()

    def d64(self):
        v = struct.unpack_from("<d", self.b, self.p)[0]; self.p += 8; return v

    def utf(self):
        n = self.u30()
        s = self.b[self.p:self.p + n]; self.p += n
        return s.decode("utf-8", "replace")


# ---------------------------------------------------------------- ABC structure
MULTINAME_SKIP = {
    0x07: 2, 0x0D: 2,          # QName / QNameA        -> ns, name
    0x0F: 1, 0x10: 1,          # RTQName / RTQNameA    -> name
    0x11: 0, 0x12: 0,          # RTQNameL / RTQNameLA
    0x09: 2, 0x0E: 2,          # Multiname / MultinameA-> name, ns_set
    0x1B: 1, 0x1C: 1,          # MultinameL/ MultinameLA-> ns_set
}


class ABC:
    def __init__(self, data):
        self.data = data
        r = R(data)
        self.minor = r.u16(); self.major = r.u16()
        # ---- constant pool
        n = r.u30()
        self.ints = [0] + [r.s32() for _ in range(max(0, n - 1))]
        n = r.u30()
        self.uints = [0] + [r.u32() for _ in range(max(0, n - 1))]
        n = r.u30()
        self.doubles = [0.0] + [r.d64() for _ in range(max(0, n - 1))]
        n = r.u30()
        self.strings = [""] + [r.utf() for _ in range(max(0, n - 1))]
        n = r.u30()
        self.namespaces = [None]
        for _ in range(max(0, n - 1)):
            r.u8(); r.u30()
            self.namespaces.append(None)
        n = r.u30()
        self.ns_sets = [None]
        for _ in range(max(0, n - 1)):
            c = r.u30()
            for _i in range(c):
                r.u30()
            self.ns_sets.append(None)
        n = r.u30()
        self.multinames = [None]
        for _ in range(max(0, n - 1)):
            kind = r.u8()
            if kind == 0x1D:                       # TypeName
                r.u30()
                c = r.u30()
                for _i in range(c):
                    r.u30()
                self.multinames.append(("TypeName", 0))
            else:
                skip = MULTINAME_SKIP.get(kind)
                if skip is None:
                    raise ValueError(f"unknown multiname kind {kind:#x}")
                vals = [r.u30() for _ in range(skip)]
                # for QName/Multiname the *name* string index is the last operand
                nm = vals[-1] if vals else 0
                self.multinames.append((kind, nm))
        # ---- methods
        self.method_count = r.u30()
        self.methods = []                          # (name_string_index,)
        for _ in range(self.method_count):
            pc = r.u30(); r.u30()                  # param_count, return_type
            for _i in range(pc):
                r.u30()
            name = r.u30()
            flags = r.u8()
            if flags & 0x08:                       # HAS_OPTIONAL
                oc = r.u30()
                for _i in range(oc):
                    r.u30(); r.u8()
            if flags & 0x80:                       # HAS_PARAM_NAMES
                for _i in range(pc):
                    r.u30()
            self.methods.append(name)
        # ---- metadata
        n = r.u30()
        for _ in range(n):
            r.u30()
            c = r.u30()
            for _i in range(c):
                r.u30(); r.u30()
        # ---- classes
        cc = r.u30()
        for _ in range(cc):                        # instance_info
            r.u30(); r.u30()
            flags = r.u8()
            if flags & 0x08:
                r.u30()
            ic = r.u30()
            for _i in range(ic):
                r.u30()
            r.u30()                                # iinit
            self._traits(r)
        for _ in range(cc):                        # class_info
            r.u30()                                # cinit
            self._traits(r)
        # ---- scripts
        sc = r.u30()
        for _ in range(sc):
            r.u30()
            self._traits(r)
        # ---- method bodies
        bc = r.u30()
        self.bodies = []                           # dicts
        for _ in range(bc):
            m = r.u30(); r.u30(); r.u30(); r.u30(); r.u30()
            cl = r.u30()
            code_off = r.p
            code = self.data[r.p:r.p + cl]; r.p += cl
            ec = r.u30()
            for _i in range(ec):
                r.u30(); r.u30(); r.u30(); r.u30(); r.u30()
            self._traits(r)
            self.bodies.append({"method": m, "code_off": code_off, "code_len": cl, "code": code})

    def _traits(self, r):
        tc = r.u30()
        for _ in range(tc):
            tname = r.u30()                        # name (multiname index)
            k = r.u8()
            kind = k & 0x0F
            if kind in (0, 6):                     # Slot / Const
                r.u30(); r.u30()
                vi = r.u30()
                if vi:
                    r.u8()
            elif kind in (1, 2, 3):                # Method / Getter / Setter
                r.u30()
                midx = r.u30()
                # AS3 keeps the method NAME on the trait, not in method_info
                if not hasattr(self, "trait_methods"):
                    self.trait_methods = []
                self.trait_methods.append((tname, midx, kind))
            elif kind == 4:                        # Class
                r.u30(); r.u30()
            elif kind == 5:                        # Function
                r.u30(); r.u30()
            else:
                raise ValueError(f"bad trait kind {kind}")
            if k & 0x40:                           # METADATA
                mc = r.u30()
                for _i in range(mc):
                    r.u30()

    # ------------------------------------------------------------ helpers
    def method_named(self, name):
        """-> list of (method_index, body). Looks the method up by its TRAIT name (AS3 keeps the
        name there, not in method_info), falling back to method_info.name."""
        out = []
        seen = set()
        for tname, midx, _k in getattr(self, "trait_methods", []):
            if self.mn_name(tname) == name and midx not in seen:
                seen.add(midx)
                for b in self.bodies:
                    if b["method"] == midx:
                        out.append((midx, b))
        if out:
            return out
        try:
            si = self.strings.index(name)
        except ValueError:
            return []
        for mi, nm in enumerate(self.methods):
            if nm == si:
                for b in self.bodies:
                    if b["method"] == mi:
                        out.append((mi, b))
        return out

    def mn_name(self, idx):
        m = self.multinames[idx] if 0 <= idx < len(self.multinames) else None
        if not m:
            return "?"
        if m[0] == "TypeName":
            return "<TypeName>"
        return self.strings[m[1]] if m[1] < len(self.strings) else "?"


# ---------------------------------------------------------------- disassembler
# opcode -> (mnemonic, operand kinds)  u30=index, u8=byte, s24=jump offset
OPS = {
    0x02: ("nop", []), 0x03: ("throw", []), 0x04: ("getsuper", ["u30"]), 0x05: ("setsuper", ["u30"]),
    0x08: ("kill", ["u30"]), 0x09: ("label", []),
    0x0C: ("ifnlt", ["s24"]), 0x0D: ("ifnle", ["s24"]), 0x0E: ("ifngt", ["s24"]), 0x0F: ("ifnge", ["s24"]),
    0x10: ("jump", ["s24"]), 0x11: ("iftrue", ["s24"]), 0x12: ("iffalse", ["s24"]),
    0x13: ("ifeq", ["s24"]), 0x14: ("ifne", ["s24"]), 0x15: ("iflt", ["s24"]), 0x16: ("ifle", ["s24"]),
    0x17: ("ifgt", ["s24"]), 0x18: ("ifge", ["s24"]), 0x19: ("ifstricteq", ["s24"]), 0x1A: ("ifstrictne", ["s24"]),
    0x1D: ("popscope", []), 0x1E: ("nextname", []), 0x20: ("pushnull", []), 0x21: ("pushundefined", []),
    0x23: ("nextvalue", []), 0x24: ("pushbyte", ["u8"]), 0x25: ("pushshort", ["u30"]),
    0x26: ("pushtrue", []), 0x27: ("pushfalse", []), 0x28: ("pushnan", []), 0x29: ("pop", []),
    0x2A: ("dup", []), 0x2B: ("swap", []), 0x2C: ("pushstring", ["u30"]), 0x2D: ("pushint", ["u30"]),
    0x2E: ("pushuint", ["u30"]), 0x2F: ("pushdouble", ["u30"]), 0x30: ("pushscope", []),
    0x31: ("pushnamespace", ["u30"]), 0x32: ("hasnext2", ["u30", "u30"]),
    0x40: ("newfunction", ["u30"]), 0x41: ("call", ["u30"]), 0x42: ("construct", ["u30"]),
    0x43: ("callmethod", ["u30", "u30"]), 0x44: ("callstatic", ["u30", "u30"]),
    0x45: ("callsuper", ["u30", "u30"]), 0x46: ("callproperty", ["u30", "u30"]),
    0x47: ("returnvoid", []), 0x48: ("returnvalue", []), 0x49: ("constructsuper", ["u30"]),
    0x4A: ("constructprop", ["u30", "u30"]), 0x4C: ("callproplex", ["u30", "u30"]),
    0x4E: ("callsupervoid", ["u30", "u30"]), 0x4F: ("callpropvoid", ["u30", "u30"]),
    0x53: ("applytype", ["u30"]), 0x55: ("newobject", ["u30"]), 0x56: ("newarray", ["u30"]),
    0x57: ("newactivation", []), 0x58: ("newclass", ["u30"]), 0x59: ("getdescendants", ["u30"]),
    0x5A: ("newcatch", ["u30"]), 0x5D: ("findpropstrict", ["u30"]), 0x5E: ("findproperty", ["u30"]),
    0x60: ("getlex", ["u30"]), 0x61: ("setproperty", ["u30"]), 0x62: ("getlocal", ["u30"]),
    0x63: ("setlocal", ["u30"]), 0x64: ("getglobalscope", []), 0x65: ("getscopeobject", ["u8"]),
    0x66: ("getproperty", ["u30"]), 0x68: ("initproperty", ["u30"]), 0x6A: ("deleteproperty", ["u30"]),
    0x6C: ("getslot", ["u30"]), 0x6D: ("setslot", ["u30"]),
    0x70: ("convert_s", []), 0x71: ("esc_xelem", []), 0x73: ("convert_i", []), 0x74: ("convert_u", []),
    0x75: ("convert_d", []), 0x76: ("convert_b", []), 0x77: ("convert_o", []),
    0x80: ("coerce", ["u30"]), 0x82: ("coerce_a", []), 0x85: ("coerce_s", []),
    0x87: ("astypelate", []), 0x90: ("negate", []), 0x91: ("increment", []),
    0x93: ("decrement", []), 0x95: ("typeof", []), 0x96: ("not", []),
    0xA0: ("add", []), 0xA1: ("subtract", []), 0xA2: ("multiply", []), 0xA3: ("divide", []),
    0xA4: ("modulo", []), 0xA5: ("lshift", []), 0xA6: ("rshift", []), 0xA8: ("bitand", []),
    0xA9: ("bitor", []), 0xAA: ("bitxor", []), 0xAB: ("equals", []), 0xAC: ("strictequals", []),
    0xAD: ("lessthan", []), 0xAE: ("lessequals", []), 0xAF: ("greaterthan", []), 0xB0: ("greaterequals", []),
    0xB3: ("istypelate", []), 0xB4: ("in", []),
    0xC0: ("increment_i", []), 0xC1: ("decrement_i", []), 0xC2: ("inclocal_i", ["u30"]),
    0xC5: ("add_i", []), 0xC6: ("subtract_i", []),
    0xD0: ("getlocal_0", []), 0xD1: ("getlocal_1", []), 0xD2: ("getlocal_2", []), 0xD3: ("getlocal_3", []),
    0xD4: ("setlocal_0", []), 0xD5: ("setlocal_1", []), 0xD6: ("setlocal_2", []), 0xD7: ("setlocal_3", []),
    0xEF: ("debug", ["u8", "u30", "u8", "u30"]), 0xF0: ("debugline", ["u30"]), 0xF1: ("debugfile", ["u30"]),
}


def disasm(abc, code):
    """-> list of (offset, size, mnemonic, [operands], rendered)"""
    out = []
    r = R(code)
    while r.p < len(code):
        off = r.p
        op = r.u8()
        mn, kinds = OPS.get(op, (f"op_{op:02x}", []))
        ops = []
        for k in kinds:
            if k == "u30":
                ops.append(r.u30())
            elif k == "u8":
                ops.append(r.u8())
            elif k == "s24":
                v = code[r.p] | (code[r.p + 1] << 8) | (code[r.p + 2] << 16)
                if v & 0x800000:
                    v -= 0x1000000
                r.p += 3
                ops.append(v)
        txt = f"{mn}"
        if mn == "pushstring" and ops[0] < len(abc.strings):
            txt += f" {abc.strings[ops[0]]!r}"
        elif mn in ("getproperty", "setproperty", "callproperty", "callpropvoid", "findpropstrict",
                    "findproperty", "getlex", "initproperty", "coerce", "constructprop", "callproplex"):
            txt += f" {abc.mn_name(ops[0])}"
            if len(ops) > 1:
                txt += f" ({ops[1]} args)"
        elif ops:
            txt += " " + ", ".join(str(o) for o in ops)
        out.append((off, r.p - off, mn, ops, txt))
    return out
