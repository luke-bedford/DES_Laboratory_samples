"""Standalone entry point for the frozen model-v0 snapshot - run via
`python -m lab_sim.v0`.

This file is new tooling, not part of the frozen model-v0 snapshot itself
(everything else in this package is a byte-for-byte copy of the model-v0
git tag - see lab_sim/CHANGES.md). It exists so v0 can be run side by
side with later versions without editing the frozen modules: v0's own
plotting.py/report.py still default their output_path to the flat
diagnostics/... path they had at the tag, so every call here passes
diagnostics/v0/... explicitly instead (see CHANGES.md's "Diagnostics
output convention"). v0 has no MODEL_VERSION constant - that constant
didn't exist at the tag - so the "Model v0" label below is a literal,
not an import.
"""

from .config import SimulationConfig
from .plotting import plot_distribution_checks, plot_stage_time_distributions
from .report import render_html_report
from .simulation import run_simulation


def main() -> None:
    print("=== Model v0 ===")
    config = SimulationConfig()
    stats = run_simulation(config)
    stats.print_report()

    output_path = plot_distribution_checks(
        stats, config, output_path="diagnostics/v0/distribution_checks.png"
    )
    print(f"Distribution checks saved to {output_path}")

    stage_time_path = plot_stage_time_distributions(
        config, output_path="diagnostics/v0/stage_time_distributions.png"
    )
    print(f"Stage time distribution plots saved to {stage_time_path}")

    report_path = render_html_report(
        stats, config, output_path="diagnostics/v0/summary_report.html"
    )
    print(f"Summary report saved to {report_path}")


if __name__ == "__main__":
    main()
