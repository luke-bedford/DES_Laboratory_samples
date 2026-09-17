from lab_sim import SimulationConfig, plot_distribution_checks, run_simulation


def main() -> None:
    config = SimulationConfig()
    stats = run_simulation(config)
    stats.print_report()

    output_path = plot_distribution_checks(stats, config)
    print(f"Distribution checks saved to {output_path}")


if __name__ == "__main__":
    main()
