"""Renders the real-data distribution-fit analysis to a standalone HTML
report. Visual style duplicated from lab_sim/report.py rather than imported
(same precedent that module already set for lab_sim/plotting.py's palette).
"""

import os

from lab_sim.entities import Organism
from .distribution_fits import GroupSummary
from .load_real_data import ANALYSIS_GROUPS

_SURFACE = "#fcfcfb"
_INK_PRIMARY = "#0b0b0b"
_INK_SECONDARY = "#52514e"
_INK_MUTED = "#898781"
_GRID = "#e1e0d9"


def _group_label(group: str) -> str:
    return group.replace("_", " ").title()


def _fmt(value: float | None, digits: int = 1, suffix: str = "") -> str:
    return "—" if value is None else f"{value:.{digits}f}{suffix}"


def _fmt_minutes(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 120:
        return f"{value / 60:.1f} h"
    return f"{value:.1f} min"


def _interarrival_table(summaries: dict[str, GroupSummary]) -> str:
    rows = []
    for group in ANALYSIS_GROUPS:
        fit = summaries[group].interarrival
        ks = f"{fit.ks_stat:.3f} (p={fit.ks_pvalue:.3f})" if fit.ks_stat is not None else "—"
        rows.append(
            f"<tr><td>{_group_label(group)}</td><td>{fit.n_gaps}</td>"
            f"<td>{_fmt_minutes(fit.real_mean_minutes)}</td>"
            f"<td>{_fmt_minutes(fit.configured_mean_minutes)}</td>"
            f"<td>{ks}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Group</th><th>Gaps (n)</th>"
        "<th>Real mean inter-arrival</th><th>Configured mean</th>"
        "<th>K-S stat vs. exponential</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _turnaround_table(summaries: dict[str, GroupSummary]) -> str:
    rows = []
    for group in ANALYSIS_GROUPS:
        fit = summaries[group].turnaround_all
        best = f"{fit.best_dist} {tuple(round(float(p), 2) for p in fit.best_params)}" if fit.best_dist else "—"
        ks = f"{fit.best_ks_stat:.3f} (p={fit.best_ks_pvalue:.3f})" if fit.best_ks_stat is not None else "—"
        rows.append(
            f"<tr><td>{_group_label(group)}</td><td>{fit.n}</td>"
            f"<td>{_fmt(fit.mean_hours)} h</td><td>{_fmt(fit.median_hours)} h</td>"
            f"<td>{best}</td><td>{ks}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Group</th><th>Completed (n)</th>"
        "<th>Mean</th><th>Median</th><th>Best-fit distribution (AIC-selected)</th>"
        "<th>K-S stat vs. best fit</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _turnaround_by_positivity_table(summaries: dict[str, GroupSummary]) -> str:
    rows = []
    for group in ANALYSIS_GROUPS:
        s = summaries[group]
        pos, neg = s.turnaround_positive, s.turnaround_negative
        rows.append(
            f"<tr><td>{_group_label(group)}</td>"
            f"<td>{pos.n}</td><td>{_fmt(pos.mean_hours)} h</td><td>{_fmt(pos.median_hours)} h</td>"
            f"<td>{neg.n}</td><td>{_fmt(neg.mean_hours)} h</td><td>{_fmt(neg.median_hours)} h</td></tr>"
        )
    return (
        "<table><thead><tr><th>Group</th>"
        "<th>Positive (n)</th><th>Positive mean</th><th>Positive median</th>"
        "<th>Negative (n)</th><th>Negative mean</th><th>Negative median</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _positivity_table(summaries: dict[str, GroupSummary]) -> str:
    rows = []
    for group in ANALYSIS_GROUPS:
        s = summaries[group]
        configured = f"{s.configured_positive_pct:.1f}%" if s.configured_positive_pct is not None else "—"
        rows.append(
            f"<tr><td>{_group_label(group)}</td><td>{s.n_rows}</td><td>{s.n_positive}</td>"
            f"<td>{_fmt(s.positive_pct, suffix='%')}</td><td>{configured}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Group</th><th>Rows (n)</th><th>Positive (n)</th>"
        "<th>Real % positive</th><th>Configured % positive</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _organism_table(summaries: dict[str, GroupSummary]) -> str:
    rows = []
    for group in ANALYSIS_GROUPS:
        s = summaries[group]
        total_positive = sum(s.organism_counts.values())
        if not total_positive and not s.configured_organism_pct:
            continue
        organisms = sorted(
            set(s.organism_counts) | set(s.configured_organism_pct),
            key=lambda o: -s.organism_counts.get(o, 0),
        )
        for organism in organisms:
            real_pct = 100 * s.organism_counts.get(organism, 0) / total_positive if total_positive else None
            configured_pct = s.configured_organism_pct.get(organism)
            rows.append(
                f"<tr><td>{_group_label(group)}</td><td>{organism.name.replace('_', ' ').title()}</td>"
                f"<td>{s.organism_counts.get(organism, 0)}</td>"
                f"<td>{_fmt(real_pct, suffix='%')}</td>"
                f"<td>{_fmt(configured_pct, suffix='%') if configured_pct is not None else '—'}</td></tr>"
            )
    return (
        "<table><thead><tr><th>Group</th><th>Organism</th><th>Real count</th>"
        "<th>Real % of positives</th><th>Configured %</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _day_of_week_table(day_counts: dict[str, int]) -> str:
    total = sum(day_counts.values())
    rows = [
        f"<tr><td>{day}</td><td>{count}</td><td>{_fmt(100 * count / total, 0, '%') if total else '—'}</td></tr>"
        for day, count in day_counts.items()
    ]
    return (
        "<table><thead><tr><th>Day received</th><th>Rows</th><th>%</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _unmapped_types_table(unmapped: dict[str, int]) -> str:
    rows = [f"<tr><td>{name}</td><td>{count}</td></tr>" for name, count in unmapped.items()]
    return (
        "<table><thead><tr><th>Specimen type</th><th>Rows</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_html_report(
    summaries: dict[str, GroupSummary],
    day_counts: dict[str, int],
    unmapped: dict[str, int],
    total_rows: int,
    span_days: float,
    output_path: str = "diagnostics/real_data_fit_report.html",
) -> str:
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Real data distribution fits</title>
<style>
  body {{
    font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    background: {_SURFACE};
    color: {_INK_PRIMARY};
    margin: 0;
    padding: 32px 24px;
  }}
  .wrap {{ max-width: 1100px; margin: 0 auto; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .subtitle {{ color: {_INK_SECONDARY}; margin-bottom: 24px; }}
  h2 {{ font-size: 1.05rem; margin: 32px 0 10px; color: {_INK_PRIMARY}; }}
  table {{
    width: 100%; border-collapse: collapse; background: #fff;
    border: 1px solid {_GRID}; border-radius: 8px; overflow: hidden;
    font-size: 0.85rem;
  }}
  th, td {{ padding: 8px 12px; text-align: right; border-bottom: 1px solid {_GRID}; white-space: nowrap; }}
  th:first-child, td:first-child {{ text-align: left; }}
  thead th {{ color: {_INK_SECONDARY}; font-weight: 600; background: #f5f4f1; }}
  tbody tr:last-child td {{ border-bottom: none; }}
  tbody tr:hover {{ background: #f9f8f5; }}
  .table-scroll {{ overflow-x: auto; }}
  footer {{ margin-top: 32px; color: {_INK_MUTED}; font-size: 0.8rem; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Real data vs. simulation assumptions</h1>
  <div class="subtitle">
    {total_rows} rows from Data/Received_sample_data, spanning {span_days:.1f} days.
    "Real data" analysis only - nothing here has been written back to lab_sim/config.py.
    Turnaround here is receipt-to-verification only; the dataset has no per-stage
    timestamps, so individual process-stage assumptions (reception, plating, incubation,
    ...) can't be validated, only the aggregate shape.
  </div>

  <h2>Inter-arrival fit (Poisson-arrival assumption)</h2>
  <p class="subtitle" style="margin-top:-4px;">Real mean inter-arrival vs. the configured SampleTypeProfile mean, and a K-S test against an exponential distribution fitted to the real gaps. A low K-S stat / high p-value supports the exponential (Poisson-arrival) assumption.</p>
  <div class="table-scroll">{_interarrival_table(summaries)}</div>

  <h2>Turnaround time fit (aggregate shape)</h2>
  <p class="subtitle" style="margin-top:-4px;">Best-fit distribution among normal/lognormal/gamma, selected by AIC, fitted to receipt-to-verification time pooled across positive and negative results.</p>
  <div class="table-scroll">{_turnaround_table(summaries)}</div>

  <h2>Turnaround time: positive vs. negative</h2>
  <div class="table-scroll">{_turnaround_by_positivity_table(summaries)}</div>

  <h2>Positivity rate: real vs. configured</h2>
  <div class="table-scroll">{_positivity_table(summaries)}</div>

  <h2>Organism mix: real vs. configured</h2>
  <p class="subtitle" style="margin-top:-4px;">Real organism text is matched to the model's Organism enum by substring (see analysis/organism_mapping.py); anything unmatched falls under Other.</p>
  <div class="table-scroll">{_organism_table(summaries)}</div>

  <h2>Arrivals by day of week</h2>
  <p class="subtitle" style="margin-top:-4px;">The simulation's arrival process is constant-rate Poisson with no day-of-week variation; this table is descriptive only.</p>
  <div class="table-scroll">{_day_of_week_table(day_counts)}</div>

  <h2>Specimen types not yet modeled</h2>
  <p class="subtitle" style="margin-top:-4px;">Present in the real data but not in SampleType and not analyzed above.</p>
  <div class="table-scroll">{_unmapped_types_table(unmapped)}</div>

  <footer>analysis.report.render_html_report</footer>
</div>
</body>
</html>
"""

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
