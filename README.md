# NX Image Recovery

Gets X-ray images back out of an Agfa NX workstation's image cache.

Useful when exams have dropped off the NX worklist (auto-purged or deleted) but the image data is still sitting in:

```
~\Agfa\Healthcare\NX\DataFiles\ImageCache
```

The cache files aren't DICOM. They're Agfa's RAW or own format: a 4 KB text header followed by raw 16-bit pixel data, with no patient details. This tool reads them, converts each one to a PNG (for viewing) and a 16-bit TIFF (full bit depth), puts them in one folder per X-ray and builds a contact sheet so you can match images to patients.

## Download

Get the latest zip from [Releases](../../releases) and unzip it anywhere on a PC that **isn't** the NX workstation.

## Requirements

- Windows PC with Python 3.8 or newer. Get it from [python.org](https://www.python.org/downloads/) and tick **Add to PATH**. The default install is per-user and doesn't need admin.
- numpy and pillow. The launcher installs these on first run if they're missing.

## Usage

1. On the NX PC, open the ImageCache folder, sort by **Date modified** and copy the files for the dates you need onto a USB stick. Don't rename, move or delete anything in ImageCache.
2. On the other PC, paste the files loose into the `input` folder.
3. Double-click `Recover-NX-Images.bat`.
4. Open `output`. Start with `_overview.png`.

You can drop more files into `input` and run it again whenever you like. Anything already in `output` is skipped.

### Options

Run from a command prompt in the tool folder:

| Command | What it does |
|---|---|
| `Recover-NX-Images.bat --from 2026-10-21 --to 2026-10-22` | Only files modified between those dates |
| `Recover-NX-Images.bat --no-tiff` | PNG only, smaller output |
| `Recover-NX-Images.bat --all-sizes` | Also keep NX's reduced-size copies |
| `Recover-NX-Images.bat --no-invert` | Use if images come out as negatives |

Or call the script directly: `python nx_recover.py [input] [-o output] [options]`

## Output

```
output\
  2026-10-21_1043_xray-8953a039\
    2026-10-21_104326_v3_908f0a.png         viewable, auto contrast
    2026-10-21_104326_v3_908f0a_16bit.tif   full bit depth
  _overview.png                             thumbnails of everything, with date/time
  _index.csv                                which output came from which cache file
```

- One folder per X-ray shot, named by date/time and the NX image ID.
- More than one image in a folder means NX saved the same shot more than once (e.g. after re-processing). The earliest time is closest to when it was taken.
- `_small` in a name means only NX's reduced-size copy was available.

## NOTES
- Files in `input` are only ever opened for reading.
- New files are only written inside `output`. Nothing is ever deleted, renamed, moved or overwritten.
- No network access, apart from the one-off `pip install` of numpy and pillow.
- No admin rights, no registry changes, and it never touches NX itself.

[HOW-IT-WORKS.md](HOW-IT-WORKS.md) goes through the code section by section and shows how to check all of this yourself.

## Limitations

- **No patient details.** The cache files don't contain a patient name or ID, so images have to be matched up by date/time, L/R markers and whatever exam records or JPEG exports exist.
- **Contrast is automatic.** It's a reasonable approximation, not Agfa's own image processing. 
- **Not DICOM, not back into NX.** Output is PNG/TIFF. Re-linking exams into the NX database is a job for Agfa.

## Doing it by hand

If you'd rather not use Python, ImageJ/Fiji can open these with **File > Import > Raw**:

- Open the file in Notepad++ or a hex editor and read `__Columns` (width) and `__Rows` (height) from the text at the top.
- Image type 16-bit unsigned, offset 4096 bytes, 1 image, little-endian.
- Typical sizes are 2536 x 3048 or 3048 x 2536 (full) and 1664 x 2000 or 2000 x 1664 (small).
- Bone is stored dark, so invert it and then auto brightness/contrast.

Fine for one or two files. The script is quicker for anything more because it reads the size from each header itself.
