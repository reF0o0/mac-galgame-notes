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
  cx_seal.py seal  <archive.xp3> <entry-index> <new-plain-file> <out-cipher-file>
                      [<original-plain-file>]

`seal` measures against the *original* plaintext (pass it, or the new one is
used -- that only works if the seam sits inside the part you did not rewrite)
and prints the exact (k1, seam, k2) it used.  Feed the result to
`xp3_replace.py --no-encrypt`.
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


def measure(raw, plain=None):
    """Return (k1, seam, k2, hsize).  With `plain`, the seam is read straight
    off C^P; without it, only k1/k2 are measured and the seam is None."""
    k1 = key_at(raw, 0, ASF_HEADER)
    if k1 is None:
        raise SystemExit("first 16 bytes are not a constant-key ASF Header GUID")
    hsize = struct.unpack_from("<Q", bytes(b ^ k1 for b in raw[16:24]), 0)[0]
    k2 = key_at(raw, hsize, ASF_DATA_OBJECT)
    if k2 is None:
        raise SystemExit("no DataObject GUID at hsize=%d" % hsize)
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
    return k1, seam, k2, hsize


def seal(k1, seam, k2, plain):
    body = bytearray(plain)
    for i in range(len(body)):
        body[i] ^= k1 if i < seam else k2
    return body


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    mode, arc, idx = sys.argv[1], sys.argv[2], int(sys.argv[3])
    f = open(arc, "rb")
    entries = load_index(f)
    e, raw = read_entry_raw(f, entries, idx)
    print("archive=%s entry=%d aldr=%#x seg_start=%#x size=%d"
          % (os.path.basename(arc), idx, e["aldr"], e["segs"][0]["start"],
             len(raw)))
    if mode == "probe":
        plain = None
        if len(sys.argv) > 4:
            plain = bytearray(open(sys.argv[4], "rb").read())
        k1, seam, k2, hsize = measure(raw, plain)
        print("k1=%#04x  seam=%s  k2=%#04x  hsize=%d(%#x)"
              % (k1, ("%#x" % seam) if seam is not None else "?", k2, hsize, hsize))
    elif mode == "seal":
        new_plain, out = sys.argv[4], sys.argv[5]
        ref = sys.argv[6] if len(sys.argv) > 6 else new_plain
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
