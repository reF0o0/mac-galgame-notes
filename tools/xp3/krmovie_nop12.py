#!/usr/bin/env python3
"""Patch krmovie.dll inside the game's patch.xp3 so movies render again.

The plugin decides between "draw the movie into an offscreen layer" and "hand it
to the OS media stack" with a bounds check; when the check says the movie is too
big it silently takes the path that leaves the window black.  NOPing the 12
bytes removes the comparison, so the movie always goes to layer mode.

  before: 85 C0 74 08 3B C8 0F 8D 92 00 00 00
          test eax,eax / je +8 / cmp ecx,eax / jge +0x92
  after:  90 90 90 90 90 90 90 90 90 90 90 90

The script finds the DLL by itself: it walks the archive, decrypts each entry and
looks for a PE image containing that exact 12-byte sequence.  It prints the file
offset it patched so you can check it against the notes.

usage:
  krmovie_nop12.py <patch.xp3> --filter <xp3filter.tjs> [--dry-run] [--backup]

Nothing is written unless the pattern is found exactly once.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cxdec        # noqa: E402
import xp3_replace  # noqa: E402
import xp3tool      # noqa: E402

SIGNATURE = bytes.fromhex("85c074083bc80f8d92000000")
PATCHED = b"\x90" * 12


def find_krmovie(archive):
    """Return (entry_index, offset, plaintext_bytes) or raise."""
    c = cxdec.Cxdec()
    hits = []
    with open(archive, "rb") as f:
        for i, e in enumerate(xp3tool.load_index(f)):
            body = bytearray(xp3tool.read_entry(f, e))
            if e["aldr"]:
                c.decode(e["aldr"], body)
            if not body.startswith(b"MZ"):
                continue
            off = bytes(body).find(SIGNATURE)
            if off >= 0:
                hits.append((i, off, bytes(body)))
    if not hits:
        raise SystemExit("no entry contains the 12-byte signature; already "
                         "patched, or a different game build")
    if len(hits) > 1:
        raise SystemExit("signature found in %d entries, refusing to guess"
                         % len(hits))
    return hits[0]


def main():
    argv = sys.argv[1:]
    opts = {"filter": None, "dry_run": False, "backup": False}
    if "--filter" in argv:
        i = argv.index("--filter")
        opts["filter"] = argv[i + 1]
        del argv[i:i + 2]
    for flag in ("--dry-run", "--backup"):
        if flag in argv:
            argv.remove(flag)
            opts[flag[2:].replace("-", "_")] = True
    if opts["filter"]:
        os.environ["XP3FILTER_TJS"] = opts["filter"]
    if len(argv) != 1:
        raise SystemExit(__doc__)

    archive = argv[0]
    idx, off, dll = find_krmovie(archive)
    print("krmovie.dll: entry %d, %d bytes, signature at file offset %#x"
          % (idx, len(dll), off))
    patched = bytearray(dll)
    patched[off:off + 12] = PATCHED
    print("  %s -> %s" % (SIGNATURE.hex(), PATCHED.hex()))
    rep = xp3_replace.replace_entry(archive, idx, bytes(patched),
                                    encrypt=True, backup=opts["backup"],
                                    dry_run=opts["dry_run"])
    if opts["dry_run"]:
        print("dry run, nothing written")
        return
    print("  wrote %d bytes @ %#x, new index block @ %#x"
          % (rep["new_size"], rep["new_start"], rep["new_index_off"]))
    print("Now fully quit the game and start it again -- KiriKiri opens and "
          "caches the .xp3 at startup, so a running instance keeps using the "
          "old file.")


if __name__ == "__main__":
    main()
