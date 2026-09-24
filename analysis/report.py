"""Renders the real-data distribution-fit analysis to a standalone HTML
report. Visual style duplicated from lab_sim/v2/report.py rather than imported
(same precedent that module already set for lab_sim/v2/plotting.py's palette).
"""

import os

from lab_sim.v2.entities import Organism
from .distribution_fits import DAY_ORDER, GroupSummary
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


def _day_rate_table(summaries: dict[str, GroupSummary]) -> str:
    header = "".join(f"<th>{day[:3]}</th>" for day in DAY_ORDER)
    rows = []
    for group in ANALYSIS_GROUPS:
        rates = summaries[group].nhpp.day_rates_per_day
        cells = "".join(f"<td>{_fmt(rates.get(day))}</td>" for day in DAY_ORDER)
        rows.append(f"<tr><td>{_group_label(group)}</td>{cells}</tr>")
    return (
        f"<table><thead><tr><th>Group</th>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _hour_rate_table(summaries: dict[str, GroupSummary]) -> str:
    """One row per group, arrivals/hour-slot averaged across the 7 weekdays
    for each hour - a compact, scannable shape (24 columns) rather than the
    full 168-cell (weekday, hour) grid the K-S/Weibull checks below actually
    use."""
    header = "".join(f"<th>{h:02d}</th>" for h in range(24))
    rows = []
    for group in ANALYSIS_GROUPS:
        hour_rates = summaries[group].nhpp.hour_rates_per_hour
        cells = []
        for h in range(24):
            pooled = sum(hour_rates.get((day, h), 0.0) for day in DAY_ORDER) / 7
            cells.append(f"<td>{_fmt(pooled, digits=2)}</td>")
        rows.append(f"<tr><td>{_group_label(group)}</td>{''.join(cells)}</tr>")
    return (
        f"<table><thead><tr><th>Group</th>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _nhpp_ks_table(summaries: dict[str, GroupSummary]) -> str:
    rows = []
    for group in ANALYSIS_GROUPS:
        n = summaries[group].nhpp
        raw = f"{n.raw_ks_stat:.3f}" if n.raw_ks_stat is not None else "—"
        rescaled = f"{n.rescaled_ks_stat:.3f}" if n.rescaled_ks_stat is not None else "—"
        hour_rescaled = f"{n.hour_rescaled_ks_stat:.3f}" if n.hour_rescaled_ks_stat is not None else "—"
        rows.append(
            f"<tr><td>{_group_label(group)}</td><td>{raw}</td><td>{rescaled}</td>"
            f"<td>{hour_rescaled}</td><td>{n.hour_rescaled_ties_dropped}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Group</th>"
        "<th>Raw K-S vs. exponential (fitted rate)</th>"
        "<th>Day-of-week-rescaled K-S vs. Exp(1)</th>"
        "<th>Day+hour-rescaled K-S vs. Exp(1)</th>"
        "<th>Ties dropped (day+hour)</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _weibull_table(summaries: dict[str, GroupSummary]) -> str:
    rows = []
    for group in ANALYSIS_GROUPS:
        n = summaries[group].nhpp
        raw_w, res_w, hour_w = n.raw_weibull, n.rescaled_weibull, n.hour_weibull
        raw_shape = f"{raw_w.shape:.2f}" if raw_w.shape is not None else "—"
        res_shape = f"{res_w.shape:.2f}" if res_w.shape is not None else "—"
        hour_shape = f"{hour_w.shape:.2f}" if hour_w.shape is not None else "—"
        raw_delta = (
            f"{n.raw_exponential_aic - raw_w.aic:,.0f}"
            if n.raw_exponential_aic is not None and raw_w.aic is not None
            else "—"
        )
        res_delta = (
            f"{n.rescaled_exp1_aic - res_w.aic:,.0f}"
            if n.rescaled_exp1_aic is not None and res_w.aic is not None
            else "—"
        )
        hour_delta = (
            f"{n.hour_rescaled_exp1_aic - hour_w.aic:,.0f}"
            if n.hour_rescaled_exp1_aic is not None and hour_w.aic is not None
            else "—"
        )
        rows.append(
            f"<tr><td>{_group_label(group)}</td>"
            f"<td>{raw_shape}</td><td>{raw_delta}</td>"
            f"<td>{res_shape}</td><td>{res_delta}</td>"
            f"<td>{hour_shape}</td><td>{hour_delta}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Group</th>"
        "<th>Raw Weibull shape</th><th>Raw AIC improvement over exponential</th>"
        "<th>Day-rescaled Weibull shape</th><th>Day-rescaled AIC improvement over Exp(1)</th>"
        "<th>Day+hour-rescaled Weibull shape</th><th>Day+hour-rescaled AIC improvement over Exp(1)</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _dispersion_table(summaries: dict[str, GroupSummary]) -> str:
    rows = [
        f"<tr><td>{_group_label(group)}</td><td>{_fmt(summaries[group].nhpp.index_of_dispersion)}</td></tr>"
        for group in ANALYSIS_GROUPS
    ]
    return (
        "<table><thead><tr><th>Group</th><th>Index of dispersion (daily counts)</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_html_report(
    summaries: dict[str, GroupSummary],
    day_counts: dict[str, int],
    unmapped: dict[str, int],
    total_rows: int,
    span_days: float,
    output_path: str = "diagnostics/v2/real_data_fit_report.html",
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
  h3 {{ font-size: 0.9rem; margin: 20px 0 8px; color: {_INK_PRIMARY}; }}
  code {{ background: #f0efea; padding: 1px 5px; border-radius: 4px; font-size: 0.85em; }}
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
    "Real data" analysis only - nothing here has been written back to lab_sim/v2/config.py.
    Turnaround here is booking-in-to-verification only; the dataset has no per-stage
    timestamps, so individual process-stage assumptions (reception, plating, incubation,
    ...) can't be validated, only the aggregate shape. <strong>anon_received is when the
    sample is booked in at reception, not when it physically reaches the lab</strong> (see
    TODO.md) - so "inter-arrival gap" below really means inter-booking-in gap, and
    turnaround excludes whatever wait happens before booking-in.
  </div>

  <h2>Inter-arrival fit (Poisson-arrival assumption)</h2>
  <p class="subtitle" style="margin-top:-4px;">Real mean gap between booking-in events vs. the configured SampleTypeProfile mean (which models lab_sim/v2/arrivals.py's true physical arrival process), and a K-S test against an exponential distribution fitted to the real gaps. A low K-S stat / high p-value supports the exponential (Poisson-arrival) assumption.</p>
  <div class="table-scroll">{_interarrival_table(summaries)}</div>

  <h2>Turnaround time fit (aggregate shape)</h2>
  <p class="subtitle" style="margin-top:-4px;">Best-fit distribution among normal/lognormal/gamma, selected by AIC, fitted to booking-in-to-verification time pooled across positive and negative results.</p>
  <div class="table-scroll">{_turnaround_table(summaries)}</div>

  <h2>Turnaround time: positive vs. negative</h2>
  <div class="table-scroll">{_turnaround_by_positivity_table(summaries)}</div>

  <h2>Positivity rate: real vs. configured</h2>
  <div class="table-scroll">{_positivity_table(summaries)}</div>

  <h2>Organism mix: real vs. configured</h2>
  <p class="subtitle" style="margin-top:-4px;">Real organism text is matched to the model's Organism enum by substring (see analysis/organism_mapping.py); anything unmatched falls under Other.</p>
  <div class="table-scroll">{_organism_table(summaries)}</div>

  <h2>Arrivals by day of week</h2>
  <p class="subtitle" style="margin-top:-4px;">Descriptive only - see the inter-arrival distribution review below for how this feeds the simulation's day-of-week + hour-of-day NHPP arrival model.</p>
  <div class="table-scroll">{_day_of_week_table(day_counts)}</div>

  <h2>Specimen types not yet modeled</h2>
  <p class="subtitle" style="margin-top:-4px;">Present in the real data but not in SampleType and not analyzed above.</p>
  <div class="table-scroll">{_unmapped_types_table(unmapped)}</div>

  <h2>Inter-arrival distribution review: day-of-week and hour-of-day NHPP, Weibull, and what the data actually supports</h2>
  <p class="subtitle" style="margin-top:-4px;">
    The day-of-week table above shows arrival rate varies significantly by weekday for every
    group. This review now also uses <code>received_hour</code>, a directly-extracted,
    reliable hour-of-day field (0-23) added in a later data export - unlike
    <code>anon_received</code>'s fractional-day component, which is not anchored to true
    midnight and was never usable for this. Three candidate rate models are compared below:
    a non-homogeneous Poisson process (NHPP) with a piecewise-constant day-of-week rate (as
    before), the same but with a finer joint (weekday, hour) rate, and a Weibull fit to the
    raw gaps.
  </p>
  <p class="subtitle" style="margin-top:-4px;">
    Both NHPP grains were tested properly, not just asserted: each row's rate (arrivals per
    day, or per hour-slot for the finer model - both using an exact denominator, the number of
    distinct calendar days/hours actually labeled with that weekday or weekday+hour in the
    window, not occurrences&times;24h or &times;168h, since a ~78-day window doesn't divide
    evenly) defines a piecewise-constant rate function, and the <em>time-rescaling theorem</em>
    converts each real inter-arrival gap into a rescaled interval that should be i.i.d. Exp(1)
    if that rate model is right. Unlike the raw exponential K-S stat (which fits its rate from
    the same data), neither rescaled K-S test has a fitted parameter, so both are genuine
    tests.
  </p>
  <p class="subtitle" style="margin-top:-4px;">
    <strong>The result: hour-of-day correction helps substantially more than day-of-week alone,
    but doesn't fully explain the gaps either.</strong> Day+hour-rescaled K-S stats drop
    noticeably below the day-of-week-only ones for every busy group (see the table below) -
    hour-of-day is a real, worthwhile signal, not noise. But the single most informative number
    here still doesn't move where full resolution would predict: a Weibull shape fit to the
    day+hour-rescaled gaps stays close to the day-of-week-rescaled shape (both cluster around
    0.4-0.5 across every group) instead of collapsing toward 1. If day+hour rate variation were
    the whole story, that shape would have moved to 1 after rescaling. It didn't, for any group.
    The Q-Q plots below show the same thing visually: the bottom (day+hour-rescaled) panel sits
    closer to the diagonal than the middle (day-of-week-only) panel, but both still show the
    same S-shaped deviation the raw panel does, just compressed.
  </p>
  <p class="subtitle" style="margin-top:-4px;">
    That residual - confirmed independently by the index-of-dispersion table below, 5-50&times;
    a homogeneous Poisson process at every group - is consistent with the explanation this
    review already had: <code>anon_received</code> is when a sample is
    <strong>booked in at reception</strong>, not when it physically arrives at the lab (see
    TODO.md), so every gap fitted above is really an inter-booking-in gap. Booking-in is a
    staff-paced LIS-logging step, not the external process generating physical specimens - of
    course it doesn't look like a clean Poisson process at any rate grain; it looks like
    reception throughput. Hour-of-day rate variation was one real, measurable piece of that
    throughput pattern (staff are busier at some hours than others) and is now worth encoding
    directly; the remainder plausibly reflects batching/logging behavior no smooth rate
    function - at any grain - would explain away. A hyperexponential/mixture-of-exponentials
    model was also considered, but it's mathematically a discrete-rate mixture without tracking
    <em>when</em> each rate applies, so it shares the same blind spot to intra-day structure
    the day-of-week-only NHPP had - the day+hour rates already computed make a separate fit
    redundant for this review.
  </p>
  <p class="subtitle" style="margin-top:-4px;">
    <strong>Recommendation:</strong> encode the joint day-of-week + hour-of-day rate in the
    simulation (model v2 does: <code>lab_sim/v2/arrivals.py</code>, calibrated from
    <code>hour_rates_per_hour</code> below) - it's real, statistically confirmed to help more
    than day-of-week alone, and factors cleanly into the existing per-weekday rate times an
    hourly shape. But don't expect it to fully resolve the exponential K-S rejection on its
    own, since the gaps it's being tested against are booking-in gaps, not
    <code>lab_sim/v2/arrivals.py</code>'s modeled physical-arrival process, and the residual
    Weibull shape (~0.4-0.5) is essentially unchanged by either rate correction. Replacing the
    NHPP's exponential gap distribution with a Weibull one within each bucket - a materially
    different renewal-process model, not a rate-function tweak - remains a real option for a
    future version if the residual overdispersion needs to be modeled directly rather than
    left as a documented limitation; not implemented in v2, since it's a bigger architectural
    change than adding a rate grain and wasn't asked for this pass. Getting a
    booking-in-to-verification split that isolates true physical arrival time is still the
    bigger remaining lever.
  </p>

  <h3>Day-of-week arrival rate (arrivals/day, exact-occurrence denominator)</h3>
  <div class="table-scroll">{_day_rate_table(summaries)}</div>

  <h3>Hour-of-day arrival rate (arrivals/hour-slot, averaged across weekdays)</h3>
  <p class="subtitle" style="margin-top:-4px;">
    Descriptive shape only - the K-S/Weibull checks below use the full 168-cell (weekday, hour)
    rate grid, not this weekday-averaged view.
  </p>
  <div class="table-scroll">{_hour_rate_table(summaries)}</div>

  <h3>Raw vs. day-of-week-rescaled vs. day+hour-rescaled K-S test</h3>
  <div class="table-scroll">{_nhpp_ks_table(summaries)}</div>

  <h3>Weibull fit: raw gaps vs. rescaled gaps</h3>
  <p class="subtitle" style="margin-top:-4px;">
    Shape &lt; 1 on the raw gaps is expected under time-varying Poisson rates (a mixture of
    exponentials is itself over-dispersed) and isn't evidence of genuine renewal-process
    structure on its own - the rescaled columns are the ones that test whether day-of-week, or
    day+hour, explain it away.
  </p>
  <div class="table-scroll">{_weibull_table(summaries)}</div>

  <h3>Index of dispersion</h3>
  <div class="table-scroll">{_dispersion_table(summaries)}</div>

  <h3>Q-Q plots: raw exponential vs. day-of-week-rescaled vs. day+hour-rescaled</h3>
  <img src="real_data_interarrival_qq.png" alt="Inter-arrival Q-Q plots" style="max-width:100%; border:1px solid {_GRID}; border-radius: 8px;">

  <footer>analysis.report.render_html_report</footer>
</div>
</body>
</html>
"""

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
