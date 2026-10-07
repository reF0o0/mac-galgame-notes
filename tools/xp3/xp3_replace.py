#!/usr/bin/env python3
"""Replace one file inside a protected .xp3 with minimal changes.

Everything is appended at the end of the archive and one pointer is repointed,
so the bulk of the file is never touched.  That matters for KiriKiri: a full
"read index, rewrite entries in place, recompress index" rebuild is easy to get
wrong (get an offset or an `aldr` wrong and the engine just prints
`失敗。` and refuses to open the archive at all).

Steps for the entry you are replacing:

  1. re-encrypt the new body with the entry's own `aldr` (the CX filter is a
     self-inverse XOR keystream, so the same call that decrypted the old body
     encrypts the new one),
  2. append the ciphertext at EOF,
  3. patch that entry's size/offset fields in the index block,
  4. re-serialise that index block, append it at EOF, and repoint the single
     chain pointer that used to lead to it.

usage:
  xp3_replace.py <archive.xp3> <entry-index> <new-body-file> [options]

  --list              just list entries and exit
  --filter PATH       game's xp3filter.tjs (needed for protected archives)
  --no-encrypt        write the body as-is (archive is not CX protected)
  --dry-run           show what would happen, change nothing
  --backup            keep a .bak copy of the archive first

Only single-segment entries are supported; the tool refuses anything else
rather than silently producing a broken archive.
"""
import os
import shutil
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cxdec  # noqa: E402   (also pulls in the ECB table loader)

MAGIC = b"XP3\r\n \n\x1a\x8b\x67\x01"


def u64(buf, off):
    return struct.unpack_from("<q", buf, off)[0]


def chunks(data):
    """Walk the top-level sub-chunk list of an index block."""
    out, pos = [], 0
    while pos + 12 <= len(data):
        tag = bytes(data[pos:pos + 4])
        size = u64(data, pos + 4)
        if size < 0 or pos + 12 + size > len(data):
            break
        out.append({"tag": tag, "off": pos, "size": size, "body": pos + 12})
        pos += 12 + size
    return out


def read_blocks(path):
    """Return the chained index blocks, with the file offset of each pointer."""
    f = open(path, "rb")
    if f.read(11) != MAGIC:
        raise SystemExit("not an XP3 archive: %s" % path)
    pos, blocks = 11, []
    while True:
        f.seek(pos)
        ofs = u64(f.read(8), 0)
        if ofs <= 0 or ofs >= os.path.getsize(path):
            raise SystemExit("bad index offset %#x" % ofs)
        f.seek(ofs)
        flag = f.read(1)[0]
        method = flag & 0x07
        if method == 1:
            csize, rsize = u64(f.read(8), 0), u64(f.read(8), 0)
            data = bytearray(zlib.decompress(f.read(csize)))
            assert len(data) == rsize, (len(data), rsize)
        elif method == 0:
            rsize = u64(f.read(8), 0)
            data = bytearray(f.read(rsize))
        else:
            raise SystemExit("unknown index encode method %d" % method)
        blocks.append({"ptr_pos": pos, "ofs": ofs, "flag": flag,
                       "data": data, "after": f.tell()})
        if not flag & 0x80:
            break
        pos = blocks[-1]["after"]
    f.close()
    return blocks


