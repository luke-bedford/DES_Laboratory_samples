import dataclasses

import numpy as np

from .config import SimulationConfig
from .simulation import run_simulation

# Metrics from StatsCollector.summary() that are meaningful to aggregate across
# replications - everything numeric except warmup_minutes and organism_counts,
# which are constant (a config echo) and a dict respectively, not a per-run
# random outcome.
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
