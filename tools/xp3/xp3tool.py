#!/usr/bin/env python3
"""Minimal XP3 reader/writer helper (matches krkrz base/XP3Archive.cpp).

usage:
  xp3tool.py list <archive.xp3> [--min N] [--max N]
  xp3tool.py dump <archive.xp3> <index-in-list> <outfile>
"""
import os
import struct
import sys
import zlib

XP3_MAGIC = b"XP3\r\n \n\x1a\x8b\x67\x01"


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def i64(b, o):
    return struct.unpack_from("<q", b, o)[0]


def parse_subchunks(buf):
    out = {}
    pos = 0
    n = len(buf)
    while pos + 12 <= n:
        tag = buf[pos:pos + 4]
        size = i64(buf, pos + 4)
        body = buf[pos + 12:pos + 12 + size]
        if len(body) != size:
            break
        out.setdefault(tag.decode("latin1"), []).append(body)
        pos += 12 + size
    return out


def load_index(f):
    head = f.read(11)
    if head != XP3_MAGIC:
        raise SystemExit("not an xp3: %r" % head)
    entries = []
    # mirrors krkrz: read u64 pointer, seek to it, read the block, then the
    # stream keeps whatever position the block read left it at
    pos = 11
    loops = 0
    while True:
        loops += 1
        if loops > 64:
            raise SystemExit("too many index blocks")
        f.seek(pos)
        index_ofs = i64(f.read(8), 0)
        if index_ofs <= 0 or index_ofs >= os.path.getsize(f.name):
            raise SystemExit("bad index offset %#x" % index_ofs)
        f.seek(index_ofs)
        flag = f.read(1)[0]
        method = flag & 0x07
        if method == 1:
            csize = i64(f.read(8), 0)
            rsize = i64(f.read(8), 0)
            data = zlib.decompress(f.read(csize))
            assert len(data) == rsize, (len(data), rsize)
        elif method == 0:
            rsize = i64(f.read(8), 0)
            data = f.read(rsize)
        else:
            raise SystemExit("unknown index encode method %d" % method)
        pos = f.tell()

        p = 0
        while p + 12 <= len(data):
            tag = data[p:p + 4]
            size = i64(data, p + 4)
            if size < 0 or p + 12 + size > len(data):
                break
            if tag != b"File":
                p += 12 + size
                continue
            content = data[p + 12:p + 12 + size]
            subs = parse_subchunks(content)
            info = subs["info"][0]
            segm = subs["segm"][0]
            aldr = subs.get("adlr", [b"\0\0\0\0"])[0]
            name_len = u16(info, 20)
            name = info[22:22 + name_len * 2].decode("utf-16-le", "replace")
            segs = []
            for i in range(len(segm) // 28):
                b = i * 28
                segs.append({
                    "flags": u32(segm, b),
                    "start": i64(segm, b + 4),
                    "orgsize": i64(segm, b + 12),
                    "arcsize": i64(segm, b + 20),
                })
            entries.append({
                "name": name,
                "flags": u32(info, 0),
                "orgsize": i64(info, 4),
                "arcsize": i64(info, 12),
                "hash": info[16:20].hex() if False else None,
                "aldr": u32(aldr, 0),
                "segs": segs,
            })
            p += 12 + size
        if not (flag & 0x80):
            break
    return entries


def read_entry(f, e):
    out = bytearray()
    for s in e["segs"]:
        f.seek(s["start"])
        raw = f.read(s["arcsize"])
        if (s["flags"] & 0x07) == 1:
            raw = zlib.decompress(raw)
        assert len(raw) == s["orgsize"], (len(raw), s["orgsize"])
        out += raw
    return bytes(out)


def main():
    cmd = sys.argv[1]
    path = sys.argv[2]
    with open(path, "rb") as f:
        entries = load_index(f)
        if cmd == "list":
            lo = hi = None
            if "--min" in sys.argv:
                lo = int(sys.argv[sys.argv.index("--min") + 1])
            if "--max" in sys.argv:
                hi = int(sys.argv[sys.argv.index("--max") + 1])
            print("%s: %d entries, index_ofs=%#x" % (path, len(entries), 0))
            for i, e in enumerate(entries):
                if lo is not None and e["orgsize"] < lo:
                    continue
                if hi is not None and e["orgsize"] > hi:
                    continue
                print("  [%d] %-40s org=%-9d arc=%-9d flags=%#x segs=%d %s" % (
                    i, e["name"][:40], e["orgsize"], e["arcsize"], e["flags"],
                    len(e["segs"]),
                    ",".join("f=%#x s=%#x o=%d a=%d" % (s["flags"], s["start"],
                                                        s["orgsize"], s["arcsize"])
                             for s in e["segs"])))
        elif cmd == "dump":
            i = int(sys.argv[3])
            out = sys.argv[4]
            data = read_entry(f, entries[i])
            with open(out, "wb") as g:
                g.write(data)
            print("wrote %s (%d bytes)" % (out, len(data)))


if __name__ == "__main__":
    main()
