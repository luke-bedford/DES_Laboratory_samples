"""Standalone entry point for model v2 - run via `python -m lab_sim.v2`
(top-level `main.py` delegates here). Writes diagnostics to
diagnostics/v2/, the module defaults for this version.
"""

from .config import MODEL_VERSION, SimulationConfig
from .plotting import plot_distribution_checks, plot_stage_time_distributions
from .report import render_html_report
from .simulation import run_simulation


def main() -> None:
    print(f"=== Model {MODEL_VERSION} ===")
    config = SimulationConfig()
    stats = run_simulation(config)
    stats.print_report()

    output_path = plot_distribution_checks(stats, config)
    print(f"Distribution checks saved to {output_path}")

    stage_time_path = plot_stage_time_distributions(config)
    print(f"Stage time distribution plots saved to {stage_time_path}")

    report_path = render_html_report(stats, config)
    print(f"Summary report saved to {report_path}")


if __name__ == "__main__":
    main()
