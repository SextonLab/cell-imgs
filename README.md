# cellimgs

Command line tools for high-content microscopy: convert vendor `.C01` files to
TIF, group single-plane TIFs into Z-stacks, make max projections, merge
channels, segment with Cellpose, count objects, and align two imaging passes.

Masks are written as `uint16` label images, ready to load into CellProfiler.

## Installation

No JDK, no JVM, no `python-javabridge`, no `python-bioformats`. A CUDA GPU is
recommended for `gen-masks` but not required.

```bash
git clone git@github.com:SextonLab/cell-imgs.git
cd cell-imgs
pip install .
```

For development, and to run the tests:

```bash
pip install -e ".[dev]"
pytest
```

Reading vendor formats other than `.C01` (CZI, ND2, LIF) needs the optional
extra:

```bash
pip install ".[formats]"
```

### Requirements

* Python 3.10+
* Cellpose 4 (Cellpose-SAM). Installed automatically.
* CUDA is optional. `gen-masks` falls back to CPU with a warning.

## Upgrading from 0.4.x

**Cellpose 4 removed the entire v3 model zoo.** `cyto`, `cyto2`, `cyto3`,
`nuclei` and friends no longer exist; Cellpose-SAM replaces all of them. In
Cellpose 4 the old `model_type=` argument is accepted and then *ignored*, so
the previous version of this package silently produced CPSAM masks while
writing `cyto3` into the log file.

| Was | Now |
| --- | --- |
| `--model cyto3` | omit `--model` — CPSAM is the only built-in model. `--model` now takes a path or name of a **custom-trained** model, and rejects v3 zoo names rather than ignoring them. |
| `--color rg` | removed. Cellpose 4 takes arbitrary channel order; use `--channel-axis` for multi-channel input. |
| `--denoise_model` | removed. `cellpose.denoise.CellposeDenoiseModel` no longer exists. |
| `masker` (PyQt GUI) | removed. Use the GUI that ships with Cellpose. |
| `align_images` | renamed `align-images`; the old name still works. |

Masks made with Cellpose 3 are **not** reproducible under Cellpose 4. Keep a
pinned v3 environment if you need to re-run an old analysis exactly.

Other behaviour changes:

* `stack-imgs` and `smashtif` now agree on one output name,
  `{well}_F{field:03d}_C{channel:02d}.tif`. Previously they disagreed
  (`A01_F001_C01.tif` versus `A01_001_01.tif`).
* Stacks keep their source dtype. They used to be written as float64,
  8x larger than necessary.
* `log.txt` is appended to rather than overwritten.
* All TIF output is LZW compressed. See below.

## Output format

Every TIF this package writes is **LZW compressed**, which is lossless and
read natively by CellProfiler 4 and ImageJ. Label masks shrink about 28x
(8.0 MB to 0.29 MB for a 1996x1996 `uint16` mask), so a full plate of masks
goes from roughly 27 GB to under 1 GB. Raw images shrink around 20%.

Masks are `uint16` label images with contiguous labels starting at 1.

## Commands

### Generate masks

```bash
gen-masks imgdir/ maskdir/ --count --no_edge
```

Segments every TIF in `imgdir` and writes a `uint16` label mask of the same
name into `maskdir`. Images that already have a mask are skipped, and the model
is not loaded onto the GPU if there is nothing to do.

| Option | Meaning |
| --- | --- |
| `-d`, `--diam` | Cell diameter in pixels. `0` (default) disables rescaling. |
| `-c`, `--channel` | Filename fragment selecting a channel, e.g. `C01`, `d0`. |
| `-m`, `--model` | Path or name of a custom-trained model. Omit for Cellpose-SAM. |
| `-n`, `--no_edge` | Drop objects touching the image edge. |
| `-f`, `--flow` | Flow threshold. Default `0.4`. |
| `-p`, `--prob` | Cell probability threshold. Default `0.0`. |
| `-r`, `--replace` | Re-segment images that already have masks. |
| `-b`, `--batch` | Cellpose batch size. Default `8`. |
| `--count` | Write `counts.csv` of per-image object counts. |
| `--normalize` | Path to a normalize parameter JSON. See `normal-params`. |
| `--channel-axis` | Axis holding channels, for multi-channel input. |
| `--min-size` | Discard objects below this pixel area. Default `15`. |
| `--do-3d` | Segment a 3D stack volumetrically. |
| `--anisotropy` | Z:XY sampling ratio, used with `--do-3d`. |
| `--gpu` / `--no-gpu` | Use CUDA if available. Default `--gpu`. |

Run `normal-params` to write a `normalize_default.json` you can edit and pass
back via `--normalize`.

### Convert C01 to TIF

```bash
convert-c01 c01dir/ tifdir/
```

`.C01` is decoded in pure Python. `--pattern` accepts a different input glob,
and any other extension is delegated to `bioio` if the `formats` extra is
installed.

### Stack, project, merge

```bash
stack-imgs src/ dest/ -s CV8000        # single planes -> 3D stacks
max-proj stackdir/ mipdir/             # 3D stacks -> max projections
smashtif src/ dest/ -s CV8000          # both in one pass, no intermediate
cmerge indir/ outdir/ C01 C02 C03      # 3 single-channel TIFs -> one RGB TIF
```

`stack-imgs` and `smashtif` share these options:

| Option | Meaning |
| --- | --- |
| `-s`, `--scope` | Naming convention: `CV8000`, `CQ1`, `STICH`, `STACK`. |
| `-c`, `--channel` | Filename fragment selecting a channel. |
| `-b`, `--bulk` | Look one directory deeper for images. |
| `-r`, `--replace` | Overwrite existing output. |
| `-o`, `--on` | `stack-imgs` only: stack along `z`, `t` or `l`. |
| `-l`, `--on_loc` | `smashtif` only: group by stage location, not field. |

`max-proj` projects along axis 0 by default, matching what these tools write.
Pass `-a` to override. Files that are not 3D are reported and skipped rather
than aborting the run.

### Counts

```bash
get-imgcounts maskdir/                        # per-image counts.csv
get-wellcounts maskdir/counts.csv -s STACK    # aggregate to well_count.csv
```

Use the `-s` scope that matches the *mask* filenames. Masks made from
`smashtif`/`stack-imgs` output use `STACK`; masks made directly from raw
microscope files use `CV8000` or `CQ1`.

### Align two passes

```bash
align-images /first/pass/dir /second/pass/dir --no_edge
```

Segments both passes, hill-climbs the second pass into alignment with the
first, writes `correction_results.csv`, and applies the offsets to produce
`outputs/aligned_images/`. Takes the same segmentation options as `gen-masks`.

## Filename conventions

Every tool identifies images by parsing the filename. `cellimgs/metadata.py`
is the single source of truth:

| Scope | Example |
| --- | --- |
| `CV8000` | `plate1_A01_T0001F001L01A01Z01C01.tif` |
| `CQ1` | `W0001F0001T0001Z001C1.tif` (plate id from the parent folder) |
| `CX5` | `MFGTMP_260306160001_A01f00d0.C01` — Cellomics ArrayScan |
| `STICH` | `A01_F0001_T0001_Z0004_C01.tif` |
| `STACK` | `A01_F001_C01.tif` — this package's own output |

Filenames that do not match are counted and reported, not silently dropped.

## Logging

Each command appends its parameters and a timestamp to `log.txt` in the output
directory.
