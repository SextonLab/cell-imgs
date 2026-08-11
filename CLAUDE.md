# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`cellimgs` is a package of Click-based CLI tools for high-content microscopy: converting vendor `.C01` files to TIF, grouping single-plane TIFs into Z-stacks, max projections, RGB channel merging, Cellpose segmentation, object counting, and two-pass alignment. The consumer of the masks is CellProfiler, which is why every mask is written as a `uint16` label image.

Commands are declared in `pyproject.toml` under `[project.scripts]`. There is no CLI dispatcher module — adding a command means adding the Click function *and* an entry-point line, then reinstalling.

## Commands

```bash
pip install -e ".[dev]"     # re-run after touching [project.scripts]
pytest                      # 75 tests, no GPU or model weights needed
pytest tests/test_align.py::test_align_pair_recovers_a_known_shift   # single test
ruff check cellimgs tests
```

CI (`.github/workflows/ci.yml`) runs ruff, pytest on Python 3.10 and 3.12, and a `--help` smoke test of every console script.

## Architecture

**Filename metadata is the core abstraction.** These microscopes encode plate/well/field/timepoint/Z/channel in the filename, so nearly every tool parses filenames into a DataFrame, groups rows, and combines the matching images.

`cellimgs/metadata.py` is the single source of truth. This matters historically: the same regexes used to live in three places with different column names and different bugs, and the CQ1 pattern required a path separator while being applied to `os.path.basename()`, so it could never match — every CQ1 run silently produced no output. Do not reintroduce a local regex.

- `_PATTERNS` — one compiled regex per scope, matched against the extension-stripped basename. Never depend on directory separators.
- `build_table(files, scope)` → DataFrame with the columns in `COLUMNS`. Numeric columns are ints so they sort numerically.
- `iter_groups(df)` → `(well, field, channel)` tuples, computed **per well**. Global field lists produce empty groups on ragged plates.
- `stack_files(df, well, field, channel, on=)` → ordered paths for one stack.
- `stack_name(well, field, channel)` → `A01_F001_C01.tif`, the canonical output name shared by `stack-imgs` and `smashtif`.

Scopes are `CV8000`, `CQ1`, `CX5` (Cellomics ArrayScan), `STICH` and `STACK`. The `STACK` scope exists so this package's own output can be fed back into `get-wellcounts` — if you change `stack_name`, change the `STACK` pattern to match. Adding a scope means adding the pattern, a test, and the row in the README table; `normalize_scope` handles casing and the `CV800` alias.

`cellimgs/imgio.py` holds the shared filesystem and array helpers: `ensure_dir` (never `os.mkdir` — it fails on nested paths), `find_images`, `read_stack`, `write_stack`, `max_project`, `count_labels`. `read_stack` allocates with the source dtype; allocating with `np.zeros`/`np.ones` silently promotes plate data to float64.

`write_stack` passes `photometric="minisblack"`. Without it, tifffile stores a 3-plane Z-stack as an RGB image with separate components.

**All TIF output goes through `write_image`/`write_stack`**, which apply `imgio.COMPRESSION` (`"lzw"`). Never call `tif.imwrite` directly from a command — that is how output silently reverts to uncompressed. LZW is required: it is lossless, CellProfiler 4 reads it natively, and it shrinks label masks ~27x, which matters because output lands on a network mount.

**Lazy imports.** `cellimgs/__init__.py` deliberately imports nothing, and `gen_masks.py` imports cellpose inside functions. The previous `__init__.py` imported every submodule, so one missing dependency broke all eleven console scripts at once. `logger.py` must stay dependency-free — it used to import cellpose and torch for six lines of file writing, and every CLI paid that startup cost.

## Cellpose

Pinned to **Cellpose 4** (`cellpose>=4.0`, tested against 4.2.1.1). Three v3 APIs are traps:

- `models.CellposeModel(model_type=...)` is accepted and **ignored** (warns at `models.py:121`). Use `pretrained_model=`.
- `eval(channels=...)` is accepted and **ignored** (warns at `models.py:224`). Use `channel_axis=`.
- `denoise.CellposeDenoiseModel` no longer exists; the module only exports `add_noise`.

`gen_masks.resolve_model` rejects v3 zoo names with a `BadParameter` rather than letting them be ignored — extend `LEGACY_MODELS` if more surface. `eval()` returns 3 values. `utils.remove_edge_masks`, `utils.outlines_list` and `models.normalize_default` all still exist.

`gen_masks.get_masks` is the reusable function; `generate_masks` is the thin Click wrapper, and `align_all.run` calls `get_masks` directly rather than shelling out. It computes the work list before constructing the model, so a fully-cached directory never touches the GPU.

## Alignment

`align_all.align_pair` hill-climbs a binarised second-pass mask into overlap with the first, four directions at a time. The step schedule is **coarse-to-fine**: on a round where no direction improves, the step halves. The original derived the step purely from the current overlap and gave up after five stalled rounds, so a 6-pixel offset attacked with 10-pixel steps could never be refined. `tests/test_align.py` asserts exact recovery of known shifts — keep it passing if you touch the loop.

`pad_image` direction names describe the pad, not the motion: `"right"` pads the right edge and crops from the left, moving content left.

## Conventions

- Output directories are created before `logger()` is called, not after.
- `logger(path, params, command=)` takes an explicit dict. Never pass `locals()` — the old idiom captured whatever was in scope, including the constructed Cellpose model.
- Errors that reach a user go through `click.ClickException` so the CLI prints one line instead of a traceback.
- Commands skip existing output unless `--replace`, and report counts of what they wrote, skipped and failed to parse. Silent no-ops caused several of the bugs this package was rewritten to fix.
- `KMP_DUPLICATE_LIB_OK=TRUE` is set on Windows in commands that touch torch.

## Removed

Do not restore these without a reason: the PyQt GUI (`gui/`, `masker`), `cellimgs/cellimgs.py` (dead, typo-ridden), `cellimgs/tifsmasher.py` (duplicated `stacker.py`), `cellimgs/merger.py` (folded into `metadata.py` and `imgio.py`), `setup.py` and `requirements.txt` (replaced by `pyproject.toml`), and the `javabridge`/`bioformats` dependency (replaced by `cellimgs/c01.py`).

## C01 reader

`cellimgs/c01.py` decodes Cellomics `.C01` in pure Python: 4-byte header, zlib stream, `BITMAPINFOHEADER` plus 12 bytes of padding, pixel data at offset 52, 8 or 16 bit, negative `biHeight` means bottom-up rows. `c01.encode` exists to generate test fixtures.

**This has not been validated against a real instrument file** — it is implemented from the Bio-Formats `CellomicsReader` spec and round-trip tested only. Verify against a known `.C01` before trusting a production conversion.
