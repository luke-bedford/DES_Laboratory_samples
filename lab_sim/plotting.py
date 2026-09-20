import math
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

from .config import SimulationConfig
from .entities import SampleType
from .stats import StatsCollector

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


def _type_label(sample_type: SampleType) -> str:
    return sample_type.name.replace("_", " ").title()


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


def _expected_arrivals_per_bucket(
    config: SimulationConfig, sample_type: SampleType, bucket_minutes: float
) -> float:
    """Expected sample count per bucket for one sample type, given its own
    interarrival mean (SampleTypeProfile). For a batched type this multiplies
    in the mean batch size - only approximate, since the true per-bucket
    count is a compound Poisson-of-batches distribution, not a pure Poisson
    one, but close enough to anchor the diagnostic plot."""

    profile = config.sample_type_profiles[sample_type]
    batch_mean = (sum(config.batch_size_range) / 2) if profile.batched else 1.0
    return (bucket_minutes / profile.mean_interarrival_minutes) * batch_mean


def _plot_arrival_counts(
    ax,
    stats: StatsCollector,
    config: SimulationConfig,
    bucket_minutes: float,
    sample_type: SampleType,
    bins: np.ndarray,
    show_legend: bool,
) -> None:
    """Bucketed arrival counts for one sample type vs. the Poisson
    distribution implied by that type's own interarrival mean."""

    n_buckets = max(1, math.ceil(config.sim_duration_minutes / bucket_minutes))
    counts = np.zeros(n_buckets, dtype=int)
    for sample in stats.observed_arrivals():
        if sample.sample_type is not sample_type:
            continue
        # Bucket relative to the end of the warm-up period, since
        # arrival_time is absolute simulation time.
        idx = min(
            int((sample.arrival_time - config.warmup_minutes) // bucket_minutes),
            n_buckets - 1,
        )
        counts[idx] += 1

    lam = _expected_arrivals_per_bucket(config, sample_type, bucket_minutes)

    ax.hist(
        counts,
        bins=bins,
        density=True,
        color=_BLUE,
        alpha=0.85,
        edgecolor=_SURFACE,
        linewidth=1.0,
        label="observed",
        zorder=2,
    )
    k_values = np.arange(0, int(bins[-1]) + 1)
    pmf = [_poisson_pmf(k, lam) for k in k_values]
    ax.plot(
        k_values,
        pmf,
        color=_ORANGE,
        linewidth=2,
        marker="o",
        markersize=3,
        label=f"Poisson (λ={lam:.1f})",
        zorder=3,
    )
    ax.set_title(_type_label(sample_type), fontsize=10)
    ax.set_xlabel("samples / bucket", fontsize=9)
    if show_legend:
        ax.legend(frameon=False, labelcolor=_INK_SECONDARY, fontsize=7, loc="upper right")


def _plot_turnaround_times(
    ax,
    stats: StatsCollector,
    sample_type: SampleType,
    bins: np.ndarray,
) -> None:
    """Completed-sample turnaround times for one sample type, split by culture
    outcome, since positive cultures pick up an extra identification +
    sensitivity stage that shifts their turnaround distribution."""

    completed = stats.observed_completions()
    negative_hours = [
        s.turnaround_time("reported") / 60.0
        for s in completed
        if s.sample_type is sample_type
        and s.is_culture_positive is False
        and s.turnaround_time("reported") is not None
    ]
    positive_hours = [
        s.turnaround_time("reported") / 60.0
        for s in completed
        if s.sample_type is sample_type
        and s.is_culture_positive is True
        and s.turnaround_time("reported") is not None
    ]

    if negative_hours:
        ax.hist(
            negative_hours,
            bins=bins,
            density=True,
            histtype="stepfilled",
            color=_BLUE,
            alpha=0.75,
            edgecolor=_SURFACE,
            linewidth=1.0,
            label="negative",
            zorder=2,
        )
    if positive_hours:
        ax.hist(
            positive_hours,
            bins=bins,
            density=True,
            histtype="stepfilled",
            color=_ORANGE,
            alpha=0.75,
            edgecolor=_SURFACE,
            linewidth=1.0,
            label="positive",
            zorder=3,
        )
    if negative_hours or positive_hours:
        ax.text(
            0.97,
            0.95,
            f"neg={len(negative_hours)} pos={len(positive_hours)}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            color=_INK_MUTED,
            fontsize=7,
        )
    else:
        ax.text(
            0.5,
            0.5,
            "no completions",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=_INK_MUTED,
            fontsize=8,
        )
    ax.set_xlabel("turnaround (hours)", fontsize=9)


def plot_distribution_checks(
    stats: StatsCollector,
    config: SimulationConfig,
    output_path: str = "diagnostics/distribution_checks.png",
    bucket_minutes: float = 60.0,
) -> str:
    """Renders arrival-count and turnaround-time diagnostics as small multiples,
    one column per sample type, and saves them to output_path."""

    sample_types = list(SampleType)
    n_types = len(sample_types)

    n_buckets = max(1, math.ceil(config.sim_duration_minutes / bucket_minutes))
    observed_arrivals = stats.observed_arrivals()
    counts_by_type = {}
    for sample_type in sample_types:
        counts = np.zeros(n_buckets, dtype=int)
        for sample in observed_arrivals:
            if sample.sample_type is sample_type:
                idx = min(
                    int((sample.arrival_time - config.warmup_minutes) // bucket_minutes),
                    n_buckets - 1,
                )
                counts[idx] += 1
        counts_by_type[sample_type] = counts
    max_lam = max(
        _expected_arrivals_per_bucket(config, st, bucket_minutes) for st in sample_types
    )
    max_count = max(
        [int(c.max()) for c in counts_by_type.values() if len(c)] + [math.ceil(max_lam * 3)]
    )
    count_bins = np.arange(0, max_count + 2) - 0.5

    all_hours = [
        t / 60.0
        for s in stats.observed_completions()
        if (t := s.turnaround_time("reported")) is not None
    ]
    if all_hours:
        n_bins = max(5, min(12, len(all_hours) // 3))
        turnaround_bins = np.linspace(min(all_hours), max(all_hours), n_bins + 1)
    else:
        turnaround_bins = np.linspace(0, 1, 6)

    fig, axes = plt.subplots(
        2, n_types, figsize=(2.6 * n_types, 6.5), sharey="row"
    )
    fig.patch.set_facecolor(_SURFACE)

    for col, sample_type in enumerate(sample_types):
        ax_top, ax_bottom = axes[0, col], axes[1, col]
        _plot_arrival_counts(
            ax_top, stats, config, bucket_minutes, sample_type, count_bins, col == 0
        )
        _plot_turnaround_times(ax_bottom, stats, sample_type, turnaround_bins)
        _style_axes(ax_top)
        _style_axes(ax_bottom)
        if col == 0:
            ax_top.set_ylabel("probability", fontsize=9)
            ax_bottom.set_ylabel("probability density", fontsize=9)
        else:
            ax_top.tick_params(labelleft=False)
            ax_bottom.tick_params(labelleft=False)

    fig.suptitle(
        "Arrivals per bucket (top) and turnaround time (bottom), by sample type",
        color=_INK_PRIMARY,
        fontsize=11,
        y=0.99,
    )
    legend_handles = [
        Patch(facecolor=_BLUE, alpha=0.75, label="culture negative"),
        Patch(facecolor=_ORANGE, alpha=0.75, label="culture positive"),
    ]
    fig.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.955),
        ncol=2,
        frameon=False,
        labelcolor=_INK_SECONDARY,
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=150, facecolor=_SURFACE)
    plt.close(fig)
    return output_path
