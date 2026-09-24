import math
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from scipy import stats

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

# Label -> SimulationConfig attribute name for each of the simulation's own
# per-stage (mean, stdev) Gaussian service-time parameters (processes.py's
# _duration, floored at STAGE_TIME_FLOOR_MINUTES). Labels match report.py's
# _PHASES so both documents describe the same stages the same way.
STAGE_TIME_FIELDS: list[tuple[str, str]] = [
    ("Reception", "reception_time"),
    ("Accessioning", "accessioning_time"),
    ("Plating", "plating_time"),
    ("Primary incubation", "incubation_time"),
    ("Reading", "reading_time"),
    ("Susceptibility setup", "susceptibility_setup_time"),
    ("Sensitivity incubation", "sensitivity_incubation_time"),
    ("Sensitivity reading", "sensitivity_reading_time"),
    ("Result entry", "result_entry_time"),
    ("Verification", "verification_time"),
]

STAGE_TIME_FLOOR_MINUTES = 0.1
_STAGE_HOUR_THRESHOLD_MINUTES = 120  # matches report._format_minutes's minutes/hours cutoff


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
    """Expected sample count per bucket for one sample type, given the mean
    of its day-of-week arrival rates (SampleTypeProfile). For a batched type
    this multiplies in the mean batch size. Doubly approximate now: the true
    per-bucket count is a compound Poisson-of-batches distribution even at a
    constant rate, and arrivals are no longer constant-rate at all - this
    overlay uses the week-average rate as a single reference line, so a
    visible mismatch against buckets that fall on a particularly busy or
    quiet weekday is expected and is itself evidence the day-of-week NHPP is
    doing something, not a bug in the overlay."""

    profile = config.sample_type_profiles[sample_type]
    avg_rate_per_day = sum(profile.arrivals_per_day_by_weekday.values()) / 7
    avg_rate_per_minute = avg_rate_per_day / (24 * 60)
    batch_mean = (sum(config.batch_size_range) / 2) if profile.batched else 1.0
    return bucket_minutes * avg_rate_per_minute * batch_mean


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


def stage_time_params(config: SimulationConfig) -> list[dict]:
    """Mean/stdev/floor-clip-% for each of the simulation's own per-stage
    Gaussian service-time parameters (STAGE_TIME_FIELDS) - what
    lab_sim/processes.py actually samples from, not a fit to any data."""

    params = []
    for label, attr in STAGE_TIME_FIELDS:
        mean_minutes, stdev_minutes = getattr(config, attr)
        floor_clip_pct = 100 * float(
            stats.norm.cdf(STAGE_TIME_FLOOR_MINUTES, mean_minutes, stdev_minutes)
        )
        params.append({
            "label": label,
            "mean_minutes": mean_minutes,
            "stdev_minutes": stdev_minutes,
            "floor_clip_pct": floor_clip_pct,
        })
    return params


def _plot_stage_time(ax, label: str, mean_minutes: float, stdev_minutes: float) -> None:
    """Draws the Gaussian PDF processes.py actually samples from for this
    stage (random.gauss(mean, stdev), floored at STAGE_TIME_FLOOR_MINUTES) -
    not a fit to data, just a visualization of the configured parameters.
    Displayed in hours for stages whose mean is >=
    _STAGE_HOUR_THRESHOLD_MINUTES, minutes otherwise."""

    use_hours = mean_minutes >= _STAGE_HOUR_THRESHOLD_MINUTES
    scale = 1 / 60 if use_hours else 1.0
    unit = "h" if use_hours else "min"

    mean_u = mean_minutes * scale
    stdev_u = stdev_minutes * scale
    floor_u = STAGE_TIME_FLOOR_MINUTES * scale

    x_lo = max(0.0, mean_u - 4 * stdev_u)
    x_hi = mean_u + 4 * stdev_u
    x = np.linspace(x_lo, x_hi, 200)
    pdf = stats.norm.pdf(x, mean_u, stdev_u)

    ax.plot(x, pdf, color=_ORANGE, linewidth=2, zorder=3)
    ax.fill_between(x, pdf, color=_ORANGE, alpha=0.15, zorder=2)
    if x_lo <= floor_u <= x_hi:
        ax.axvline(floor_u, color=_INK_MUTED, linewidth=1, linestyle="--", zorder=1)
    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(0, pdf.max() * 1.15)
    ax.set_title(label, fontsize=9.5)
    ax.set_xlabel(f"{mean_u:.1f} ± {stdev_u:.1f} {unit}", fontsize=8)


def plot_stage_time_distributions(
    config: SimulationConfig,
    output_path: str = "diagnostics/stage_time_distributions.png",
) -> str:
    """Visualizes config.py's own per-stage (mean, stdev) Gaussian
    service-time assumptions, one small panel per stage."""

    params = stage_time_params(config)
    n = len(params)
    cols = 5
    rows = -(-n // cols)  # ceil division

    fig, axes = plt.subplots(rows, cols, figsize=(2.6 * cols, 2.6 * rows))
    axes = np.atleast_2d(axes)

    for i, p in enumerate(params):
        ax = axes[i // cols, i % cols]
        _plot_stage_time(ax, p["label"], p["mean_minutes"], p["stdev_minutes"])
        _style_axes(ax)
        if i % cols == 0:
            ax.set_ylabel("density", fontsize=9)

    for i in range(n, rows * cols):
        axes[i // cols, i % cols].axis("off")

    fig.patch.set_facecolor(_SURFACE)
    fig.suptitle(
        "Per-stage service-time parameters (Gaussian, floored at "
        f"{STAGE_TIME_FLOOR_MINUTES} min)",
        color=_INK_PRIMARY, fontsize=10.5, y=1.0,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=150, facecolor=_SURFACE)
    plt.close(fig)
    return output_path
