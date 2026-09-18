import os
from statistics import mean

from .config import SimulationConfig
from .entities import Sample, SampleType
from .stats import StatsCollector

# (display label, timestamp key marking the phase's start, timestamp key
# marking its end) - mirrors the sample.mark() calls in processes.py.
# Susceptibility-related phases are only ever marked on positive samples.
_PHASES: list[tuple[str, str, str]] = [
    ("Reception", "reception_start", "reception_end"),
    ("Accessioning", "accessioning_start", "accessioning_end"),
    ("Plating", "plating_start", "plating_end"),
    ("Primary incubation", "incubation_start", "incubation_end"),
    ("Reading", "reading_start", "reading_end"),
    ("Susceptibility setup", "susceptibility_setup_start", "susceptibility_setup_end"),
    ("Sensitivity incubation", "sensitivity_incubation_start", "sensitivity_incubation_end"),
    ("Sensitivity reading", "sensitivity_reading_start", "sensitivity_reading_end"),
    ("Result entry", "result_entry_start", "result_entry_end"),
    ("Verification", "verification_start", "reported"),
]

_SURFACE = "#fcfcfb"
_INK_PRIMARY = "#0b0b0b"
_INK_SECONDARY = "#52514e"
_INK_MUTED = "#898781"
_GRID = "#e1e0d9"
_BLUE = "#2a78d6"
_ORANGE = "#eb6834"


def _type_label(sample_type: SampleType) -> str:
    return sample_type.name.replace("_", " ").title()


def _phase_duration(sample: Sample, start_key: str, end_key: str) -> float | None:
    start = sample.timestamps.get(start_key)
    end = sample.timestamps.get(end_key)
    if start is None or end is None:
        return None
    return end - start


def _format_minutes(minutes: float | None) -> str:
    if minutes is None:
        return "—"
    if minutes >= 120:
        return f"{minutes / 60:.1f} h"
    return f"{minutes:.1f} min"


def _format_hours(hours: float | None) -> str:
    return "—" if hours is None else f"{hours:.1f} h"


def build_summary(stats: StatsCollector, config: SimulationConfig) -> dict:
    """Aggregates arrival counts, turnaround times, and per-phase durations
    by sample type from a finished run's StatsCollector."""

    sample_types = list(config.sample_type_profiles)

    counts = {}
    for sample_type in sample_types:
        arrived = sum(1 for s in stats.arrivals if s.sample_type is sample_type)
        completed = [s for s in stats.completed_samples if s.sample_type is sample_type]
        positive = sum(1 for s in completed if s.is_culture_positive)
        counts[sample_type] = {
            "arrived": arrived,
            "completed": len(completed),
            "positive": positive,
            "negative": len(completed) - positive,
        }

    turnaround = {}
    for sample_type in sample_types:
        hours = [
            t / 60.0
            for s in stats.completed_samples
            if s.sample_type is sample_type and (t := s.turnaround_time("reported")) is not None
        ]
        turnaround[sample_type] = {
            "n": len(hours),
            "mean_hours": mean(hours) if hours else None,
            "min_hours": min(hours) if hours else None,
            "max_hours": max(hours) if hours else None,
        }

    phase_durations = {}
    for sample_type in sample_types:
        completed = [s for s in stats.completed_samples if s.sample_type is sample_type]
        per_phase = {}
        for label, start_key, end_key in _PHASES:
            values = [
                d
                for s in completed
                if (d := _phase_duration(s, start_key, end_key)) is not None
            ]
            per_phase[label] = mean(values) if values else None
        phase_durations[sample_type] = per_phase

    return {
        "sample_types": sample_types,
        "counts": counts,
        "turnaround": turnaround,
        "phase_durations": phase_durations,
    }


