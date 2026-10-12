import dataclasses

import numpy as np

from .config import SimulationConfig
from .entities import SampleType
from .simulation import run_simulation

# Metrics from StatsCollector.summary() that are meaningful to aggregate across
# replications - everything numeric except warmup_minutes, organism_counts,
# and queueing, which are a constant (a config echo), a dict, and a nested
# dict respectively, not a flat per-run random outcome. queueing has its own
# aggregator (aggregate_queueing_replications) below, since its per-sample-
# type breakdown needs per-key NaN-handling that a flat scalar doesn't.
_AGGREGATE_METRICS = [
    "samples_arrived",
    "samples_completed",
    "samples_rejected",
    "samples_positive",
    "mean_turnaround_minutes",
    "max_turnaround_minutes",
    "min_turnaround_minutes",
    "arrivals_during_warmup",
    "completions_during_warmup",
]


def run_replications(config: SimulationConfig, n_replications: int) -> list[dict]:
    """Runs `run_simulation` `n_replications` times, each an independent
    replication of the same config except for `random_seed` (config.random_seed
    + 0, + 1, ...), and collects each run's `StatsCollector.summary()`."""

    summaries = []
    for i in range(n_replications):
        run_config = dataclasses.replace(config, random_seed=config.random_seed + i)
        stats = run_simulation(run_config)
        summaries.append(stats.summary())
    return summaries


def aggregate_replications(summaries: list[dict]) -> dict:
    """Aggregates a list of StatsCollector.summary() dicts - one per
    independent replication - into a mean and an empirical 95% interval
    (2.5th/97.5th percentile across replications) per metric. This is the
    standard discrete-event-simulation "method of replications" approach to
    quantifying run-to-run variability, not a Bayesian credible interval -
    there's no posterior here, just repeated independent samples."""

    metrics = {}
    for key in _AGGREGATE_METRICS:
        values = np.array([s[key] for s in summaries], dtype=float)
        metrics[key] = {
            "mean": float(values.mean()),
            "ci_low": float(np.percentile(values, 2.5)),
            "ci_high": float(np.percentile(values, 97.5)),
        }

    return {"n_replications": len(summaries), "metrics": metrics}


def print_replication_summary(aggregate: dict) -> None:
    print(f"=== Replication Summary ({aggregate['n_replications']} runs) ===")
    for key, m in aggregate["metrics"].items():
        print(f"{key}: mean={m['mean']:.2f}  95% interval=[{m['ci_low']:.2f}, {m['ci_high']:.2f}]")


def _aggregate_queueing_node(summaries: list[dict], path: tuple[str, ...]) -> dict:
    """Aggregates one StatsCollector.queueing_summary() node (either a
    by_type[name] entry or the overall entry) across replications. A
    replication where that node had zero completions (mean_minutes is None
    - see StatsCollector.queueing_summary) contributes no observation to the
    mean/interval, via NaN + nanmean/nanpercentile, rather than biasing the
    distribution toward zero the way a 0.0 placeholder would."""

    means = []
    completions = []
    for s in summaries:
        node = s["queueing"]
        for key in path:
            node = node[key]
        means.append(node["mean_minutes"] if node["mean_minutes"] is not None else float("nan"))
        completions.append(node["n"])

    values = np.array(means, dtype=float)
    has_data = ~np.isnan(values)

    return {
        "n_replications_with_completions": int(has_data.sum()),
        "mean_completions_per_replication": float(np.mean(completions)),
        "mean_minutes": float(np.nanmean(values)) if has_data.any() else float("nan"),
        "ci_low_minutes": float(np.nanpercentile(values, 2.5)) if has_data.any() else float("nan"),
        "ci_high_minutes": float(np.nanpercentile(values, 97.5)) if has_data.any() else float("nan"),
    }


def aggregate_queueing_replications(summaries: list[dict]) -> dict:
    """Aggregates each replication's StatsCollector.queueing_summary() - the
    mean total queueing wait (see stats.total_queue_wait_minutes) per
    sample type and for the whole cohort - into a mean and empirical 95%
    interval across replications, the same method-of-replications approach
    as aggregate_replications. Each replication's own mean is treated as one
    observation (consistent with how aggregate_replications already treats
    e.g. mean_turnaround_minutes); samples are not pooled across
    replications, which would understate run-to-run variability."""

    by_type = {
        sample_type.name: _aggregate_queueing_node(summaries, ("by_type", sample_type.name))
        for sample_type in SampleType
    }
    overall = _aggregate_queueing_node(summaries, ("overall",))

    return {"n_replications": len(summaries), "by_type": by_type, "overall": overall}


def print_queueing_summary(aggregate: dict) -> None:
    print(f"=== Queueing Summary ({aggregate['n_replications']} runs) ===")
    for type_name, m in aggregate["by_type"].items():
        if m["n_replications_with_completions"] == 0:
            print(f"{type_name}: no completions in any replication")
            continue
        print(
            f"{type_name}: mean={m['mean_minutes']:.2f} min  "
            f"95% interval=[{m['ci_low_minutes']:.2f}, {m['ci_high_minutes']:.2f}]  "
            f"(~{m['mean_completions_per_replication']:.1f} completions/replication)"
        )
    overall = aggregate["overall"]
    print(
        f"ALL SAMPLES: mean={overall['mean_minutes']:.2f} min  "
        f"95% interval=[{overall['ci_low_minutes']:.2f}, {overall['ci_high_minutes']:.2f}]"
    )
