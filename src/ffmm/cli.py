"""ffmm download | build"""

from __future__ import annotations

import argparse


def _period(text: str) -> tuple[int, int]:
    y, m = (int(x) for x in text.split("-"))
    return y, m


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ffmm", description="Chilean mutual fund holdings from the CMF")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download", help="download monthly portfolio files from the CMF portal")
    d.add_argument("--start", type=_period, default=(2019, 1), help="YYYY-MM (default 2019-01)")
    d.add_argument("--end", type=_period, help="YYYY-MM (default: last month)")
    d.add_argument(
        "--portfolio",
        action="append",
        choices=["NACI", "EXTR", "FUTU", "OPCI", "OPLA"],
        help="repeatable; default NACI, EXTR and FUTU",
    )
    d.add_argument("--raw", default="data/raw")
    d.add_argument("--pause", type=float, default=1.5)
    b = sub.add_parser("build", help="aggregate raw files into data/processed and docs/figures")
    b.add_argument("--raw", default="data/raw")
    args = p.parse_args(argv)

    if args.cmd == "download":
        from .download import Downloader

        stats = Downloader(args.raw, pause=args.pause).run(
            args.portfolio or ["NACI", "EXTR", "FUTU"], args.start, args.end
        )
        print(stats)
    else:
        from .build import build

        r = build(args.raw)
        print(f"built tables for {len(r['composition'])} months")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
