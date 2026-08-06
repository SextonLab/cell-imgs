"""Run logging.

Writes a ``log.txt`` of the parameters used for a run into the output
directory. This module deliberately imports nothing heavy — it used to pull in
cellpose, torch, pandas, numpy and tifffile for six lines of file writing,
which every CLI paid for at startup.
"""

import os
from datetime import datetime


def logger(path, params, command=None):
    """Append a timestamped record of ``params`` to ``path/log.txt``.

    Args:
        path: output directory. Created if it does not exist.
        params: mapping of parameter name to value. Pass an explicit dict —
            the old ``logger(outdir, locals())`` idiom captured whatever
            happened to be in scope, including the constructed Cellpose model.
        command: name of the command being logged.
    """
    os.makedirs(path, exist_ok=True)
    logfile = os.path.join(path, "log.txt")

    lines = [f"=== {datetime.now().isoformat(timespec='seconds')} ==="]
    if command:
        lines.append(f"command:{command}")
    lines.extend(f"{key}:{value}" for key, value in params.items())

    # Append rather than truncate, so a directory keeps its processing history.
    with open(logfile, "a") as handle:
        handle.write("\n".join(lines) + "\n\n")

    print("Log appended to:", logfile)
    return logfile