def parse_entry(data, chunk):
    """Decode one `File` chunk into a dict we can edit and re-serialise."""
    body = data[chunk["body"]:chunk["body"] + chunk["size"]]
    subs = {c["tag"]: c for c in chunks(body)}
    info, segm = subs[b"info"], subs[b"segm"]
    io, so = info["body"], segm["body"]
    nlen = struct.unpack_from("<H", body, io + 20)[0]
    segs = []
    for i in range(segm["size"] // 28):
        b = so + i * 28
        segs.append({"flags": struct.unpack_from("<I", body, b)[0],
                     "start": u64(body, b + 4),
                     "orgsize": u64(body, b + 12),
                     "arcsize": u64(body, b + 20)})
    return {"chunk": chunk,
            "name": body[io + 22:io + 22 + nlen * 2].decode("utf-16-le", "replace"),
            "info_off": chunk["body"] + io,
            "segm_off": chunk["body"] + so,
            "orgsize": u64(body, io + 4),
            "arcsize": u64(body, io + 12),
            "segs": segs}


def list_entries(path):
    blocks = read_blocks(path)
    out = []
    for bi, b in enumerate(blocks):
        for c in chunks(b["data"]):
            if c["tag"] == b"File":
                out.append((bi, parse_entry(b["data"], c)))
    return blocks, out


def entry_aldr(archive, idx):
    import xp3tool
    with open(archive, "rb") as f:
        return xp3tool.load_index(f)[idx]["aldr"]


def replace_entry(archive, idx, blob, encrypt=True, backup=False, dry_run=False):
    """Swap entry `idx` of `archive` for `blob`. Returns a small report dict."""
    blocks, files = list_entries(archive)
    if idx < 0 or idx >= len(files):
        raise SystemExit("entry index out of range")
    bi, entry = files[idx]
    if len(entry["segs"]) != 1:
        raise SystemExit("entry %d has %d segments; only single-segment entries "
                         "are supported" % (idx, len(entry["segs"])))

    aldr = entry_aldr(archive, idx)
    payload = blob
    if encrypt and aldr:
        payload = bytearray(blob)
        cxdec.Cxdec().decode(aldr, payload)
        payload = bytes(payload)

    old_start = entry["segs"][0]["start"]
    new_start = os.path.getsize(archive)
    report = {"idx": idx, "name": entry["name"], "aldr": aldr,
              "old_size": entry["orgsize"], "old_start": old_start,
              "new_size": len(blob), "new_start": new_start,
              "block": bi, "encrypted": bool(encrypt and aldr)}
    if dry_run:
        return report
    if backup:
        shutil.copy2(archive, archive + ".bak")

    data = blocks[bi]["data"]
    struct.pack_into("<q", data, entry["info_off"] + 4, len(blob))
    struct.pack_into("<q", data, entry["info_off"] + 12, len(blob))
    b = entry["segm_off"]
    struct.pack_into("<I", data, b, entry["segs"][0]["flags"] & ~0x07)
    struct.pack_into("<q", data, b + 4, new_start)
    struct.pack_into("<q", data, b + 12, len(blob))
    struct.pack_into("<q", data, b + 20, len(blob))

    with open(archive, "ab") as g:
        g.write(payload)
        comp = zlib.compress(bytes(data), 9)
        new_index_off = g.tell()
        g.write(bytes([0x01]))                      # zlib, no next block
        g.write(struct.pack("<q", len(comp)))
        g.write(struct.pack("<q", len(data)))
        g.write(comp)

    # repoint whichever pointer used to lead to this block
    ptr_pos = blocks[bi - 1]["after"] if bi else blocks[0]["ptr_pos"]
    with open(archive, "r+b") as g:
        g.seek(ptr_pos)
        g.write(struct.pack("<q", new_index_off))
    report.update({"new_index_off": new_index_off, "ptr_pos": ptr_pos})
    return report


def main():
    argv = sys.argv[1:]
    opts = {"filter": None, "encrypt": True, "dry_run": False, "backup": False}
    for flag, key in (("--filter", "filter"),):
        if flag in argv:
            i = argv.index(flag)
            opts[key] = argv[i + 1]
            del argv[i:i + 2]
    for flag, key in (("--no-encrypt", "encrypt"), ("--dry-run", "dry_run"),
                      ("--backup", "backup")):
        if flag in argv:
            argv.remove(flag)
            opts[key] = not opts[key] if key == "encrypt" else True
    if opts["filter"]:
        os.environ["XP3FILTER_TJS"] = opts["filter"]

    if not argv or "--list" in argv:
        if not argv:
            raise SystemExit(__doc__)
        archive = argv[0] if argv[0] != "--list" else argv[1]
        _, files = list_entries(archive)
        for i, (_, e) in enumerate(files):
            print("[%3d] %-42s org=%-11d start=%#x aldr=%#x"
                  % (i, e["name"][:42], e["orgsize"], e["segs"][0]["start"],
                     0))
        return
    if len(argv) != 3:
        raise SystemExit(__doc__)

    archive, idx, body_path = argv[0], int(argv[1]), argv[2]
    blob = open(body_path, "rb").read()
    rep = replace_entry(archive, idx, blob, encrypt=opts["encrypt"],
                        backup=opts["backup"], dry_run=opts["dry_run"])
    print("entry %d %r\n  %d bytes @ %#x  ->  %d bytes @ %#x   aldr=%#x%s"
          % (rep["idx"], rep["name"], rep["old_size"], rep["old_start"],
             rep["new_size"], rep["new_start"], rep["aldr"],
             "" if rep["encrypted"] else "  (written as plaintext)"))
    if opts["dry_run"]:
        print("dry run, nothing written")
        return
    print("new index block at %#x, repointed %#x"
          % (rep["new_index_off"], rep["ptr_pos"]))
    print("run tools/verify.py to confirm the entry reads back correctly")


if __name__ == "__main__":
    main()
