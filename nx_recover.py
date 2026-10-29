#!/usr/bin/env python3
"""
nx_recover.py - Recover viewable images from Agfa NX ImageCache files.

Copyright (c) 2026 cimply.

HOW TO USE
    1. Copy the cache files (from D:\\Agfa\\Healthcare\\NX\\DataFiles\\ImageCache)
       loose into the "input" folder next to this script.
    2. Double-click Recover-NX-Images.bat (or run: python nx_recover.py).
    3. Recovered images appear in the "output" folder, one subfolder per X-ray.
    Add more files to "input" and run again any time - images already in
    "output" are skipped, never duplicated or overwritten.

SAFETY IN ONE PARAGRAPH
    Files in "input" are only ever OPENED FOR READING. Nothing is deleted,
    renamed, moved or modified anywhere. The only files written are new files
    inside "output". No network access, no registry, no admin rights, no
    changes to NX. See HOW-IT-WORKS.md for a section-by-section walkthrough.
    Even so: work on a COPY of the cache files, on a PC other than the NX
    workstation.

Advanced usage:
    python nx_recover.py [input folder] [-o output folder]
                         [--from YYYY-MM-DD] [--to YYYY-MM-DD]
                         [--all-sizes] [--no-tiff] [--no-invert]

Requires: Python 3.8+, numpy, pillow   (pip install numpy pillow)
"""

# =============================================================================
# SECTION 1 - IMPORTS
# Only Python's standard library plus numpy (number crunching) and pillow
# (saving PNG/TIFF). Nothing here talks to the network or runs other programs.
# =============================================================================
import argparse          # reads the command-line options
import csv               # writes the _index.csv summary
import datetime as dt    # file dates for naming and the --from/--to filter
import hashlib           # short, stable ID per image for file names
import re                # pattern-matching file names
import struct            # decoding the two numbers at the start of each file
import sys               # exiting with a message
from collections import defaultdict
from pathlib import Path # file and folder paths

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Missing libraries. Run:  python -m pip install numpy pillow")

__version__ = "1.0.0"
TOOL_DIR = Path(__file__).resolve().parent   # the folder this script lives in

# Placeholder and Windows housekeeping files that are never images
IGNORE = {"desktop.ini", "thumbs.db"}


def input_files(folder):
    """Every file under the input folder, minus hidden/placeholder files."""
    return sorted(p for p in folder.rglob("*")
                  if p.is_file() and not p.name.startswith(".") and p.name.lower() not in IGNORE)


# =============================================================================
# SECTION 2 - FILE NAME PATTERN
# NX names cache files like:
#   <seriesUID>.<32 hex chars>-<imageUID>.cached.<normal|small>.primary-<N>.<n>
# This pattern pulls out the parts used to group files: which X-ray it is
# (the hex ID), full-size or small copy, and the save version (primary-N).
# It is only used to label and group files - it never changes them.
# =============================================================================
NAME_RE = re.compile(
    r"^(?P<a>[\d.]+)\.(?P<hex>[0-9a-fA-F]{32})-(?P<b>[\d.]+)"
    r"\.cached\.(?P<size>\w+)\.primary-(?P<ver>\d+)\."
)


# =============================================================================
# SECTION 3 - READ ONE CACHE FILE  (read-only)
# File layout (as observed on NX cache files):
#   bytes 0-3    header block size, always 4096
#   bytes 4-7    length of the text header
#   bytes 8..    text like "__Columns=2536;__Rows=3048;__BitsStored=15;..."
#   byte 4096..  the raw pixel values, 2 bytes each, row by row
# The file is read into memory with read_bytes() - a read-only operation.
# Every check below must pass or the file is skipped with a reason; nothing
# is ever "repaired" or written back.
# =============================================================================
def read_nx_image(path):
    """Return (pixels, bits_stored, header dict) or raise ValueError."""
    raw = path.read_bytes()                                  # READ ONLY
    if len(raw) < 8:
        raise ValueError("file too small")
    hdr_len, txt_len = struct.unpack_from("<II", raw, 0)
    if hdr_len != 4096 or not (0 < txt_len < hdr_len):
        raise ValueError("not an NX cache file (unexpected header)")
    text = raw[8:8 + txt_len].decode("ascii", "replace")
    meta = dict(kv.split("=", 1) for kv in text.split(";") if "=" in kv)
    if "DCImage" not in meta.get("__TypeName", ""):
        raise ValueError(f"not an image ({meta.get('__TypeName', 'unknown type')})")
    cols, rows = int(meta["__Columns"]), int(meta["__Rows"])
    alloc = int(meta.get("__BitsAllocated", 16))
    bits = int(meta.get("__BitsStored", alloc))
    if alloc != 16:
        raise ValueError(f"unsupported BitsAllocated={alloc}")
    need = hdr_len + rows * cols * 2
    if len(raw) < need:
        raise ValueError(f"truncated ({len(raw)} of {need} bytes)")
    px = np.frombuffer(raw, dtype="<u2", count=rows * cols, offset=hdr_len)
    px = px.reshape(rows, cols) & ((1 << bits) - 1)
    return px, bits, meta


