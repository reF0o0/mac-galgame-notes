#!/usr/bin/env python3
"""Read an .xp3 back the way the engine does and report what is really in it.

For every entry: size, MD5 of the *decrypted* body, and a guess at the payload
type from its first bytes.  Use this after any write-back tool -- it catches the
two mistakes that are otherwise invisible until you launch the game:

  * the body was written without re-encrypting it, so the engine decrypts it a
    second time and gets noise;
  * the index no longer points at the body you think it does.

usage:
  verify.py <archive.xp3> [--filter PATH] [--entry N]
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cxdec    # noqa: E402
import xp3tool  # noqa: E402

SIGS = [
    (b"\x4d\x5a", "PE/DLL"),
    (b"\x30\x26\xb2\x75", "ASF (wmv/wma)"),
    (b"RIFF", "RIFF (avi/wav)"),
    (b"\x89PNG", "PNG"),
    (b"ftyp", "MP4"),
    (b"OggS", "Ogg"),
    (b"BGM", "KiriKiri audio"),
]


def sniff(buf):
    for sig, name in SIGS:
        if buf.startswith(sig) or (name == "MP4" and buf[4:8] == sig):
            return name
    return "?"


def main():
    argv = sys.argv[1:]
    only = None
    if "--filter" in argv:
        i = argv.index("--filter")
        os.environ["XP3FILTER_TJS"] = argv[i + 1]
        del argv[i:i + 2]
    if "--entry" in argv:
        i = argv.index("--entry")
        only = int(argv[i + 1])
        del argv[i:i + 2]
    if len(argv) != 1:
        raise SystemExit(__doc__)

    archive = argv[0]
    c = cxdec.Cxdec()
    with open(archive, "rb") as f:
        entries = xp3tool.load_index(f)
        for i, e in enumerate(entries):
            if only is not None and i != only:
                continue
            body = bytearray(xp3tool.read_entry(f, e))
            if e["aldr"]:
                c.decode(e["aldr"], body)
            print("[%3d] %-42s %-11d %-14s aldr=%#010x %s"
                  % (i, e["name"][:42], len(body), sniff(bytes(body[:8])),
                     e["aldr"], hashlib.md5(body).hexdigest()))


if __name__ == "__main__":
    main()
