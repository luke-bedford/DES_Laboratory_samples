"""Fits the simulation's distributional assumptions against the real dataset.

Two things are checked per specimen type (the 6 modeled types, plus Multi-site
as a 7th analysis-only group - see load_real_data.py):

1. Inter-arrival gaps against an exponential distribution (the Poisson-arrival
   assumption every SampleTypeProfile.mean_interarrival_minutes rests on).
2. Aggregate turnaround time (receipt to verification - there's no per-stage
   timestamp in the real data, so only the *aggregate* shape can be checked,
   not individual stage assumptions) against normal/lognormal/gamma, picking
   the best fit by AIC.

Also compares real positivity rates and organism mixes against
lab_sim.config.SimulationConfig's current SampleTypeProfile values, for the 6
modeled types.

Nothing here writes to lab_sim/config.py - this module only reports.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

from lab_sim.config import SimulationConfig
from lab_sim.entities import Organism, SampleType
from .load_real_data import ANALYSIS_GROUPS, RealResultRow, SPECIMEN_TYPE_MAP
from .organism_mapping import map_organism

_MAPPED_TYPE_BY_GROUP: dict[str, SampleType] = {
    t.name: t for t in SPECIMEN_TYPE_MAP.values()
}

DAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

TURNAROUND_CANDIDATES = {
    "normal": stats.norm,
    "lognormal": stats.lognorm,
    "gamma": stats.gamma,
}


@dataclass
class InterarrivalFit:
    n_gaps: int
    real_mean_minutes: float | None
    ks_stat: float | None
    ks_pvalue: float | None
    configured_mean_minutes: float | None
    aic: float | None = None


@dataclass
class TurnaroundFit:
    n: int
    mean_hours: float | None
    median_hours: float | None
    best_dist: str | None
    best_params: tuple | None
    best_ks_stat: float | None
    best_ks_pvalue: float | None
    aic_by_dist: dict[str, float] = field(default_factory=dict)


@dataclass
class WeibullFit:
    n: int
    shape: float | None
    scale: float | None
    aic: float | None
    ks_stat: float | None
    ks_pvalue: float | None


@dataclass
class NHPPReview:
    """Day-of-week non-homogeneous Poisson process (NHPP) review for one
    group's inter-arrival gaps - see day_of_week_rates/time_rescale_gaps/
    fit_weibull below. raw_* fields describe the pooled gaps as already fit by
    fit_interarrival; rescaled_* fields describe the same arrivals after
    applying the time-rescaling theorem to the day-of-week rate model, which
    should look like an Exp(1) process if that model explains the real gaps'
    non-exponential shape."""

    day_rates_per_day: dict[str, float]
    day_occurrences: dict[str, int]
    raw_ks_stat: float | None
    raw_ks_pvalue: float | None
    raw_exponential_aic: float | None
    rescaled_n: int
    rescaled_ties_dropped: int
    rescaled_ks_stat: float | None
    rescaled_ks_pvalue: float | None
    rescaled_exp1_aic: float | None
    raw_weibull: WeibullFit
    rescaled_weibull: WeibullFit
    index_of_dispersion: float | None


@dataclass
class GroupSummary:
    group: str
    n_rows: int
    n_positive: int
    positive_pct: float | None
    configured_positive_pct: float | None
    interarrival: InterarrivalFit
    nhpp: NHPPReview
    turnaround_all: TurnaroundFit
    turnaround_positive: TurnaroundFit
    turnaround_negative: TurnaroundFit
    organism_counts: Counter
    configured_organism_pct: dict[Organism, float]


def interarrival_gaps_minutes(rows: list[RealResultRow]) -> np.ndarray:
    received_sorted = np.sort(np.array([r.received_days for r in rows]))
    gaps = np.diff(received_sorted) * 24 * 60
    return gaps[gaps > 0]  # guard against ties producing zero-length gaps


def fit_interarrival(rows: list[RealResultRow], configured_mean: float | None) -> InterarrivalFit:
    gaps = interarrival_gaps_minutes(rows)
    if len(gaps) < 5:
        return InterarrivalFit(len(gaps), None, None, None, configured_mean)

    mean_minutes = float(np.mean(gaps))
    ks_stat, ks_pvalue = stats.kstest(gaps, "expon", args=(0, mean_minutes))
    return InterarrivalFit(
        n_gaps=len(gaps),
        real_mean_minutes=mean_minutes,
        ks_stat=float(ks_stat),
        ks_pvalue=float(ks_pvalue),
        configured_mean_minutes=configured_mean,
        # loc is fixed at 0, not fitted - only the mean/scale is a free
        # parameter, so k=1 (see _aic's docstring on why this can't just be
        # len(params)).
        aic=_aic(stats.expon, (0, mean_minutes), gaps, k=1),
    )


def _aic(dist, params: tuple, data: np.ndarray, k: int | None = None) -> float:
    """AIC = 2k - 2*log-likelihood. k defaults to len(params), correct when
    every entry in params was actually fitted (e.g. fit_turnaround's
    dist.fit(hours) with no fixed args). Pass k explicitly whenever a param
    was pinned rather than fitted (e.g. loc=0) - counting a pinned param as
    "free" understates the model's fit quality relative to a genuinely
    simpler one, which matters here since raw-vs-rescaled AIC deltas are the
    headline comparison."""
    loglik = float(np.sum(dist.logpdf(data, *params)))
    n_fitted = len(params) if k is None else k
    return 2 * n_fitted - 2 * loglik


def fit_turnaround(hours: np.ndarray) -> TurnaroundFit:
    hours = hours[hours > 0]  # lognormal/gamma need strictly positive support
    if len(hours) < 5:
        return TurnaroundFit(len(hours), None, None, None, None, None, None)

    fitted = {}
    for name, dist in TURNAROUND_CANDIDATES.items():
        try:
            params = dist.fit(hours)
            ks_stat, ks_pvalue = stats.kstest(hours, dist.cdf, args=params)
        except Exception:
            continue
        fitted[name] = {
            "params": params,
            "aic": _aic(dist, params, hours),
            "ks_stat": float(ks_stat),
            "ks_pvalue": float(ks_pvalue),
        }

    if not fitted:
        return TurnaroundFit(len(hours), float(np.mean(hours)), float(np.median(hours)), None, None, None, None)

    best_name = min(fitted, key=lambda name: fitted[name]["aic"])
    best = fitted[best_name]
    return TurnaroundFit(
        n=len(hours),
        mean_hours=float(np.mean(hours)),
        median_hours=float(np.median(hours)),
        best_dist=best_name,
        best_params=best["params"],
        best_ks_stat=best["ks_stat"],
        best_ks_pvalue=best["ks_pvalue"],
        aic_by_dist={name: f["aic"] for name, f in fitted.items()},
    )


def fit_weibull(gaps: np.ndarray) -> WeibullFit:
    """Weibull fit with location pinned to 0 (gaps/rescaled intervals are
    non-negative by construction) - shape<1 gives a heavier-than-exponential
    left tail (over-dispersed, CV>1), shape=1 recovers the exponential,
    shape>1 is more regular than random."""
    gaps = gaps[gaps > 0]
    if len(gaps) < 5:
        return WeibullFit(len(gaps), None, None, None, None, None)

    shape, loc, scale = stats.weibull_min.fit(gaps, floc=0)
    params = (shape, loc, scale)
    ks_stat, ks_pvalue = stats.kstest(gaps, "weibull_min", args=params)
    return WeibullFit(
        n=len(gaps),
        shape=float(shape),
        scale=float(scale),
        aic=_aic(stats.weibull_min, params, gaps, k=2),  # loc fixed, shape+scale fitted
        ks_stat=float(ks_stat),
        ks_pvalue=float(ks_pvalue),
    )


def day_of_week_rates(rows: list[RealResultRow]) -> tuple[dict[str, float], dict[str, int]]:
    """Per-weekday arrival rate (arrivals/day) for one group, using an exact
    occurrence count as the denominator rather than assuming every weekday
    occurs equally often: over a ~78-day window each weekday occurs 11 or 12
    times unevenly, so occurrences*24h would bias whichever weekdays happen
    to land the extra occurrence by several percent. day_of_week itself comes
    from the dataset's own day_received column (reliable); the calendar-day
    grouping used only to COUNT occurrences comes from floor(received_days),
    which is approximate since receipt timestamps aren't anchored to true
    midnight (see TODO.md) - a handful of rows near a day boundary could
    shift into a neighbouring bucket, biasing the occurrence count by at most
    one day per boundary, not the per-row weekday label itself."""

    day_for_calendar_day: dict[int, str] = {}
    counts_per_weekday: Counter = Counter()
    for r in rows:
        if r.day_of_week not in DAY_ORDER:
            continue
        calendar_day = int(np.floor(r.received_days))
        day_for_calendar_day[calendar_day] = r.day_of_week
        counts_per_weekday[r.day_of_week] += 1

    occurrences = Counter(day_for_calendar_day.values())
    rates = {
        day: (counts_per_weekday[day] / occurrences[day]) if occurrences.get(day) else 0.0
        for day in DAY_ORDER
    }
    return rates, {day: occurrences.get(day, 0) for day in DAY_ORDER}


def _weekday_of_calendar_day(calendar_day: int, anchor_day: int, anchor_weekday: str) -> str:
    offset = (calendar_day - anchor_day) % 7
    return DAY_ORDER[(DAY_ORDER.index(anchor_weekday) + offset) % 7]


def _integrate_rate(
    a: float, b: float, anchor_day: int, anchor_weekday: str, day_rates: dict[str, float]
) -> float:
    """Integral of the piecewise-constant day-of-week rate function between
    times a and b (in days), i.e. the NHPP compensator's value over [a, b) -
    the expected arrival count an NHPP with these rates would produce in that
    window. A bounded loop over the (small) number of calendar days [a, b)
    spans, rather than a closed form, since a gap can straddle a day (and
    therefore rate) boundary."""
    if b <= a:
        return 0.0
    first_day = int(np.floor(a))
    last_day = int(np.floor(b - 1e-12))
    total = 0.0
    cursor = a
    for day in range(first_day, last_day + 1):
        segment_end = min(day + 1, b)
        weekday = _weekday_of_calendar_day(day, anchor_day, anchor_weekday)
        total += day_rates[weekday] * (segment_end - cursor)
        cursor = segment_end
    return total


def time_rescale_gaps(
    rows: list[RealResultRow], day_rates: dict[str, float]
) -> tuple[np.ndarray, int]:
    """Applies the time-rescaling theorem: if arrivals truly follow an NHPP
    with rate day_rates(t), then integrating that rate over each inter-arrival
    gap yields i.i.d. Exp(1) intervals. Computed over the FULL sorted arrival
    sequence (not pre-filtered for ties/zero gaps, unlike
    interarrival_gaps_minutes) so the compensator is built over the real
    arrival sequence rather than one already biased by dropping some of it;
    returns the rescaled gaps together with a count of non-positive entries
    (arrival ties) the caller should drop before a K-S test."""

    valid_rows = [r for r in rows if r.day_of_week in DAY_ORDER]
    if len(valid_rows) < 2:
        return np.array([]), 0

    anchor_day = int(np.floor(valid_rows[0].received_days))
    anchor_weekday = valid_rows[0].day_of_week
    times = np.sort(np.array([r.received_days for r in valid_rows]))

    rescaled = np.array(
        [
            _integrate_rate(times[i - 1], times[i], anchor_day, anchor_weekday, day_rates)
            for i in range(1, len(times))
        ]
    )
    n_dropped = int(np.sum(rescaled <= 0))
    return rescaled, n_dropped


def index_of_dispersion(rows: list[RealResultRow], bucket_days: float = 1.0) -> float | None:
    """Variance-to-mean ratio of arrival counts in fixed daily bins - exactly
    1 in expectation for a homogeneous Poisson process at any binning, so a
    value well above 1 is a second, standard confirmation (alongside the
    day-of-week chi-square test) that arrivals are far from constant-rate,
    complementary to the gap-based K-S/Weibull checks above."""
    if len(rows) < 2:
        return None
    times = np.array([r.received_days for r in rows])
    t_min, t_max = float(times.min()), float(times.max())
    n_buckets = max(1, int(np.ceil((t_max - t_min) / bucket_days)))
    edges = t_min + np.arange(n_buckets + 1) * bucket_days
    counts, _ = np.histogram(times, bins=edges)
    if len(counts) < 2 or counts.mean() == 0:
        return None
    return float(counts.var(ddof=1) / counts.mean())


def nhpp_review(rows: list[RealResultRow], interarrival: InterarrivalFit) -> NHPPReview:
    day_rates, day_occurrences = day_of_week_rates(rows)
    raw_gaps = interarrival_gaps_minutes(rows)

    rescaled_all, n_dropped = time_rescale_gaps(rows, day_rates)
    rescaled = rescaled_all[rescaled_all > 0]
    if len(rescaled) >= 5:
        rescaled_ks_stat, rescaled_ks_pvalue = stats.kstest(rescaled, "expon", args=(0, 1))
        # Exp(1) here has no fitted parameters (k=0) - unlike the raw
        # exponential K-S/AIC, which fits its rate from the same data. The
        # two K-S stats therefore aren't strictly apples-to-apples (the raw
        # one is anti-conservative by comparison); the direction of the
        # comparison is still the informative part.
        rescaled_exp1_aic = _aic(stats.expon, (0, 1), rescaled, k=0)
    else:
        rescaled_ks_stat = rescaled_ks_pvalue = rescaled_exp1_aic = None

    return NHPPReview(
        day_rates_per_day=day_rates,
        day_occurrences=day_occurrences,
        raw_ks_stat=interarrival.ks_stat,
        raw_ks_pvalue=interarrival.ks_pvalue,
        raw_exponential_aic=interarrival.aic,
        rescaled_n=len(rescaled),
        rescaled_ties_dropped=n_dropped,
        rescaled_ks_stat=float(rescaled_ks_stat) if rescaled_ks_stat is not None else None,
        rescaled_ks_pvalue=float(rescaled_ks_pvalue) if rescaled_ks_pvalue is not None else None,
        rescaled_exp1_aic=rescaled_exp1_aic,
        raw_weibull=fit_weibull(raw_gaps),
        rescaled_weibull=fit_weibull(rescaled),
        index_of_dispersion=index_of_dispersion(rows),
    )


def _configured_organism_pct(config: SimulationConfig, sample_type: SampleType) -> dict[Organism, float]:
    weights = config.sample_type_profiles[sample_type].organism_weights
    total = sum(weights.values())
    if not total:
        return {}
    return {organism: 100 * w / total for organism, w in weights.items()}


def summarize_group(
    group: str, rows: list[RealResultRow], config: SimulationConfig
) -> GroupSummary:
    n_rows = len(rows)
    positive_rows = [r for r in rows if r.is_positive]
    negative_rows = [r for r in rows if not r.is_positive]
    n_positive = len(positive_rows)

    mapped = _MAPPED_TYPE_BY_GROUP.get(group)
    configured_mean = (
        config.sample_type_profiles[mapped].mean_interarrival_minutes if mapped else None
    )
    configured_positive_pct = (
        100 * config.sample_type_profiles[mapped].positive_probability if mapped else None
    )
    configured_organism_pct = _configured_organism_pct(config, mapped) if mapped else {}

    organism_counts = Counter(
        map_organism(r.organism_text) for r in positive_rows if r.organism_text
    )

    interarrival = fit_interarrival(rows, configured_mean)

    return GroupSummary(
        group=group,
        n_rows=n_rows,
        n_positive=n_positive,
        positive_pct=100 * n_positive / n_rows if n_rows else None,
        configured_positive_pct=configured_positive_pct,
        interarrival=interarrival,
        nhpp=nhpp_review(rows, interarrival),
        turnaround_all=fit_turnaround(np.array([r.turnaround_days * 24 for r in rows])),
        turnaround_positive=fit_turnaround(
            np.array([r.turnaround_days * 24 for r in positive_rows])
        ),
        turnaround_negative=fit_turnaround(
            np.array([r.turnaround_days * 24 for r in negative_rows])
        ),
        organism_counts=organism_counts,
        configured_organism_pct=configured_organism_pct,
    )


def summarize_all(
    rows: list[RealResultRow], config: SimulationConfig
) -> dict[str, GroupSummary]:
    from .load_real_data import rows_by_group

    grouped = rows_by_group(rows)
    return {
        group: summarize_group(group, grouped[group], config) for group in ANALYSIS_GROUPS
    }


def day_of_week_counts(rows: list[RealResultRow]) -> dict[str, int]:
    counts = Counter(r.day_of_week for r in rows if r.day_of_week in DAY_ORDER)
    return {day: counts.get(day, 0) for day in DAY_ORDER}
