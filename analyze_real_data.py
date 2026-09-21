from lab_sim import SimulationConfig

from analysis.distribution_fits import day_of_week_counts, summarize_all
from analysis.load_real_data import DEFAULT_DATA_PATH, load_rows, unmapped_type_counts
from analysis.plots import render_distribution_plots
from analysis.report import render_html_report


def main() -> None:
    rows = load_rows(DEFAULT_DATA_PATH)
    config = SimulationConfig()

    summaries = summarize_all(rows, config)
    day_counts = day_of_week_counts(rows)
    unmapped = unmapped_type_counts(rows)
    span_days = max(r.received_days for r in rows) - min(r.received_days for r in rows)

    print(f"Loaded {len(rows)} rows from {DEFAULT_DATA_PATH}, spanning {span_days:.1f} days.")
    for group, summary in summaries.items():
        print(
            f"{group}: n={summary.n_rows} positive={summary.n_positive} "
            f"({summary.positive_pct:.1f}%)" if summary.positive_pct is not None else
            f"{group}: n={summary.n_rows} positive={summary.n_positive}"
        )

    plot_path = render_distribution_plots(rows, summaries)
    print(f"Distribution-fit plots saved to {plot_path}")

    report_path = render_html_report(
        summaries, day_counts, unmapped, len(rows), span_days
    )
    print(f"Fit report saved to {report_path}")


if __name__ == "__main__":
    main()