def _counts_table(summary: dict) -> str:
    rows = []
    for sample_type in summary["sample_types"]:
        c = summary["counts"][sample_type]
        pct_positive = f"{100 * c['positive'] / c['completed']:.0f}%" if c["completed"] else "—"
        rows.append(
            f"<tr><td>{_type_label(sample_type)}</td><td>{c['arrived']}</td>"
            f"<td>{c['completed']}</td><td>{c['positive']}</td><td>{c['negative']}</td>"
            f"<td>{pct_positive}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Specimen type</th><th>Arrived</th><th>Completed</th>"
        "<th>Positive</th><th>Negative</th><th>% positive</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _turnaround_table(summary: dict) -> str:
    rows = []
    for sample_type in summary["sample_types"]:
        t = summary["turnaround"][sample_type]
        rows.append(
            f"<tr><td>{_type_label(sample_type)}</td><td>{t['n']}</td>"
            f"<td>{_format_hours(t['mean_hours'])}</td><td>{_format_hours(t['min_hours'])}</td>"
            f"<td>{_format_hours(t['max_hours'])}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Specimen type</th><th>Completed</th>"
        "<th>Mean turnaround</th><th>Min turnaround</th><th>Max turnaround</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _phase_table(summary: dict) -> str:
    phase_labels = [label for label, _, _ in _PHASES]
    header = "".join(f"<th>{label}</th>" for label in phase_labels)
    rows = []
    for sample_type in summary["sample_types"]:
        per_phase = summary["phase_durations"][sample_type]
        cells = "".join(f"<td>{_format_minutes(per_phase[label])}</td>" for label in phase_labels)
        rows.append(f"<tr><td>{_type_label(sample_type)}</td>{cells}</tr>")
    return (
        f"<table><thead><tr><th>Specimen type</th>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_html_report(
    stats: StatsCollector,
    config: SimulationConfig,
    output_path: str = "diagnostics/summary_report.html",
) -> str:
    """Renders arrival counts, turnaround times, and average per-phase
    durations, each broken down by sample type, to a standalone HTML file."""

    summary = build_summary(stats, config)
    overall = stats.summary()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Lab simulation summary</title>
<style>
  body {{
    font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    background: {_SURFACE};
    color: {_INK_PRIMARY};
    margin: 0;
    padding: 32px 24px;
  }}
  .wrap {{ max-width: 1000px; margin: 0 auto; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .subtitle {{ color: {_INK_SECONDARY}; margin-bottom: 24px; }}
  .run-meta {{
    display: flex; flex-wrap: wrap; gap: 24px;
    margin-bottom: 32px; padding: 16px 20px;
    background: #fff; border: 1px solid {_GRID}; border-radius: 8px;
  }}
  .run-meta div {{ min-width: 140px; }}
  .run-meta .label {{ color: {_INK_MUTED}; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; }}
  .run-meta .value {{ font-size: 1.15rem; font-weight: 600; }}
  h2 {{ font-size: 1.05rem; margin: 32px 0 10px; color: {_INK_PRIMARY}; }}
  table {{
    width: 100%; border-collapse: collapse; background: #fff;
    border: 1px solid {_GRID}; border-radius: 8px; overflow: hidden;
    font-size: 0.88rem;
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
  <h1>Lab simulation summary</h1>
  <div class="subtitle">Generated from a {config.sim_duration_minutes / 60 / 24:.1f}-day run (seed {config.random_seed})</div>

  <div class="run-meta">
    <div><div class="label">Arrived</div><div class="value">{len(stats.arrivals)}</div></div>
    <div><div class="label">Completed</div><div class="value">{overall['samples_completed']}</div></div>
    <div><div class="label">Positive</div><div class="value">{overall['samples_positive']}</div></div>
    <div><div class="label">Rejected</div><div class="value">{overall['samples_rejected']}</div></div>
    <div><div class="label">Mean turnaround</div><div class="value">{overall['mean_turnaround_minutes'] / 60:.1f} h</div></div>
  </div>

  <h2>Samples by specimen type</h2>
  <div class="table-scroll">{_counts_table(summary)}</div>

  <h2>Turnaround time by specimen type</h2>
  <div class="table-scroll">{_turnaround_table(summary)}</div>

  <h2>Average phase duration by specimen type</h2>
  <p class="subtitle" style="margin-top:-4px;">Susceptibility-related phases only apply to positive samples; a dash means no completed sample of that type reached that phase.</p>
  <div class="table-scroll">{_phase_table(summary)}</div>

  <footer>lab_sim.report.render_html_report &middot; {overall['samples_completed']} completed samples analyzed</footer>
</div>
</body>
</html>
"""

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
