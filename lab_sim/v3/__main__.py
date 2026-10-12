"""Standalone entry point for model v3 - run via `python -m lab_sim.v3`
(top-level `main.py` delegates here). Writes diagnostics to
diagnostics/v3/, the module defaults for this version.
"""

import argparse

from .config import MODEL_VERSION, SimulationConfig
from .plotting import plot_distribution_checks, plot_stage_time_distributions
from .replications import (
    aggregate_queueing_replications,
    aggregate_replications,
    print_queueing_summary,
    print_replication_summary,
    run_replications,
)
from .report import render_html_report
from .simulation import run_simulation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run lab_sim model v3.")
    parser.add_argument(
        "--replications",
        type=int,
        default=100,
        help=(
            "Number of independent replications (varying only random_seed) to "
            "run for the report's mean + 95%% interval per metric. Pass 1 to "
            "skip replication entirely for fast iteration. Default: 100 - "
            "expect a correspondingly long run time."
        ),
    )
    args = parser.parse_args()

    print(f"=== Model {MODEL_VERSION} ===")
    config = SimulationConfig()
    stats = run_simulation(config)
    stats.print_report()

    output_path = plot_distribution_checks(stats, config)
    print(f"Distribution checks saved to {output_path}")

    stage_time_path = plot_stage_time_distributions(config)
    print(f"Stage time distribution plots saved to {stage_time_path}")

    replication_summary = None
    queueing_summary = None
    if args.replications > 1:
        print(f"Running {args.replications} replications for aggregate statistics...")
        summaries = run_replications(config, args.replications)
        replication_summary = aggregate_replications(summaries)
        print_replication_summary(replication_summary)
        queueing_summary = aggregate_queueing_replications(summaries)
        print_queueing_summary(queueing_summary)

    report_path = render_html_report(
        stats,
        config,
        replication_summary=replication_summary,
        queueing_summary=queueing_summary,
    )
    print(f"Summary report saved to {report_path}")


if __name__ == "__main__":
    main()
