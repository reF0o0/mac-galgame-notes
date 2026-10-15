#!/usr/bin/env python3
"""Verify a single-entry .xp3 swap end to end.

  1. the patched archive's index still parses and every entry other than the
     one you swapped still has byte-identical index fields,
  2. the swapped entry reads back through the archive, decrypts with the
     keystream measured from the pristine archive, and hashes to the file you
     meant to install.

That is the whole claim a swap makes.  "The game starts" is a weaker check:
`xp3_replace.py` repoints one pointer, so a mistake there is invisible until
something reads the entry.

usage: verify_swap.py <patched.xp3> <pristine.xp3> <entry-index> <expected-file>
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cx_seal  # noqa: E402
import xp3tool  # noqa: E402


def fields(e):
    """Everything in the index entry that decides what the engine reads."""
    return (e["name"], e["hash"], e["flags"], e["orgsize"], e["arcsize"],
            e["aldr"], tuple((s["flags"], s["start"], s["orgsize"], s["arcsize"])
                             for s in e["segs"]))


def main():
    patched, pristine, idx, expected = (sys.argv[1], sys.argv[2],
                                       int(sys.argv[3]), sys.argv[4])
    blob = open(expected, "rb").read()

    # Keys come from the pristine archive, so anything below is a real check
    # and not a tautology: the old ciphertext alone fixes k1/k2 (the two ASF
    # GUIDs), and the seam is the one offset at which the new ciphertext and
    # the file we meant to install differ by exactly the other key.
    with open(pristine, "rb") as b:
        pb = xp3tool.load_index(b)
        old = bytearray(cx_seal.read_entry_raw(b, pb, idx)[1])
    k1p, _, k2p, _ = cx_seal.measure(old)

    with open(patched, "rb") as a:
        pa = xp3tool.load_index(a)
        print("entries: patched=%d pristine=%d" % (len(pa), len(pb)))
        assert len(pa) == len(pb)
        diffs = [i for i in range(len(pa)) if fields(pa[i]) != fields(pb[i])]
        print("entries whose index fields changed: %s" % diffs)
        assert diffs == [idx], "expected only entry %d to change" % idx
        raw = bytearray(xp3tool.read_entry(a, pa[idx]))
    if len(blob) != len(raw):
        raise SystemExit("entry is %d bytes but %s is %d"
                         % (len(raw), os.path.basename(expected), len(blob)))

    k1, seam, k2, hsize = cx_seal.measure(raw, bytearray(blob))
    print("keystream: k1=%#04x seam=%#x k2=%#04x hsize=%d"
          % (k1, seam, k2, hsize))
    assert (k1, k2) == (k1p, k2p), \
        "patched entry uses keys %#04x/%#04x, pristine uses %#04x/%#04x" % (
            k1, k2, k1p, k2p)
    assert bytes(raw) != bytes(old), "entry %d still holds the old body" % idx
    for i in range(len(raw)):
        raw[i] ^= k1 if i < seam else k2

    h = hashlib.sha256(bytes(raw)).hexdigest()
    w = hashlib.sha256(blob).hexdigest()
    print("decrypted sha256 %s" % h)
    print("expected  sha256 %s" % w)
    assert h == w, "decrypted entry does not match the file we installed"
    print("OK: entry %d reads back as %s" % (idx, os.path.basename(expected)))


if __name__ == "__main__":
    main()
