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
class GroupSummary:
    group: str
    n_rows: int
    n_positive: int
    positive_pct: float | None
    configured_positive_pct: float | None
    interarrival: InterarrivalFit
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
    )


def _aic(dist, params: tuple, data: np.ndarray) -> float:
    loglik = float(np.sum(dist.logpdf(data, *params)))
    return 2 * len(params) - 2 * loglik


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

    return GroupSummary(
        group=group,
        n_rows=n_rows,
        n_positive=n_positive,
        positive_pct=100 * n_positive / n_rows if n_rows else None,
        configured_positive_pct=configured_positive_pct,
        interarrival=fit_interarrival(rows, configured_mean),
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
