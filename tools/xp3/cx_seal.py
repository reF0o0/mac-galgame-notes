#!/usr/bin/env python3
"""Measure an entry's CX keystream off the archive itself, then seal a body.

`cxdec.py` reproduces the engine's filter, but it needs the game's own
`xp3filter.tjs` (the 1024-entry ECB table).  Some protected archives ship
without that file -- ATRI is one -- and then the keystream has to be measured
instead of computed:

  * k1 = the key that turns the first 16 bytes into the ASF Header GUID,
  * k2 = the key that turns the object at `hsize` into the DataObject GUID,
  * the seam = the one offset where k1 hands over to k2.

In every archive seen so far the keystream really is *two constant runs*
(`cxdec`'s two chunks, minus the per-chunk exception bytes that never landed
inside the file).  `measure()` refuses anything else rather than producing a
body the engine would decrypt into garbage.

Do not assume `(aldr & 0x134) + 0x736` (the 千恋＊万花 boundary): in ATRI's
vol1.xp3 it holds for 4 of the 5 movie entries and is wrong for the fifth.
Measure, then compare.

The filter is a self-inverse XOR keystream, so sealing = running the same
keystream over the new plaintext, and it is position stable: a body of any
length can be sealed with keys measured from the original.

usage:
  cx_seal.py probe <archive.xp3> <entry-index> [<original-plain-file>]
  cx_seal.py decrypt <archive.xp3> <entry-index> <out-plain-file> --anchor OFFSET:HEX
  cx_seal.py seal  <archive.xp3> <entry-index> <new-plain-file> <out-cipher-file>
                      [<original-plain-file>]

`seal` measures against the *original* plaintext (pass it, or the new one is
used -- that only works if the seam sits inside the part you did not rewrite)
and prints the exact (k1, seam, k2) it used.  Feed the result to
`xp3_replace.py --no-encrypt`.

No plaintext at all?  k1 and k2 still fall out of the two ASF GUIDs, and the
seam comes from `--anchor OFFSET:HEX` -- bytes you know the plaintext has at
that offset, typically a structure body copied off a sibling file from the same
release (ATRI's five movies share one header object GUID: it sits at 0x37f in
the odd one out and 0x266 in the other four, and it is what pins that entry's
seam to 0x38d).  One anchor straddling the switch is enough; the tool refuses
anchors that are inconsistent with k1/k2 rather than guessing.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from xp3tool import load_index  # noqa: E402

ASF_HEADER = bytes.fromhex("3026b2758e66cf11a6d900aa0062ce6c")
ASF_DATA_OBJECT = bytes.fromhex("3626b2758e66cf11a6d900aa0062ce6c")


def read_entry_raw(f, entries, idx):
    e = entries[idx]
    if len(e["segs"]) != 1:
        raise SystemExit("entry %d has %d segments; only single ones supported"
                         % (idx, len(e["segs"])))
    s = e["segs"][0]
    f.seek(s["start"])
    return e, bytearray(f.read(s["arcsize"]))


def key_at(raw, off, guid):
    """Key k with raw[off:off+16] ^ k == guid, or None."""
    if off + 16 > len(raw):
        return None
    k = raw[off] ^ guid[0]
    return k if all(raw[off + i] ^ k == guid[i] for i in range(16)) else None


def keys(raw):
    """(k1, k2, hsize) from the two known ASF GUIDs -- ciphertext only."""
    k1 = key_at(raw, 0, ASF_HEADER)
    if k1 is None:
        raise SystemExit("first 16 bytes are not a constant-key ASF Header GUID")
    hsize = struct.unpack_from("<Q", bytes(b ^ k1 for b in raw[16:24]), 0)[0]
    k2 = key_at(raw, hsize, ASF_DATA_OBJECT)
    if k2 is None:
        raise SystemExit("no DataObject GUID at hsize=%d" % hsize)
    return k1, k2, hsize


def seam_from_anchors(raw, k1, k2, anchors):
    """Narrow the seam down with known plaintext.  Returns (lo, hi) with the
    seam in (lo, hi]: every anchor byte below it must decode with k1, every
    one at or above it with k2."""
    lo, hi = 0, len(raw)
    for off, block in anchors:
        if off + len(block) > len(raw):
            raise SystemExit("anchor at %#x runs past the end of the entry" % off)
        for j, b in enumerate(block):
            i = off + j
            k = raw[i] ^ b
            if k == k1:
                lo = max(lo, i + 1)
            elif k == k2:
                hi = min(hi, i)
            else:
                raise SystemExit(
                    "anchor byte at %#x needs key %#04x, which is neither "
                    "k1=%#04x nor k2=%#04x" % (i, k, k1, k2))
    if hi < lo:
        raise SystemExit("anchors are inconsistent: seam must be > %#x and <= %#x"
                         % (lo - 1, hi))
    return lo, hi


def measure(raw, plain=None, anchors=()):
    """Return (k1, seam, k2, hsize).  With `plain`, the seam is read straight
    off C^P; without it, only k1/k2 are measured and the seam is None."""
    k1, k2, hsize = keys(raw)
    seam = None
    if plain is not None:
        if len(plain) != len(raw):
            raise SystemExit("plain is %d bytes, entry is %d"
                             % (len(plain), len(raw)))
        diff = (int.from_bytes(raw, "big") ^ int.from_bytes(plain, "big")
                ).to_bytes(len(raw), "big")
        seam = 0
        while diff[seam] == k1:
            seam += 1
        expect = bytes([k1]) * seam + bytes([k2]) * (len(raw) - seam)
        if diff != expect:
            n = sum(1 for i in range(len(diff)) if diff[i] != expect[i])
            raise SystemExit("keystream is NOT two constant runs: %d bytes differ"
                             % n)
    elif anchors:
        lo, hi = seam_from_anchors(raw, k1, k2, anchors)
        if lo != hi:
            raise SystemExit("anchors only narrow the seam to (%#x, %#x]; "
                             "add an anchor that crosses the switch"
                             % (lo - 1, hi))
        seam = lo
    return k1, seam, k2, hsize


def seal(k1, seam, k2, plain):
    body = bytearray(plain)
    for i in range(len(body)):
        body[i] ^= k1 if i < seam else k2
    return body


def main():
    argv = sys.argv[1:]
    anchors = []
    while "--anchor" in argv:
        i = argv.index("--anchor")
        off, _, hexs = argv[i + 1].partition(":")
        anchors.append((int(off, 0), bytes.fromhex(hexs)))
        del argv[i:i + 2]
    if len(argv) < 3:
        raise SystemExit(__doc__)
    mode, arc, idx = argv[0], argv[1], int(argv[2])
    f = open(arc, "rb")
    entries = load_index(f)
    e, raw = read_entry_raw(f, entries, idx)
    print("archive=%s entry=%d aldr=%#x seg_start=%#x size=%d"
          % (os.path.basename(arc), idx, e["aldr"], e["segs"][0]["start"],
             len(raw)))
    if mode == "probe":
        plain = None
        if len(argv) > 3:
            plain = bytearray(open(argv[3], "rb").read())
        if anchors:
            k1, k2, hsize = keys(raw)
            lo, hi = seam_from_anchors(raw, k1, k2, anchors)
            seam = lo if lo == hi else None
            print("anchors narrow the seam to (%#x, %s]%s"
                  % (lo - 1, ("%#x" % hi) if hi < len(raw) else "end of entry",
                     " -> %#x" % lo if lo == hi else
                     " -- add an anchor that crosses the switch"))
        else:
            k1, seam, k2, hsize = measure(raw, plain)
        print("k1=%#04x  seam=%s  k2=%#04x  hsize=%d(%#x)"
              % (k1, ("%#x" % seam) if seam is not None else "?", k2, hsize, hsize))
    elif mode == "decrypt":
        # self-inverse: the same keystream takes the ciphertext back to plain
        if not anchors:
            raise SystemExit("decrypt needs --anchor: the seam has to come from "
                             "known plaintext, and the plaintext is what we are "
                             "trying to build")
        k1, k2, hsize = keys(raw)
        lo, hi = seam_from_anchors(raw, k1, k2, anchors)
        if lo != hi:
            raise SystemExit("anchors only narrow the seam to (%#x, %#x]"
                             % (lo - 1, hi))
        out = argv[3]
        body = seal(k1, lo, k2, raw)
        open(out, "wb").write(body)
        print("k1=%#04x seam=%#x k2=%#04x  -> %d bytes to %s"
              % (k1, lo, k2, len(body), out))
    elif mode == "seal":
        new_plain, out = argv[3], argv[4]
        ref = argv[5] if len(argv) > 5 else new_plain
        k1, seam, k2, hsize = measure(raw, bytearray(open(ref, "rb").read()))
        if seam is None:
            raise SystemExit("could not measure the seam")
        body = seal(k1, seam, k2, open(new_plain, "rb").read())
        open(out, "wb").write(body)
        print("sealed %d bytes -> %s (k1=%#04x up to %#x, k2=%#04x after)"
              % (len(body), out, k1, seam, k2))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
