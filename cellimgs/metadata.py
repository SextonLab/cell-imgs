"""Filename metadata parsing for high-content screening images.

Every microscope in this package encodes plate/well/field/timepoint/Z/channel
in the filename, so all of the stacking and projection tools work the same way:
parse filenames into a table, group the rows, then combine the matching images.

This module is the single source of truth for those patterns. Previously the
same regexes lived in three places (``merger.make_table``, ``merger.get_regex``
and ``stacker.REG``) with different column names and different bugs.
"""

import os
import re

import pandas as pd

SCOPES = ("CV8000", "CQ1", "CX5", "STICH", "STACK")

# Patterns are matched against the basename with its extension stripped, so
# they must never depend on directory separators. The old CQ1 pattern required
# a literal path separator but was applied to os.path.basename(), which meant
# it could never match and every CQ1 run silently produced no output.
_PATTERNS = {
    # e.g. plate1_A01_T0001F001L01A01Z01C01.tif
    "CV8000": re.compile(
        r"^(?P<plate_id>.+)_(?P<well_id>[A-P]\d{2})"
        r"_T(?P<timepoint>\d+)F(?P<field_id>\d+)L(?P<location>\d+)"
        r"A(?P<action>\d+)Z(?P<zstack>\d+)C(?P<channel>\d+)$"
    ),
    # e.g. W0001F0001T0001Z001C1.tif  (plate id comes from the parent folder)
    "CQ1": re.compile(
        r"^(?P<well_id>W\d{4})F(?P<field_id>\d+)T(?P<timepoint>\d+)"
        r"Z(?P<zstack>\d+)C(?P<channel>\d+)$"
    ),
    # Cellomics ArrayScan, e.g. MFGTMP_260306160001_A01f00d0.C01
    # 'f' is the field and 'd' the channel (dye).
    "CX5": re.compile(
        r"^(?P<plate_id>.+)_(?P<well_id>[A-P]\d{2})"
        r"f(?P<field_id>\d+)d(?P<channel>\d+)$"
    ),
    # e.g. A01_F0001_T0001_Z0004_C01.tif
    "STICH": re.compile(
        r"^(?P<well_id>.+?)_F(?P<field_id>\d+)_T(?P<timepoint>\d+)"
        r"_Z(?P<zstack>\d+)_C(?P<channel>\d+)$"
    ),
    # This package's own output, e.g. A01_F001_C01.tif. Without it the
    # stacks and projections written by stack-imgs and smashtif could not be
    # fed back into get-wellcounts.
    "STACK": re.compile(
        r"^(?P<well_id>.+?)_F(?P<field_id>\d+)_C(?P<channel>\d+)$"
    ),
}

COLUMNS = (
    "path",
    "plate_id",
    "well_id",
    "row_id",
    "column_id",
    "timepoint",
    "field_id",
    "location",
    "zstack",
    "channel",
)

#: Columns that are parsed as integers, so they sort numerically rather than
#: lexically. ``zstack`` in particular used to be ordered by concatenating
#: every digit in the full path, which broke whenever a directory name
#: contained a number.
NUMERIC = ("timepoint", "field_id", "location", "zstack", "channel")

_WELL_SPLIT = re.compile(r"^([A-Za-z]+)0*(\d+)$")


def normalize_scope(scope):
    """Accept any casing and the common ``CV800`` typo from the old README."""
    key = str(scope).upper().strip()
    if key == "CV800":
        key = "CV8000"
    if key not in SCOPES:
        raise ValueError(f"Unknown scope {scope!r}; expected one of {', '.join(SCOPES)}")
    return key


def split_wellid(well):
    """Split a well id such as ``A01`` or ``W0001`` into (row, column)."""
    match = _WELL_SPLIT.match(str(well))
    if match is None:
        return str(well), ""
    return match.group(1), match.group(2)


def parse_filename(path, scope):
    """Parse one path into a metadata dict, or ``None`` if it does not match."""
    scope = normalize_scope(scope)
    stem = os.path.splitext(os.path.basename(path))[0]
    match = _PATTERNS[scope].match(stem)
    if match is None:
        return None

    meta = match.groupdict()
    meta.pop("action", None)

    record = {"path": path}
    for column in COLUMNS[1:]:
        record[column] = meta.get(column)

    # CQ1 filenames carry no plate id, so fall back to the containing folder.
    if not record["plate_id"]:
        parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
        record["plate_id"] = parent or "plate"

    for column in NUMERIC:
        record[column] = int(record[column]) if record[column] is not None else 0

    record["row_id"], record["column_id"] = split_wellid(record["well_id"])
    return record


def build_table(files, scope):
    """Build the metadata DataFrame for ``files``.

    Unparseable filenames are skipped, and the caller is told how many were
    dropped rather than silently receiving a short table.
    """
    records = []
    skipped = []
    for path in files:
        record = parse_filename(path, scope)
        if record is None:
            skipped.append(path)
        else:
            records.append(record)

    if skipped:
        print(
            f"Warning: {len(skipped)} of {len(files)} file(s) did not match the "
            f"{normalize_scope(scope)} naming pattern and were skipped. "
            f"First unmatched: {os.path.basename(skipped[0])}"
        )

    df = pd.DataFrame(records, columns=list(COLUMNS))
    for column in NUMERIC:
        df[column] = df[column].astype("int64")
    return df


def stack_files(df, well, field, channel, on="z", field_column="field_id"):
    """Ordered list of paths making up a single stack.

    ``on`` selects the axis the stack varies along: ``z`` (default), ``t`` for
    a timelapse, or ``l`` for stage location.
    """
    axis = {"z": "zstack", "t": "timepoint", "l": "location"}[on]
    rows = df[
        (df["well_id"] == well)
        & (df[field_column] == field)
        & (df["channel"] == channel)
    ]
    return rows.sort_values(axis)["path"].tolist()


def iter_groups(df, field_column="field_id"):
    """Yield every ``(well, field, channel)`` combination present in ``df``.

    Fields and channels are taken per well rather than globally. ``stacker.py``
    used to iterate the global field list inside the well loop, which produced
    empty stacks and an IndexError on plates where wells had different fields.
    """
    for well in sorted(df["well_id"].unique()):
        in_well = df[df["well_id"] == well]
        for field in sorted(in_well[field_column].unique()):
            in_field = in_well[in_well[field_column] == field]
            for channel in sorted(in_field["channel"].unique()):
                yield well, field, channel


def stack_name(well, field, channel, suffix=".tif"):
    """Canonical output filename for a stack or projection.

    Both ``stacker`` and ``smashtif`` now emit this form. Previously they
    disagreed: ``A01_F001_C01.tif`` versus ``A01_001_01.tif``.
    """
    return f"{well}_F{int(field):03d}_C{int(channel):02d}{suffix}"
