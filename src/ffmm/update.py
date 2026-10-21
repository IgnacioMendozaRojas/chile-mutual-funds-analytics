"""Bring data/processed up to date with the CMF, one month at a time.

Months already in the tables are skipped, so a monthly run downloads only the new
month (three files). `--rebuild` recomputes every month from the start date.
Each month is written as soon as it is done, so an interrupted run resumes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
from cmf_etl import BlockedError, NoDataError
from cmf_etl.extract import CMFClient

from . import store
from .monthly import aggregate
from .source import load_month

START = (2019, 1)


def months(start: tuple[int, int], end: tuple[int, int]) -> Iterator[tuple[int, int]]:
    y, m = start
    while (y, m) <= end:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def last_published(today: dt.date | None = None) -> tuple[int, int]:
    """The CMF publishes month M around days 10-15 of M+1; ask for M-1 and accept 'not yet'."""
    today = today or dt.date.today()
    return (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)


class PausedClient(CMFClient):
    """CMF client that waits between downloads, to be gentle with a public service."""

    def __init__(self, pause: float = 1.5, **kw):
        super().__init__(**kw)
        self.pause = pause

    def download(self, portfolio, year, month):
        try:
            return super().download(portfolio, year, month)
        finally:
            time.sleep(self.pause)


def _notice(level: str, title: str, message: str) -> None:
    """Plain line locally; a run annotation on GitHub Actions."""
    if os.getenv("GITHUB_ACTIONS"):
        print(f"::{level} title={title}::{message}")
    else:
        print(f"{level}: {title}: {message}")


def update(
    out: Path,
    start: tuple[int, int] = START,
    end: tuple[int, int] | None = None,
    rebuild: bool = False,
    client=None,
) -> dict[str, list[str]]:
    end = end or last_published()
    done = set() if rebuild else store.months_done(out)
    result: dict[str, list[str]] = {"added": [], "not_published": [], "blocked": []}
    for y, m in months(start, end):
        label = f"{y}-{m:02d}"
        if label in done:
            continue
        try:
            month = load_month(y, m, client=client)
        except NoDataError:
            result["not_published"].append(label)
            continue
        except BlockedError as exc:
            result["blocked"].append(label)
            _notice("error", f"Blocked {label}", str(exc))
            continue
        store.replace_month(out, aggregate(month))
        result["added"].append(label)
        for code, warnings in month.warnings.items():
            for w in warnings:
                _notice("warning", f"{code} {label}", w)
        print(f"{label}: " + ", ".join(f"{c} {n:,} rows" for c, n in month.rows.items()))
    return result


def gaps(out: Path, start: tuple[int, int] = START) -> list[str]:
    """Months missing between the start and the latest month in the tables."""
    done = store.months_done(out)
    if not done:
        return []
    last = pd.Period(max(done), "M")
    return [f"{y}-{m:02d}" for y, m in months(start, (last.year, last.month)) if f"{y}-{m:02d}" not in done]


def _period(text: str) -> tuple[int, int]:
    y, m = (int(x) for x in text.split("-"))
    return y, m


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ffmm update", description=__doc__)
    p.add_argument("--out", default="data/processed", type=Path)
    p.add_argument("--start", type=_period, default=START)
    p.add_argument("--end", type=_period)
    p.add_argument("--rebuild", action="store_true", help="recompute every month from --start")
    p.add_argument("--pause", type=float, default=1.5, help="seconds between downloads")
    args = p.parse_args(argv)

    r = update(args.out, args.start, args.end, args.rebuild, PausedClient(args.pause))
    print(f"added {len(r['added'])} months: {', '.join(r['added']) or '-'}")
    if r["not_published"]:
        print(f"not published yet: {', '.join(r['not_published'])}")
    missing = gaps(args.out, args.start)
    if missing:
        _notice("error", "Gaps", f"months missing inside the series: {', '.join(missing)}")
    return 1 if (r["blocked"] or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
