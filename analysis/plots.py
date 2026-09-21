"""Renders the real-data distribution-fit diagnostics to a PNG, faceted by
specimen type - same visual language as lab_sim/plotting.py (histogram +
fitted-curve overlay), duplicated here rather than imported since the two
modules plot different things.
"""

import os

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

from .distribution_fits import (
    GroupSummary,
    TURNAROUND_CANDIDATES,
    interarrival_gaps_minutes,
    time_rescale_gaps,
)
from .load_real_data import ANALYSIS_GROUPS, RealResultRow, rows_by_group

_SURFACE = "#fcfcfb"
_INK_PRIMARY = "#0b0b0b"
_INK_SECONDARY = "#52514e"
_INK_MUTED = "#898781"
_GRID = "#e1e0d9"
_AXIS = "#c3c2b7"
_BLUE = "#2a78d6"
_ORANGE = "#eb6834"


def _style_axes(ax) -> None:
    ax.set_facecolor(_SURFACE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(_AXIS)
    ax.spines["bottom"].set_color(_AXIS)
    ax.tick_params(colors=_INK_MUTED, labelsize=8)
    ax.grid(axis="y", color=_GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.title.set_color(_INK_PRIMARY)
    ax.xaxis.label.set_color(_INK_SECONDARY)
    ax.yaxis.label.set_color(_INK_SECONDARY)


def _group_label(group: str) -> str:
    return group.replace("_", " ").title()


def _no_data(ax, group: str) -> None:
    ax.text(
        0.5, 0.5, "not enough data",
        transform=ax.transAxes, ha="center", va="center",
        color=_INK_MUTED, fontsize=8,
    )
    ax.set_title(_group_label(group), fontsize=10)


def _plot_interarrival(ax, rows: list[RealResultRow], summary: GroupSummary, show_legend: bool) -> None:
    fit = summary.interarrival
    gaps_hours = interarrival_gaps_minutes(rows) / 60.0
    if len(gaps_hours) < 5 or fit.real_mean_minutes is None:
        _no_data(ax, summary.group)
        return

    # Clip the display range to the 99th percentile - a handful of very long
    # gaps (e.g. a quiet weekend) otherwise stretch the bins so far that the
    # bulk of the distribution collapses into a single sliver near zero.
    x_max = np.percentile(gaps_hours, 99)
    counts, _, _ = ax.hist(
        gaps_hours, bins=30, range=(0, x_max), density=True, color=_BLUE, alpha=0.85,
        edgecolor=_SURFACE, linewidth=0.6, label="observed", zorder=2,
    )
    mean_hours = fit.real_mean_minutes / 60.0
    x = np.linspace(0, x_max, 200)
    ax.plot(
        x, stats.expon.pdf(x, scale=mean_hours), color=_ORANGE, linewidth=2,
        label="fitted exponential", zorder=3,
    )
    ax.set_xlim(0, x_max)
    # A tightly-scaled exponential can peak far above the histogram's own
    # bars; clip to the histogram's range so that peak doesn't flatten
    # everything else in the panel.
    ax.set_ylim(0, max(counts.max(), stats.expon.pdf(0, scale=mean_hours)) * 1.15)
    ax.set_title(_group_label(summary.group), fontsize=10)
    ax.set_xlabel("inter-arrival gap (h)", fontsize=9)
    if show_legend:
        ax.legend(frameon=False, labelcolor=_INK_SECONDARY, fontsize=7, loc="upper right")


def _plot_turnaround(ax, summary: GroupSummary, all_hours: np.ndarray, show_legend: bool) -> None:
    fit = summary.turnaround_all
    if len(all_hours) < 5 or fit.best_dist is None:
        _no_data(ax, summary.group)
        return

    # Same 99th-percentile clip as the inter-arrival plot - turnaround has a
    # long real tail (samples awaiting a delayed final report) that would
    # otherwise dominate the axis.
    x_min = max(0.01, min(all_hours))
    x_max = np.percentile(all_hours, 99)
    counts, _, _ = ax.hist(
        all_hours, bins=30, range=(x_min, x_max), density=True, color=_BLUE, alpha=0.85,
        edgecolor=_SURFACE, linewidth=0.6, label="observed", zorder=2,
    )
    dist = TURNAROUND_CANDIDATES[fit.best_dist]
    x = np.linspace(x_min, x_max, 200)
    ax.plot(
        x, dist.pdf(x, *fit.best_params), color=_ORANGE, linewidth=2,
        label=f"best fit: {fit.best_dist}", zorder=3,
    )
    ax.set_xlim(x_min, x_max)
    # A distribution with shape < 1 (e.g. gamma) can have a PDF that diverges
    # near its lower bound; clip to the histogram's own range so that
    # divergence doesn't flatten the rest of the panel.
    ax.set_ylim(0, max(counts.max(), 1e-9) * 1.5)
    ax.set_xlabel("turnaround (h)", fontsize=9)
    if show_legend:
        ax.legend(frameon=False, labelcolor=_INK_SECONDARY, fontsize=7, loc="upper right")


def _no_data_qq(ax) -> None:
    ax.text(
        0.5, 0.5, "not enough data",
        transform=ax.transAxes, ha="center", va="center",
        color=_INK_MUTED, fontsize=8,
    )


def _qq_exponential(ax, sample: np.ndarray, scale: float) -> None:
    """Empirical quantiles of sample against the theoretical quantiles of an
    Exp(scale) - points hugging the 45-degree reference line support the
    exponential fit; systematic curvature away from it (as seen here for
    every group, in both the raw and rescaled panels) is the signature of a
    heavier-than-exponential tail. Log-log axes: the exponential's own
    quantiles are extremely right-skewed at this sample size (a handful of
    long quiet gaps vs. thousands of short ones), so linear axes crush
    nearly every point into the corner and hide exactly the deviation this
    plot exists to show."""
    sample = np.sort(sample[sample > 0])
    n = len(sample)
    probs = (np.arange(1, n + 1) - 0.5) / n
    theoretical = stats.expon.ppf(probs, scale=scale)
    ax.scatter(
        theoretical, sample, s=6, color=_BLUE, alpha=0.5,
        edgecolors="none", zorder=2,
    )
    lo = max(min(float(theoretical[0]), float(sample[0])), 1e-6)
    hi = max(float(theoretical[-1]), float(sample[-1]))
    ax.plot([lo, hi], [lo, hi], color=_ORANGE, linewidth=1.5, zorder=3)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)


def render_interarrival_qq_plots(
    rows: list[RealResultRow],
    summaries: dict[str, GroupSummary],
    output_path: str = "diagnostics/real_data_interarrival_qq.png",
) -> str:
    """Q-Q plots for the exponential inter-arrival fits: top row is the raw
    pooled gaps against an exponential at the fitted rate (same fit as the
    histogram overlay in render_distribution_plots); bottom row is the same
    arrivals after day-of-week NHPP time-rescaling (see
    distribution_fits.time_rescale_gaps) against Exp(1) - the "does
    correcting for day-of-week explain the curvature" comparison."""

    grouped = rows_by_group(rows)
    n = len(ANALYSIS_GROUPS)

    fig, axes = plt.subplots(2, n, figsize=(2.6 * n, 6.0))
    fig.patch.set_facecolor(_SURFACE)

    for col, group in enumerate(ANALYSIS_GROUPS):
        summary = summaries[group]
        rows_for_group = grouped[group]
        ax_top, ax_bottom = axes[0, col], axes[1, col]

        raw_gaps = interarrival_gaps_minutes(rows_for_group)
        mean_minutes = summary.interarrival.real_mean_minutes
        if len(raw_gaps) >= 5 and mean_minutes:
            _qq_exponential(ax_top, raw_gaps, mean_minutes)
        else:
            _no_data_qq(ax_top)
        ax_top.set_title(_group_label(group), fontsize=10)
        ax_top.set_xlabel("theoretical, min (fitted rate)", fontsize=7.5)

        rescaled, _ = time_rescale_gaps(rows_for_group, summary.nhpp.day_rates_per_day)
        rescaled = rescaled[rescaled > 0]
        if len(rescaled) >= 5:
            _qq_exponential(ax_bottom, rescaled, 1.0)
        else:
            _no_data_qq(ax_bottom)
        ax_bottom.set_xlabel("theoretical, Exp(1) (day-of-week rescaled)", fontsize=7.5)

        _style_axes(ax_top)
        _style_axes(ax_bottom)

    axes[0, 0].set_ylabel("observed (min)", fontsize=9)
    axes[1, 0].set_ylabel("observed (rescaled)", fontsize=9)

    fig.suptitle(
        "Inter-arrival Q-Q: raw exponential fit (top) vs. day-of-week NHPP "
        "time-rescaled (bottom) - points on the diagonal support the model",
        color=_INK_PRIMARY, fontsize=10.5, y=0.99,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=150, facecolor=_SURFACE)
    plt.close(fig)
    return output_path


def render_distribution_plots(
    rows: list[RealResultRow],
    summaries: dict[str, GroupSummary],
    output_path: str = "diagnostics/real_data_distribution_fits.png",
) -> str:
    grouped = rows_by_group(rows)
    n = len(ANALYSIS_GROUPS)

    # Not sharing axes: arrival rates and turnaround scales differ by orders
    # of magnitude between groups (e.g. Swab arrives every few minutes, Tissue
    # every few hours), so a shared y-axis would flatten all but the busiest
    # column.
    fig, axes = plt.subplots(2, n, figsize=(2.6 * n, 6.5))
    fig.patch.set_facecolor(_SURFACE)

    for col, group in enumerate(ANALYSIS_GROUPS):
        summary = summaries[group]
        rows_for_group = grouped[group]
        ax_top, ax_bottom = axes[0, col], axes[1, col]

        _plot_interarrival(ax_top, rows_for_group, summary, col == 0)
        all_hours = np.array([r.turnaround_days * 24 for r in rows_for_group])
        _plot_turnaround(ax_bottom, summary, all_hours, col == 0)

        _style_axes(ax_top)
        _style_axes(ax_bottom)
        ax_top.set_ylabel("density", fontsize=9)
        ax_bottom.set_ylabel("density", fontsize=9)

    fig.suptitle(
        "Real data: inter-arrival gaps vs. fitted exponential (top), "
        "turnaround vs. best-fit distribution (bottom)",
        color=_INK_PRIMARY, fontsize=11, y=0.99,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=150, facecolor=_SURFACE)
    plt.close(fig)
    return output_path
