#!/usr/bin/env python3
"""Commandor — entry point shim.

Historically this file imported a non-existent `terminal` module and would
fail at import time.  The real entry point lives in `__main__.py` (wired
up via the `commandor` console-script in pyproject.toml).  This file is
kept as a thin wrapper so `python -m commandor.main` still works for
backward compatibility.
"""

import sys

from .__main__ import main


if __name__ == "__main__":
    sys.exit(main())
