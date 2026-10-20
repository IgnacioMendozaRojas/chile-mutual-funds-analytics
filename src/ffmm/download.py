"""Download CMF mutual fund portfolio files.

The CMF statistics portal has no API: a browser loads the form (which sets a
session cookie) and posts month, year and portfolio code to a download endpoint.
Files are saved untouched, gzip-compressed, as <raw_dir>/<CODE>_<YYYYMM>.txt.gz, so a
re-run skips what is already there.
"""

from __future__ import annotations

import datetime as dt
import gzip
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

FORM_URL = "https://www.cmfchile.cl/institucional/estadisticas/ffm_cartera.php"
DOWNLOAD_URL = "https://www.cmfchile.cl/institucional/estadisticas/ffm_download.php"


def months(start: tuple[int, int], end: tuple[int, int]) -> Iterator[tuple[int, int]]:
    y, m = start
    while (y, m) <= end:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def form_portfolios(html: str) -> dict[str, str]:
    """Portfolio codes offered by the form, without the "Seleccione" placeholder."""
    block = re.search(r"<select[^>]*name=[\"']cartera[\"'][^>]*>(.*?)</select>", html, re.S | re.I)
    options = re.findall(r"<option[^>]*value=[\"']([^\"']+)[\"'][^>]*>([^<]*)", block.group(1) if block else "", re.I)
    return {v.strip(): t.strip() for v, t in options if re.fullmatch(r"[A-Z]{3,5}", v.strip())}


def is_data(content: bytes) -> bool:
    head = content[:400].decode("latin-1", "replace").lower()
    return len(content) > 50 and "<html" not in head and "<!doctype" not in head


@dataclass
class Downloader:
    raw_dir: Path
    pause: float = 1.5
    session: object | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.raw_dir = Path(self.raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        if self.session is None:
            import requests

            self.session = requests.Session()
            self.session.headers["User-Agent"] = "Mozilla/5.0 (chile-mutual-funds-analytics)"

    def path(self, code: str, year: int, month: int) -> Path:
        return self.raw_dir / f"{code}_{year}{month:02d}.txt.gz"

    def fetch(self, code: str, year: int, month: int) -> bytes | None:
        self.session.get(FORM_URL, timeout=60)
        resp = self.session.post(
            DOWNLOAD_URL, data={"mm": f"{month:02d}", "aa": str(year), "cartera": code}, timeout=180
        )
        resp.raise_for_status()
        return resp.content if is_data(resp.content) else None

    def run(self, codes: list[str], start: tuple[int, int], end: tuple[int, int] | None = None) -> dict[str, int]:
        today = dt.date.today()
        end = end or ((today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12))
        stats = {"downloaded": 0, "skipped": 0, "empty": 0}
        for code in codes:
            for y, m in months(start, end):
                target = self.path(code, y, m)
                if target.exists():
                    stats["skipped"] += 1
                    continue
                content = self.fetch(code, y, m)
                if content is None:
                    stats["empty"] += 1
                    print(f"{code} {y}-{m:02d}: no data")
                else:
                    target.write_bytes(gzip.compress(content))
                    stats["downloaded"] += 1
                    rows = content.count(b"\n")
                    print(f"{code} {y}-{m:02d}: {rows:,} rows")
                time.sleep(self.pause)
        return stats
