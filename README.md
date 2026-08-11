# cellimgs

Command line tools for high-content microscopy: convert vendor `.C01` files to
TIF, group single-plane TIFs into Z-stacks, make max projections, merge
channels, segment with Cellpose, count objects, and align two imaging passes.

Masks are written as LZW-compressed `uint16` label images, ready to load into
CellProfiler 4.

## Installation

There is no Java anywhere in this package: no JDK, no JVM, no
`python-javabridge`, no `python-bioformats`. A CUDA GPU is recommended for
`gen-masks` but not required.

### Requirements

* Python 3.10 or newer (tested on 3.10 and 3.12)
* A CUDA GPU for practical `gen-masks` throughput. Without one it falls back
  to CPU with a warning, which is usable but far slower.
* Everything else is installed for you: cellpose 4, torch, numpy, pandas,
  tifffile, click, tqdm.

### 1. Create an environment

Install into an isolated environment rather than your system Python. With
conda or mamba:

```bash
conda create -n imaging python=3.12
conda activate imaging
```

Or with the standard library:

```bash
python3 -m venv ~/venvs/imaging
source ~/venvs/imaging/bin/activate
```

### 2. Install the package

```bash
git clone https://github.com/SextonLab/cell-imgs.git
cd cell-imgs
pip install .
```

Use `-e` instead if you intend to edit the code; then your changes take effect
without reinstalling:

```bash
pip install -e .
```

### 3. GPU support

On Linux, `pip install .` pulls a CUDA-enabled torch by default, which is
usually what you want. Verify:

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

