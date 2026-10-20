"""Figures, each in a light and a dark version for GitHub's <picture> tag."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

THEMES = {
    "light": {
        "bg": "#fcfcfb",
        "fg": "#2b2b29",
        "muted": "#6e6e6a",
        "grid": "#e6e6e3",
        "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
    },
    "dark": {
        "bg": "#1a1a19",
        "fg": "#e8e8e5",
        "muted": "#a3a39e",
        "grid": "#33332f",
        "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"],
    },
}


def _ax(t, size=(8, 4)):
    fig, ax = plt.subplots(figsize=size, facecolor=t["bg"])
    ax.set_facecolor(t["bg"])
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(t["grid"])
    ax.tick_params(colors=t["muted"], labelsize=9)
    ax.grid(True, axis="y", color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)
    return fig, ax


def _title(ax, t, title, subtitle):
    ax.set_title(title, loc="left", color=t["fg"], fontsize=12, fontweight="bold", pad=22)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, color=t["muted"], fontsize=9)


def _save(fig, out: Path, name: str, theme: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}-{theme}.png", dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _x(index) -> list:
    return [p.to_timestamp() if hasattr(p, "to_timestamp") else pd.Timestamp(str(p)) for p in index]


def stacked(df: pd.DataFrame, out: Path, name: str, title: str, subtitle: str, unit: str) -> None:
    x = _x(df.index)
    for theme, t in THEMES.items():
        fig, ax = _ax(t)
        ax.stackplot(
            x, *[df[c] for c in df.columns], colors=t["series"][: len(df.columns)], edgecolor=t["bg"], linewidth=1.0
        )
        cum = df.cumsum(axis=1).iloc[-1]
        prev = 0.0
        for c, col in zip(df.columns, t["series"], strict=False):
            mid = (prev + cum[c]) / 2
            ax.text(x[-1], mid, f"  {c}", va="center", color=t["fg"], fontsize=8.5)
            ax.plot([], [], color=col)
            prev = cum[c]
        ax.set_ylabel(unit, color=t["muted"], fontsize=9)
        ax.set_xlim(x[0], x[-1])
        _title(ax, t, title, subtitle)
        _save(fig, out, name, theme)


def lines(df: pd.DataFrame, out: Path, name: str, title: str, subtitle: str, unit: str, pct: bool = False) -> None:
    x = _x(df.index)
    for theme, t in THEMES.items():
        fig, ax = _ax(t)
        for c, col in zip(df.columns, t["series"], strict=False):
            ax.plot(x, df[c], color=col, lw=2)
            last = df[c].iloc[-1]
            if len(df.columns) > 1:
                ax.annotate(f" {c}", (x[-1], last), color=t["fg"], fontsize=8.5, va="center")
        ax.set_ylim(bottom=0)
        if pct:
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
        ax.set_ylabel(unit, color=t["muted"], fontsize=9)
        _title(ax, t, title, subtitle)
        _save(fig, out, name, theme)


def bars(s: pd.Series, out: Path, name: str, title: str, subtitle: str, unit: str) -> None:
    s = s.sort_values()
    for theme, t in THEMES.items():
        fig, ax = _ax(t, (8, 0.42 * len(s) + 1.3))
        ax.grid(False)
        ax.grid(True, axis="x", color=t["grid"], linewidth=0.8)
        ax.barh(range(len(s)), s.values, color=t["series"][0], height=0.62)
        ax.set_yticks(range(len(s)), s.index, color=t["fg"])
        for i, v in enumerate(s.values):
            ax.text(v, i, f"  {v:,.0f}", va="center", color=t["fg"], fontsize=9)
        ax.set_xlabel(unit, color=t["muted"], fontsize=9)
        _title(ax, t, title, subtitle)
        _save(fig, out, name, theme)
