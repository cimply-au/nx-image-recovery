
## Summary

| | |
|---|---|
| **Reads** | Files in `input` (read-only) |
| **Writes** | New files in `output` only: one folder per X-ray, PNG + TIFF, `_overview.png`, `_index.csv` |
| **Never** | Deletes, renames, moves or edits an existing file. Overwrites an image already in `output`. Touches NX, its database, services or settings. Changes the registry or needs admin. Runs other programs from the Python script. |
| **Network** | Only the one-off `pip install` of numpy and pillow, and only if they're missing |

## Recover-NX-Images.bat

**Step 1: find Python.** Checks for `py`, then `python`. Doesn't change anything. If neither is found it stops and says where to get Python.

**Step 2: check for numpy and pillow.** Tries to import them. If they're already there, nothing happens. If not, runs `pip install --user numpy pillow`, which downloads them from PyPI into the current user's Python. No admin needed. This is the only part that uses the internet.

**Step 3: run the converter.** Creates `input` and `output` next to the .bat if they don't exist, then runs `nx_recover.py`. Anything typed after the .bat name (e.g. `--from 2026-10-21`) is passed straight through.

## nx_recover.py

**Section 1: imports.** Standard library plus numpy (pixel maths) and pillow (writing PNG/TIFF). Nothing for networking or launching processes. `hashlib` is only used to make a short ID for file names.

**Section 2: file name pattern.** Recognises NX cache names like:

```
1.3.51...<32 hex>-1.3.51....cached.normal.primary-3.2229037
```

and pulls out the X-ray ID (the hex part), full-size vs small copy, and the save version (`primary-N`). Only used for grouping and naming. Nothing gets renamed.

**Section 3: read one cache file.** Opens the file read-only and checks that:

- the first 4 bytes say the header is 4096 bytes
- the header text says the type is `DCImage`
- width, height and bit depth are present
- the file is long enough to hold the whole image

If any check fails the file is skipped with a reason. Nothing is repaired or written back.

**Section 4: make it viewable.** NX stores bone as low values, the opposite of how X-rays are viewed, so the greyscale is flipped. Contrast is set from the body area, ignoring the flat background. All in memory, no file access.

**Section 5: options and folders.** Defaults to the `input` and `output` folders next to the script. Optional: a different folder, `--from`/`--to`, `--all-sizes`, `--no-tiff`, `--no-invert`, `--version`.

**Section 6: folder checks.**

- Creates the default `input` folder if it's missing.
- Refuses to run if input and output are the same folder or one is inside the other.
- Warns if the input path looks like the live ImageCache.
- Stops with a message if `input` is empty.

**Section 7: scan and choose files.** Lists the files in `input` (ignoring hidden files and Windows' `desktop.ini`/`Thumbs.db`) and reads their modified dates. Applies the date filter. Where NX kept a full-size and a small copy of the same image, uses the full-size one. Files that have been renamed are still tried.

**Section 8: convert and save.** The only place images get written. Makes one folder per X-ray inside `output`. Each file name ends in a short ID taken from the image's unique ID, so two different images can't end up with the same name. If an image is already in `output` from an earlier run it's listed as `DONE` and skipped. Otherwise a new `.png` and `_16bit.tif` are saved. Bad files are listed as `SKIP` and left alone.

**Section 9: overview and index.**

- `_overview.png`: thumbnails of every image in `output` (this run and earlier ones), labelled with date/time. Rebuilt each run.
- `_index.csv`: which output file came from which cache file. New rows are added to the end.

**Section 10: summary.** Prints how many images were new, already done or skipped.



always work on a copy of the cache files, on a PC other than the NX workstation.
