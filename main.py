from lab_sim import (
    SimulationConfig,
    plot_distribution_checks,
    plot_stage_time_distributions,
    render_html_report,
    run_simulation,
)


def main() -> None:
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