# =============================================================================
# SECTION 4 - MAKE IT VIEWABLE  (in memory only)
# NX stores dense tissue (bone) as LOW numbers, the reverse of how X-rays are
# viewed, so the greyscale is inverted. Brightness/contrast is set
# automatically from the body area, ignoring the flat blank background.
# Returns two versions: an 8-bit image for viewing (PNG) and the untouched
# full-depth values, just inverted, for the TIFF.
# This is pure arithmetic on data already in memory - no file access.
# =============================================================================
def to_display(px, bits, invert=True):
    bg = np.percentile(px, 99.0)                 # level of the blank background
    anat = px[px < bg - 600]                     # everything darker = the animal
    if anat.size < 1000:
        anat = px
    lo, hi = np.percentile(anat, [0.5, 99.8])    # auto contrast range
    norm = np.clip((px.astype(np.float32) - lo) / max(hi - lo, 1.0), 0.0, 1.0)
    if invert:
        norm = 1.0 - norm
    img8 = (norm ** 1.1 * 255).astype(np.uint8)
    full = ((1 << bits) - 1 - px) if invert else px
    return img8, full.astype(np.uint16)


def parse_date(s):
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError("use YYYY-MM-DD")


def overview_label(png):
    """'2026-10-21_1043_xray-8953a039/2026-10-21_104326_v3.png' -> '21/10 10:43  8953a039  v3'"""
    xray_id = png.parent.name.split("_xray-")[-1][:12]
    m = re.match(r"\d{4}-(\d{2})-(\d{2})_(\d{2})(\d{2})\d{2}_(.*)", png.stem)
    if not m:
        return f"{xray_id}  {png.stem[:24]}"
    mo, d, h, mi, rest = m.groups()
    return f"{d}/{mo} {h}:{mi}  {xray_id}  {rest}"


