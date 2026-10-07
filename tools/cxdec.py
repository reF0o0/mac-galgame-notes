#!/usr/bin/env python3
"""Faithful port of KiriKiri's own XP3 extraction filter ("cxdec"/xor128).

This is the filter the engine runs while reading a protected .xp3: it derives a
short XOR keystream from the archive's per-entry hash (`aldr`) and applies it to
each file body.  The stream is position dependent, so a prefix of a file can be
decrypted on its own -- handy when you only want to check a header.

The keystream is *self-inverse*: running the same function on ciphertext yields
plaintext, and running it on plaintext yields the ciphertext the engine expects
on disk.  `xp3_replace.py` relies on that when writing a modified file back.

The 1024-entry ECB table the xcode interpreter reads (`table_ECB` opcode, index
& 0x3ff) is not reproduced here: it is loaded at runtime from the game's own
`xp3filter.tjs`, i.e. from files you already have.  Point `--filter` (or
$XP3FILTER_TJS) at that file.

usage:
  cxdec.py key <hash> [<hash> ...]
  cxdec.py decrypt <archive.xp3> <entry-index> <out>
  cxdec.py xor <aldr-hex> <in> <out>          # self-inverse, works both ways
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
M32 = 0xFFFFFFFF

DEFAULT_FILTER = os.environ.get("XP3FILTER_TJS", "")


def load_ecb(path=None):
    path = path or os.environ.get("XP3FILTER_TJS") or DEFAULT_FILTER
    if not path:
        raise SystemExit(
            "need the game's xp3filter.tjs (pass --filter PATH or set $XP3FILTER_TJS)"
        )
    src = open(path, "r", encoding="utf-8", errors="replace").read()
    m = re.search(r"var\s+tempBlock\s*=\s*\[(.*?)\]\s*;", src, re.S)
    if not m:
        raise SystemExit("no `tempBlock` array found in %s" % path)
    vals = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{1,2})", m.group(1))]
    assert len(vals) == 4096, len(vals)
    return [
        vals[i] | (vals[i + 1] << 8) | (vals[i + 2] << 16) | (vals[i + 3] << 24)
        for i in range(0, 4096, 4)
    ]


ECB = None


def _ecb():
    global ECB
    if ECB is None:
        ECB = load_ecb()
    return ECB


class Cxdec:
    def __init__(self, ecb=None):
        self.ecb = _ecb() if ecb is None else ecb
        self.address_list = [None] * 128
        self.seed = 0

    # --- xcode_rand -------------------------------------------------------
    def xcode_rand(self):
        seed = self.seed
        self.seed = (1103515245 * seed + 12345) & M32
        # TJS keeps 64 bit intermediates; the final mask drops the high bits of
        # (seed << 16), so masking it first is equivalent.
        return (self.seed ^ ((seed << 16) & M32) ^ (seed >> 16)) & M32

    # --- xcode_execute ----------------------------------------------------
    def xcode_execute(self, xcode, arg):
        reg = 0
        reg2 = 0
        stack = []
        for i in range(1, len(xcode)):
            inst = xcode[i]
            op = inst[0]
            if op == 0:      # mov_val
                reg = inst[1] & M32
            elif op == 1:    # mov_reg
                reg2 = reg
            elif op == 2:    # not
                reg = (reg ^ M32) & M32
            elif op == 3:    # neg
                reg = (-reg) & M32
            elif op == 4:    # inc
                reg = (reg + 1) & M32
            elif op == 5:    # dec
                reg = (reg - 1) & M32
            elif op == 6:    # add_val
                reg = (reg + inst[1]) & M32
            elif op == 7:    # sub_val
                reg = (reg - inst[1]) & M32
            elif op == 8:    # xor_val
                reg = (reg ^ inst[1]) & M32
            elif op == 9:    # add_reg
                reg = (reg + reg2) & M32
            elif op == 10:   # sub_reg
                reg = (reg - reg2) & M32
            elif op == 11:   # push
                stack.append(reg2)
            elif op == 12:   # pop
                reg2 = stack.pop()
            elif op == 13:   # shr_reg  (reg is a positive 64 bit int -> logical)
                reg = (reg & M32) >> (reg2 & 0xF)
            elif op == 14:   # shl_reg
                reg = ((reg & M32) << (reg2 & 0xF)) & M32
            elif op == 15:   # imul_reg
                reg = (reg * reg2) & M32
            elif op == 16:   # load_arg
                reg = arg & M32
            elif op == 79:   # interlace
                r = reg & M32
                reg = (((r & 0xAAAAAAAA) >> 1) | ((r & 0x55555555) << 1)) & M32
            elif op == 80:   # table_ECB
                reg = self.ecb[reg & 0x3FF]
            else:
                raise RuntimeError("unknown op %r" % (op,))
        return reg & M32

    # --- xcode_push -------------------------------------------------------
    def _push(self, xcode, n, inst):
        xcode[0] += n
        if xcode[0] > 128:
            return False
        xcode.append(inst)
        return True

    def _first_stage(self, xcode):
        r = self.xcode_rand() % 3
        if r == 2:
            xcode[0] += 7
            if xcode[0] > 128:
                return False
            return self._push(xcode, 4, [0, self.ecb[self.xcode_rand() & 0x3FF]])
        if r == 1:
            xcode[0] += 1
            if xcode[0] > 128:
                return False
            return self._push(xcode, 4, [0, self.xcode_rand()])
        return self._push(xcode, 2, [16])

    def _stage0(self, xcode, stage):
        if stage == 1:
            return self._first_stage(xcode)
        stage -= 1
        if self.xcode_rand() & 1:
            if not self._stage1(xcode, stage):
                return False
        else:
            if not self._stage0(xcode, stage):
                return False

        r = self.xcode_rand() & 7
        if r == 5:
            return self._push(xcode, 2, [2])
        if r == 4:
            return self._push(xcode, 2, [3])
        if r == 2:
            return self._push(xcode, 1, [4])
        if r == 6:
            return self._push(xcode, 1, [5])
        if r == 7:
            return self._push(xcode, 21, [79])
        if r == 3:
            if xcode[0] + 1 > 128:
                xcode[0] += 1
                return False
            xcode[0] += 1
            return self._push(xcode, 4, [8, self.xcode_rand()])
        if r == 0:
            xcode[0] += 1
            if xcode[0] > 128:
                return False
            if self.xcode_rand() & 1:
                return self._push(xcode, 4, [6, self.xcode_rand()])
            return self._push(xcode, 4, [7, self.xcode_rand()])
        # r == 1
        return self._push(xcode, 13, [80])

    def _stage1(self, xcode, stage):
        if stage == 1:
            return self._first_stage(xcode)
        stage -= 1
        if not self._push(xcode, 1, [11]):
            return False
        if self.xcode_rand() & 1:
            if not self._stage1(xcode, stage):
                return False
        else:
            if not self._stage0(xcode, stage):
                return False
        if not self._push(xcode, 2, [1]):
            return False
        if self.xcode_rand() & 1:
            if not self._stage1(xcode, stage):
                return False
        else:
            if not self._stage0(xcode, stage):
                return False

        r = self.xcode_rand() % 6
        if r == 2:
            if not self._push(xcode, 2, [9]):
                return False
        elif r == 5:
            if not self._push(xcode, 2, [10]):
                return False
        elif r == 0:
            if not self._push(xcode, 2, [3]):
                return False
            if not self._push(xcode, 2, [9]):
                return False
        elif r == 3:
            if not self._push(xcode, 3, [15]):
                return False
        elif r == 1:
            if not self._push(xcode, 9, [14]):
                return False
        elif r == 4:
            if not self._push(xcode, 9, [13]):
                return False
        return self._push(xcode, 1, [12])

    def xcode_building(self, seed):
        self.seed = seed & M32
        xcode = None
        for stage in range(5, 0, -1):
            xcode = [9]  # xcode[0] = 5 + 4
            if self._stage1(xcode, stage) and xcode[0] + 5 + 1 <= 128:
                break
        return xcode

    # --- entry points -----------------------------------------------------
    def cxdec_execute_xcode(self, hash_):
        index = hash_ & 0x7F
        h = hash_ >> 7  # logical: hash_ is a positive tjs_uint32
        if self.address_list[index] is None:
            self.address_list[index] = self.xcode_building(index)
        xc = self.address_list[index]
        return (
            self.xcode_execute(xc, h),
            self.xcode_execute(xc, (h ^ M32) & M32),
        )

    def _decode_chunk(self, hash_, buf, offset, length):
        r0, r1 = self.cxdec_execute_xcode(hash_)
        key_8 = (r0 >> 8) & 0xFF
        key_9 = (r0 >> 16) & 0xFF
        key_10 = r0 & 0xFF
        key1 = r1 >> 16
        key2 = r1 & 0xFFFF
        if key1 == key2:
            key2 += 1
        if key_10 == 0:
            key_10 = 1
        if offset <= key2 < offset + length:
            buf[key2] ^= key_9
        if offset <= key1 < offset + length:
            buf[key1] ^= key_8
        for i in range(offset, offset + length):
            buf[i] ^= key_10

    def decode(self, hash_, buf):
        """Decrypt a whole (decompressed, in-archive) file buffer in place."""
        bondary = (hash_ & 0x134) + 0x736
        n = len(buf)
        if n <= bondary:
            self._decode_chunk(hash_, buf, 0, n)
            return buf
        self._decode_chunk(hash_, buf, 0, bondary)
        self._decode_chunk((hash_ >> 16) ^ hash_, buf, bondary, n - bondary)
        return buf


def main():
    argv = sys.argv[1:]
    if "--filter" in argv:
        i = argv.index("--filter")
        os.environ["XP3FILTER_TJS"] = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) < 3:
        raise SystemExit(__doc__)
    c = Cxdec()
    if argv[0] == "key":
        for a in argv[1:]:
            h = int(a, 0)
            h2 = (h >> 16) ^ h
            r = c.cxdec_execute_xcode(h)
            r2 = c.cxdec_execute_xcode(h2)
            print("hash=%#x bondary=%#x" % (h, (h & 0x134) + 0x736))
            print("  key_10=%#04x key_9=%#04x key_8=%#04x key1=%#06x key2=%#06x"
                  % (r[0] & 0xFF, (r[0] >> 16) & 0xFF, (r[0] >> 8) & 0xFF,
                     r[1] >> 16, r[1] & 0xFFFF))
            print("  hash2=%#x -> key_10=%#04x" % (h2, r2[0] & 0xFF))
    elif argv[0] == "decrypt":
        sys.path.insert(0, HERE)
        import xp3tool
        archive, idx, out = argv[1], int(argv[2]), argv[3]
        with open(archive, "rb") as f:
            e = xp3tool.load_index(f)[idx]
            data = bytearray(xp3tool.read_entry(f, e))
        c.decode(e["aldr"], data)
        with open(out, "wb") as g:
            g.write(data)
        print("wrote %s (%d bytes) aldr=%#x" % (out, len(data), e["aldr"]))
    elif argv[0] == "xor":
        # self-inverse: ciphertext in -> plaintext out, and vice versa
        h = int(argv[1], 0)
        data = bytearray(open(argv[2], "rb").read())
        c.decode(h, data)
        open(argv[3], "wb").write(data)
        print("wrote %s (%d bytes) aldr=%#x" % (argv[3], len(data), h))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