If that prints `False`, install the torch build matching your CUDA version
before anything else, then reinstall this package:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu130
```

`gen-masks` will still run without CUDA. It warns and uses the CPU.

### 4. First run downloads model weights

The first `gen-masks` invocation downloads the Cellpose-SAM weights
(about 1.2 GB) to `~/.cellpose/models/`. This happens once. Later runs load
from that cache, which takes a few seconds.

### Optional extras

Reading vendor formats other than `.C01` — CZI, ND2, LIF:

```bash
pip install ".[formats]"
```

Development tools and the test suite:

```bash
pip install -e ".[dev]"
pytest          # 75 tests, no GPU or model weights required
ruff check cellimgs tests
```

### Verifying the install

```bash
pip show cellimgs | head -3
```

Expect `Version: 1.0.0`. To confirm you are on the Cellpose 4 code rather than
an older checkout, check for a flag that only exists in this version:

```bash
gen-masks --help | grep -E "channel-axis|color|denoise"
```

Only `--channel-axis` should appear. If `--color` or `--denoise_model` show up,
an older version is still installed.

### Upgrading an existing checkout

```bash
cd cell-imgs
git pull
pip install -e .
```

**Reinstalling is required, not optional.** The console script names changed in
1.0.0 (`masker` removed, `align-images` added), and a stale install leaves
those entry points pointing at code that no longer exists.

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

* All TIF output is LZW compressed. See [Output format](#output-format).
* `stack-imgs` and `smashtif` now agree on one output name,
  `{well}_F{field:03d}_C{channel:02d}.tif`. Previously they disagreed
  (`A01_F001_C01.tif` versus `A01_001_01.tif`).
* Stacks keep their source dtype. They used to be written as float64,
  8x larger than necessary.
* `log.txt` is appended to rather than overwritten.

## Output format

Every TIF this package writes is **LZW compressed**: lossless, and read
natively by CellProfiler 4 and ImageJ. Label masks shrink about 27x — a
1996x1996 `uint16` mask goes from 8.0 MB to 0.29 MB, so a 384-well plate at
9 fields drops from roughly 27 GB of masks to about 1 GB. Raw images shrink
around 20%.

Masks are `uint16` label images with contiguous labels starting at 1.

## Performance

Measured on an RTX 4090 with Cellpose-SAM, reading and writing over a network
mount:

| Images | Size | Time per image |
| --- | --- | --- |
| CV8000 fields | 1996x1996 | 2.65 s |
| Cellomics ArrayScan | 1104x1104 | 0.81 s |

Add roughly 8 s of startup per invocation for imports and loading the model.
A 384-well plate at 9 fields per well is about 2.5 hours at 2000x2000.

Runs are resumable: images that already have a mask are skipped, so re-running
an interrupted command picks up where it stopped. The model is not loaded onto
the GPU at all if there is nothing left to do.

## Commands

| Command | Purpose |
| --- | --- |
| `gen-masks` | Cellpose segmentation to `uint16` label masks |
| `normal-params` | Write a normalization parameter JSON to edit |
| `convert-c01` | `.C01` (and other vendor formats) to TIF |
| `stack-imgs` | Single planes to 3D stacks |
| `max-proj` | 3D stacks to max projections |
| `smashtif` | Stack and project in one pass, no intermediate on disk |
| `cmerge` | Three single-channel TIFs to one RGB TIF |
| `get-imgcounts` | Per-image object counts to `counts.csv` |
| `get-wellcounts` | Aggregate `counts.csv` to per-well totals |
| `align-images` | Align a second imaging pass to a first |

Every command takes `--help`.

### Generate masks

```bash
gen-masks imgdir/ maskdir/ -c C01 --count --no_edge
```

Segments matching TIFs in `imgdir` and writes a label mask of the same name
into `maskdir`.

| Option | Meaning |
| --- | --- |
| `-d`, `--diam` | Cell diameter in pixels. `0` (default) disables rescaling. |
| `-c`, `--channel` | Filename fragment selecting a channel, e.g. `C01`, `d0`. Default `*` (all files). |
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

Set `-c` deliberately. The default matches every TIF in the directory, which on
a raw microscope export includes instrument calibration frames.

`normal-params -o/--output my_params.json` writes Cellpose's default
normalization parameters for you to edit and pass back via `--normalize`.

### Convert C01 to TIF

```bash
convert-c01 c01dir/ tifdir/
```

`.C01` is decoded in pure Python. `-p`/`--pattern` accepts a different input
glob (default `*.C01`), `-c`/`--channel` narrows it further, and `-r` overwrites
existing output. Any other extension is delegated to `bioio`, which needs the
`formats` extra.

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
| `-s`, `--scope` | Naming convention: `CV8000`, `CQ1`, `CX5`, `STICH`, `STACK`. |
| `-c`, `--channel` | Filename fragment selecting a channel. |
| `-b`, `--bulk` | Look one directory deeper for images. |
| `-r`, `--replace` | Overwrite existing output. |
| `-o`, `--on` | `stack-imgs` only: stack along `z` (default), `t` or `l`. |
| `-l`, `--on_loc` | `smashtif` only: group by stage location, not field. |

`max-proj` takes `-c`, `-r`, and `-a`/`--axis`. It projects along axis 0 by
default, matching what these tools write. Files that are not 3D are reported
and skipped rather than aborting the run.

`cmerge` takes only `-r`. Channels are paired by filename, so a missing channel
skips that image with a warning instead of silently merging the wrong files.

### Counts

```bash
get-imgcounts maskdir/                        # per-image counts.csv
get-wellcounts maskdir/counts.csv -s STACK    # aggregate to well_count.csv
```

Both accept `-o`/`--output` to redirect the output CSV; `get-imgcounts` also
takes `-c`/`--channel`.

Use the `-s` scope that matches the *mask* filenames, which are named after the
images they came from. Masks made from `smashtif`/`stack-imgs` output use
`STACK`; masks made directly from raw microscope files use `CV8000`, `CQ1` or
`CX5`.

### Align two passes

```bash
align-images /first/pass/dir /second/pass/dir --no_edge
```

Segments both passes, hill-climbs the second pass into alignment with the
first, writes `correction_results.csv`, and applies the offsets to produce
`outputs/aligned_images/`.

It accepts the `gen-masks` segmentation options `-d`, `-c`, `-m`, `-n`, `-f`,
`-p`, `-b`, `--normalize` and `--gpu`/`--no-gpu`. The output-shaping options
(`--count`, `--replace`, `--channel-axis`, `--min-size`, `--do-3d`,
`--anisotropy`) do not apply.

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

Scope names are case-insensitive, and `CV800` is accepted as an alias for
`CV8000`. `STICH` is spelled that way for backwards compatibility.

Filenames that do not match are counted and reported, not silently dropped.

## Logging

Each command appends its parameters and a timestamp to `log.txt` in the output
directory, so a directory keeps the history of how it was produced.
