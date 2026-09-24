import os
from statistics import mean, median

from .config import MODEL_VERSION, SimulationConfig
from .entities import Gender, Sample, SampleType
from .plotting import stage_time_params
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
    observed_arrivals = stats.observed_arrivals()
    observed_completions = stats.observed_completions()

    counts = {}
    for sample_type in sample_types:
        arrived = sum(1 for s in observed_arrivals if s.sample_type is sample_type)
        completed = [s for s in observed_completions if s.sample_type is sample_type]
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
            for s in observed_completions
            if s.sample_type is sample_type and (t := s.turnaround_time("reported")) is not None
        ]
        turnaround[sample_type] = {
            "n": len(hours),
            "mean_hours": mean(hours) if hours else None,
            "min_hours": min(hours) if hours else None,
            "max_hours": max(hours) if hours else None,
        }

    turnaround_by_positivity = {}
    for is_positive in (True, False):
        hours = [
            t / 60.0
            for s in observed_completions
            if s.is_culture_positive is is_positive
            and (t := s.turnaround_time("reported")) is not None
        ]
        turnaround_by_positivity[is_positive] = {
            "n": len(hours),
            "mean_hours": mean(hours) if hours else None,
            "median_hours": median(hours) if hours else None,
            "min_hours": min(hours) if hours else None,
            "max_hours": max(hours) if hours else None,
        }

    # One patient per sample (see Background/v2/Microbiology Context), so
    # demographics are read off the observed arrivals' patients directly.
    patients = [s.patient for s in observed_arrivals]
    ages = [p.age for p in patients]
    n_patients = len(patients)
    age_bands = {
        "young": sum(1 for a in ages if a <= config.young_age_threshold),
        "elderly": sum(1 for a in ages if a >= config.elderly_age_threshold),
    }
    age_bands["adult"] = n_patients - age_bands["young"] - age_bands["elderly"]
    demographics = {
        "n": n_patients,
        "gender_counts": {
            gender: sum(1 for p in patients if p.gender is gender) for gender in Gender
        },
        "age_mean": mean(ages) if ages else None,
        "age_median": median(ages) if ages else None,
        "age_min": min(ages) if ages else None,
        "age_max": max(ages) if ages else None,
        "age_bands": age_bands,
    }

    phase_durations = {}
    for sample_type in sample_types:
        completed = [s for s in observed_completions if s.sample_type is sample_type]
        per_phase = {}
        for label, start_key, end_key in _PHASES:
            values = [
                d
                for s in completed
                if (d := _phase_duration(s, start_key, end_key)) is not None
            ]
            per_phase[label] = mean(values) if values else None
        phase_durations[sample_type] = per_phase

    phase_durations_by_positivity = {}
    for is_positive in (True, False):
        completed = [s for s in observed_completions if s.is_culture_positive is is_positive]
        per_phase = {}
        for label, start_key, end_key in _PHASES:
            values = [
                d
                for s in completed
                if (d := _phase_duration(s, start_key, end_key)) is not None
            ]
            per_phase[label] = mean(values) if values else None
        phase_durations_by_positivity[is_positive] = {
            "n": len(completed),
            "phases": per_phase,
        }

    return {
        "sample_types": sample_types,
        "counts": counts,
        "turnaround": turnaround,
        "turnaround_by_positivity": turnaround_by_positivity,
        "phase_durations": phase_durations,
        "phase_durations_by_positivity": phase_durations_by_positivity,
        "demographics": demographics,
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


def _turnaround_by_positivity_table(summary: dict) -> str:
    rows = []
    for is_positive, row_label in ((True, "Culture positive"), (False, "Culture negative")):
        t = summary["turnaround_by_positivity"][is_positive]
        rows.append(
            f"<tr><td>{row_label}</td><td>{t['n']}</td>"
            f"<td>{_format_hours(t['mean_hours'])}</td><td>{_format_hours(t['median_hours'])}</td>"
            f"<td>{_format_hours(t['min_hours'])}</td><td>{_format_hours(t['max_hours'])}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Culture result</th><th>Completed</th>"
        "<th>Mean turnaround</th><th>Median turnaround</th><th>Min turnaround</th>"
        "<th>Max turnaround</th></tr></thead>"
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


def _phase_by_positivity_table(summary: dict) -> str:
    phase_labels = [label for label, _, _ in _PHASES]
    header = "".join(f"<th>{label}</th>" for label in phase_labels)
    rows = []
    for is_positive, row_label in ((True, "Culture positive"), (False, "Culture negative")):
        group = summary["phase_durations_by_positivity"][is_positive]
        cells = "".join(
            f"<td>{_format_minutes(group['phases'][label])}</td>" for label in phase_labels
        )
        rows.append(f"<tr><td>{row_label} ({group['n']})</td>{cells}</tr>")
    return (
        f"<table><thead><tr><th>Culture result</th>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _gender_table(summary: dict) -> str:
    d = summary["demographics"]
    rows = []
    for gender, count in d["gender_counts"].items():
        pct = f"{100 * count / d['n']:.0f}%" if d["n"] else "—"
        rows.append(f"<tr><td>{gender.name.title()}</td><td>{count}</td><td>{pct}</td></tr>")
    return (
        "<table><thead><tr><th>Gender</th><th>Patients</th><th>%</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _age_summary_table(summary: dict) -> str:
    d = summary["demographics"]

    def _age(value: float | None) -> str:
        return "—" if value is None else f"{value:.0f}"

    rows = [
        f"<tr><td>Mean</td><td>{_age(d['age_mean'])}</td></tr>",
        f"<tr><td>Median</td><td>{_age(d['age_median'])}</td></tr>",
        f"<tr><td>Min</td><td>{_age(d['age_min'])}</td></tr>",
        f"<tr><td>Max</td><td>{_age(d['age_max'])}</td></tr>",
    ]
    return (
        "<table><thead><tr><th>Age</th><th>Years</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _age_band_table(summary: dict, config: SimulationConfig) -> str:
    d = summary["demographics"]
    n = d["n"]

    def _pct(count: int) -> str:
        return f"{100 * count / n:.0f}%" if n else "—"

    bands = [
        (f"Young (≤ {config.young_age_threshold:.0f})", d["age_bands"]["young"]),
        ("Adult", d["age_bands"]["adult"]),
        (f"Elderly (≥ {config.elderly_age_threshold:.0f})", d["age_bands"]["elderly"]),
    ]
    rows = [
        f"<tr><td>{label}</td><td>{count}</td><td>{_pct(count)}</td></tr>"
        for label, count in bands
    ]
    return (
        "<table><thead><tr><th>Age band</th><th>Patients</th><th>%</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _stage_time_table(config: SimulationConfig) -> str:
    rows = []
    for p in stage_time_params(config):
        clip = f"{p['floor_clip_pct']:.2f}%" if p["floor_clip_pct"] >= 0.005 else "~0%"
        rows.append(
            f"<tr><td>{p['label']}</td><td>{_format_minutes(p['mean_minutes'])}</td>"
            f"<td>{_format_minutes(p['stdev_minutes'])}</td><td>{clip}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Stage</th><th>Mean</th><th>Stdev</th>"
        "<th>% of draws below the 0.1 min floor</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_html_report(
    stats: StatsCollector,
    config: SimulationConfig,
    output_path: str = "diagnostics/v2/summary_report.html",
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
  .demo-grid {{ display: flex; flex-wrap: wrap; gap: 24px; }}
  .demo-grid > div {{ flex: 1; min-width: 220px; }}
  .demo-grid .label {{ color: {_INK_MUTED}; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 6px; }}
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
  <h1>Lab simulation summary <span style="color:{_INK_MUTED}; font-weight:400;">&middot; model {MODEL_VERSION}</span></h1>
  <div class="subtitle">
    {config.warmup_minutes / 60 / 24:.1f}-day warm-up (not recorded) followed by a
    {config.sim_duration_minutes / 60 / 24:.1f}-day observation window (seed {config.random_seed})
  </div>

  <div class="run-meta">
    <div><div class="label">Arrived</div><div class="value">{overall['samples_arrived']}</div></div>
    <div><div class="label">Completed</div><div class="value">{overall['samples_completed']}</div></div>
    <div><div class="label">Positive</div><div class="value">{overall['samples_positive']}</div></div>
    <div><div class="label">Rejected</div><div class="value">{overall['samples_rejected']}</div></div>
    <div><div class="label">Mean turnaround</div><div class="value">{overall['mean_turnaround_minutes'] / 60:.1f} h</div></div>
  </div>

  <h2>Samples by specimen type</h2>
  <p class="subtitle" style="margin-top:-4px;">Arrived and Completed are independent cohorts - a sample can complete in the observation window without having arrived in it (it arrived during warm-up), or vice versa (it's still mid-pipeline at run end).</p>
  <div class="table-scroll">{_counts_table(summary)}</div>

  <h2>Patient demographics</h2>
  <p class="subtitle" style="margin-top:-4px;">One patient per arrived sample (see Background/v2/Microbiology Context); age bands use the thresholds that modulate positivity (config.young_age_threshold / elderly_age_threshold).</p>
  <div class="demo-grid">
    <div><div class="label">By gender</div>{_gender_table(summary)}</div>
    <div><div class="label">Age summary</div>{_age_summary_table(summary)}</div>
    <div><div class="label">By age band</div>{_age_band_table(summary, config)}</div>
  </div>

  <h2>Turnaround time by specimen type</h2>
  <div class="table-scroll">{_turnaround_table(summary)}</div>

  <h2>Turnaround time: culture positive vs. culture negative</h2>
  <p class="subtitle" style="margin-top:-4px;">Median is shown alongside the mean as a check: turnaround is a sum of mostly-Gaussian stage durations, so absent heavy queueing it should be roughly symmetric and the two should track each other. If they diverge noticeably, the mean is being pulled by a skewed tail (e.g. queueing delay) and the median is the more representative figure.</p>
  <div class="table-scroll">{_turnaround_by_positivity_table(summary)}</div>

  <h2>Average phase duration by specimen type</h2>
  <p class="subtitle" style="margin-top:-4px;">Susceptibility-related phases only apply to positive samples; a dash means no completed sample of that type reached that phase.</p>
  <div class="table-scroll">{_phase_table(summary)}</div>

  <h2>Average phase duration: culture positive vs. culture negative</h2>
  <p class="subtitle" style="margin-top:-4px;">Pooled across all specimen types. Negative samples never reach the susceptibility-related phases, so those are shown as a dash.</p>
  <div class="table-scroll">{_phase_by_positivity_table(summary)}</div>

  <h2>Appendix: lab stage service-time parameters</h2>
  <p class="subtitle" style="margin-top:-4px;">The parameters behind every phase-duration figure above: each stage's duration is drawn independently from a Gaussian (<code>random.gauss(mean, stdev)</code>, floored at 0.1 minutes in <code>processes.py</code>'s <code>_duration</code>), the same for every sample type and culture outcome. Configured in <code>SimulationConfig</code> (<code>config.py</code>).</p>
  <div class="table-scroll">{_stage_time_table(config)}</div>
  <img src="stage_time_distributions.png" alt="Lab stage service-time distributions" style="max-width:100%; margin-top:14px; border:1px solid {_GRID}; border-radius: 8px;">

  <footer>lab_sim.report.render_html_report &middot; {overall['samples_completed']} completed samples analyzed</footer>
</div>
</body>
</html>
"""

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
