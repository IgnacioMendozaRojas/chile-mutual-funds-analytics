"""ffmm update | ffmm build"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in {"update", "build"}:
        print("usage: ffmm {update,build} [options]   (ffmm update -h for options)")
        return 2
    if argv[0] == "update":
        from .update import main as run
    else:
        from .build import main as run
    return run(argv[1:])


if __name__ == "__main__":
    sys.exit(main())