def main():
    # =========================================================================
    # SECTION 5 - OPTIONS AND FOLDERS
    # By default the tool uses the "input" and "output" folders that sit next
    # to this script, so no options are needed. A different input/output
    # folder and a few extras can be given on the command line if wanted.
    # =========================================================================
    ap = argparse.ArgumentParser(description="Recover images from Agfa NX ImageCache files.")
    ap.add_argument("input", type=Path, nargs="?", default=TOOL_DIR / "input",
                    help="folder of COPIED cache files (default: the 'input' folder next to this script)")
    ap.add_argument("-o", "--output", type=Path, default=TOOL_DIR / "output",
                    help="where recovered images go (default: the 'output' folder next to this script)")
    ap.add_argument("--from", dest="date_from", type=parse_date, help="only files modified on/after this date")
    ap.add_argument("--to", dest="date_to", type=parse_date, help="only files modified on/before this date")
    ap.add_argument("--all-sizes", action="store_true", help="also convert 'small' copies when a full-size one exists")
    ap.add_argument("--no-tiff", action="store_true", help="skip the 16-bit TIFF output")
    ap.add_argument("--no-invert", action="store_true", help="don't invert greyscale (if images come out negative)")
    ap.add_argument("--version", action="version", version=f"nx_recover {__version__}")
    args = ap.parse_args()

    # =========================================================================
    # SECTION 6 - FOLDER SAFETY CHECKS
    # - Creates the default "input"/"output" folders if they're missing (the
    #   only folders this step can create).
    # - Input and output must be different, and neither may sit inside the
    #   other, so originals and recovered images can never mix.
    # - Warns if the input looks like the live NX ImageCache.
    # - Stops politely if there's nothing in "input".
    # =========================================================================
    src, out = args.input.resolve(), args.output.resolve()
    if src == (TOOL_DIR / "input"):
        src.mkdir(exist_ok=True)
    if not src.is_dir():
        sys.exit(f"Input folder not found: {src}")
    if src == out or src in out.parents or out in src.parents:
        sys.exit("Input and output folders must be separate (neither inside the other).")
    if "imagecache" in str(src).lower():
        print("WARNING: this looks like the live NX ImageCache. Copy the files elsewhere first.\n")
    if not input_files(src):
        sys.exit(f"The input folder is empty. Copy the NX cache files into:\n  {src}")
    out.mkdir(parents=True, exist_ok=True)
    print(f"NX Image Recovery {__version__}\nInput:  {src}\nOutput: {out}\n")

    # =========================================================================
    # SECTION 7 - SCAN AND CHOOSE FILES  (read-only)
    # Lists every file in the input folder and reads its modified date.
    # Applies the --from/--to filter. NX often keeps a full-size and a small
    # copy of the same image; the full-size one is preferred.
    # Files that don't follow the NX naming (e.g. renamed by someone) are still
    # tried, each treated as its own image.
    # =========================================================================
    picked, skipped = {}, []
    for f in input_files(src):
        mtime = dt.datetime.fromtimestamp(f.stat().st_mtime)      # READ ONLY
        if args.date_from and mtime.date() < args.date_from:
            continue
        if args.date_to and mtime.date() > args.date_to:
            continue
        m = NAME_RE.match(f.name)
        if m:
            group, image_uid, size, ver = m["hex"].lower(), m["b"], m["size"], m["ver"]
        else:  # renamed file: treat as its own image, with a Windows-safe name
            slug = re.sub(r"[^A-Za-z0-9]+", "-", f.stem).strip("-")[:24] or "file"
            group, image_uid, size, ver = slug, f.name, "unknown", "0"
        key = (group, image_uid, ver) + ((size,) if args.all_sizes else ())
        if key in picked and picked[key]["size"] == "normal":
            continue
        picked[key] = dict(path=f, group=group, image_uid=image_uid, size=size, ver=ver, mtime=mtime)

    groups = defaultdict(list)
    for rec in picked.values():
        groups[rec["group"]].append(rec)

    # =========================================================================
    # SECTION 8 - CONVERT AND SAVE  (the only place images are written)
    # One subfolder per X-ray inside "output", named <date>_<time>_xray-<id>.
    # Each file name ends with a short ID made from the image's unique ID, so
    # two different images can never get the same name.
    # For each image: if it's already in "output" from an earlier run, it is
    # skipped (never overwritten or duplicated). Otherwise: read (Section 3),
    # convert in memory (Section 4), and save a NEW .png and _16bit.tif.
    # A file that fails any check is listed as SKIP and left alone.
    # =========================================================================
    index_rows, done, already = [], 0, 0
    for group, recs in sorted(groups.items(), key=lambda kv: min(r["mtime"] for r in kv[1])):
        recs.sort(key=lambda r: (r["mtime"], r["ver"]))
        label = group[:8] if NAME_RE.match(recs[0]["path"].name) else group
        folder = out / f"{recs[0]['mtime']:%Y-%m-%d_%H%M}_xray-{label}"
        for r in recs:
            stem = f"{r['mtime']:%Y-%m-%d_%H%M%S}_v{r['ver']}"
            if r["size"] not in ("normal", "unknown"):
                stem += f"_{r['size']}"
            stem += "_" + hashlib.sha1(r["image_uid"].encode()).hexdigest()[:6]
            if (folder / f"{stem}.png").exists():                   # never overwrite
                print(f"DONE  {folder.name}/{stem}  (already in output)")
                already += 1
                continue
            try:
                px, bits, meta = read_nx_image(r["path"])
            except Exception as e:
                skipped.append((r["path"].name, str(e)))
                continue
            folder.mkdir(exist_ok=True)
            img8, full = to_display(px, bits, invert=not args.no_invert)
            Image.fromarray(img8).save(folder / f"{stem}.png")         # WRITE (output only)
            if not args.no_tiff:
                Image.fromarray(full).save(folder / f"{stem}_16bit.tif")  # WRITE (output only)
            index_rows.append([folder.name, f"{stem}.png", r["mtime"].isoformat(sep=" ", timespec="seconds"),
                               px.shape[1], px.shape[0], bits, r["size"], r["ver"], r["path"].name])
            print(f"OK    {folder.name}/{stem}  ({px.shape[1]}x{px.shape[0]}, {r['size']})")
            done += 1

    for name, why in skipped:
        print(f"SKIP  {name[:70]}  - {why}")

    # =========================================================================
    # SECTION 9 - OVERVIEW SHEET AND INDEX  (written to "output" only)
    # _overview.png: thumbnails of EVERY recovered image in "output" (this run
    #                and earlier ones), labelled with date/time, for matching
    #                images to patients. Rebuilt each run.
    # _index.csv:    which output image came from which original cache file.
    #                New rows are added to the end; existing rows are kept.
    # =========================================================================
    pngs = sorted(p for p in out.glob("*_xray-*/*.png"))
    if pngs:
        cols, cw, ch = 4, 380, 400
        rows = (len(pngs) + cols - 1) // cols
        sheet = Image.new("L", (cols * cw, rows * ch), 30)
        draw = ImageDraw.Draw(sheet)
        try:
            font = ImageFont.load_default(size=16)
        except TypeError:
            font = ImageFont.load_default()
        for i, png in enumerate(pngs):
            with Image.open(png) as im:                                 # READ (output only)
                th = im.convert("L")
                th.thumbnail((360, 360))
            x, y = (i % cols) * cw + 10, (i // cols) * ch + 8
            draw.text((x, y), overview_label(png), fill=255, font=font)
            sheet.paste(th, (x, y + 26))
        sheet.save(out / "_overview.png")                              # WRITE (output only)
    if index_rows:
        index = out / "_index.csv"
        new_file = not index.exists()
        with open(index, "a", newline="") as fh:                       # WRITE (output only)
            w = csv.writer(fh)
            if new_file:
                w.writerow(["folder", "image", "file_modified", "width", "height",
                            "bits", "size", "version", "source_file"])
            w.writerows(index_rows)

    # =========================================================================
    # SECTION 10 - SUMMARY
    # =========================================================================
    print(f"\nDone: {done} new image(s), {already} already in output, {len(skipped)} skipped.")
    print(f"Output: {out}")


if __name__ == "__main__":
    main()
