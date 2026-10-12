# Changes between model versions

Each version below lives in its own subfolder (`lab_sim/v0/`, `lab_sim/v1/`, ...) as a
complete, independent copy of the package - not a shared codebase with version-specific
overrides. This is deliberate: the whole point of keeping an old version around is being
able to run *exactly* what it was, indefinitely, even after later versions change shared
code. See `lab_sim/__init__.py` for how to import a specific version.

## v3 (current)

- **Queueing-wait instrumentation**: every `resources.<x>.request()` site in `processes.py`
  now marks a `<stage>_queue_start` timestamp immediately before the `with` block, alongside
  the existing `<stage>_start` mark taken after `yield req` resolves. Previously that gap was
  invisible - `<stage>_start` was only ever marked *after* acquiring the resource, so nothing
  in `stats.py` or `report.py` could distinguish time spent queueing from time spent in
  service. `stats.py`'s new `QUEUE_STAGES` list and `total_queue_wait_minutes(sample)` sum
  `stage_start - stage_queue_start` across every stage a sample's timestamps show it actually
  passed through - the same pattern `report.py`'s `_PHASES` already used for service-time
  durations. One exception: `sample_journey`'s single HSSW request covers reception,
  accessioning, cell counting, and (for non-blood-culture types) plating under one
  acquisition, so that whole front end gets one combined queue wait, labelled "Reception" -
  it is not double-counted as a separate "Plating" wait the way blood culture's own, later,
  standalone plating acquisition is.
- **Per-sample-type and whole-cohort queueing statistics, with replication intervals**:
  `StatsCollector.queueing_summary()` reports each sample type's (and the whole cohort's)
  mean total queueing wait for one run; `replications.aggregate_queueing_replications()`
  aggregates that across N independent replications into a mean + empirical 95% interval,
  same method as `aggregate_replications()`'s existing overall-metric intervals. A sample
  type with zero completions in a given replication (e.g. blood culture, whose up-to-5-day
  incubation routinely exceeds short observation windows) contributes no observation for
  that replication - via `NaN` + `np.nanmean`/`np.nanpercentile` - rather than a `0.0`
  placeholder that would silently bias a rare type's interval toward zero. Rendered as a new
  "Queueing statistics" section in `summary_report.html`, right after "Replication analysis".
- **Why queueing, specifically**: the v2 "Emergent behavior" finding (see below, and
  `README.md`) was that turnaround blew up well past what service times alone explain -
  e.g. observed min turnaround ~36h against an ~18h mean incubation. Until now that was an
  inference from turnaround alone; this version measures the queueing component directly
  instead of inferring it. Result (100 replications, current 7-day-window defaults): mean
  total queueing wait across the whole cohort is ~57h (95% interval [53h, 61h]) against a
  mean turnaround of ~87h (95% interval [83h, 91h]) - roughly two-thirds of turnaround is
  queueing. Most sample types cluster in the 54-81h range; blood culture is a clear,
  structural outlier at only ~24h, since it's the only type whose primary incubation draws
  on the dedicated (uncontended) blood-culture incubator pool rather than the overloaded
  staff pools, and a non-flagging bottle skips plating/susceptibility entirely - see
  `README.md`'s "Emergent behavior" section. **This figure is window-length-dependent, not
  a converged steady-state property**: HSSW/BMS/clinical-microbiologists are all in
  sustained overload at these defaults (consistent with the v1 "known limitation" below), so
  the backlog grows across the run rather than stabilizing. Doubling the window to 14 days
  (10 replications) moves the mean queueing wait to ~92h and mean turnaround to ~124h -
  both scale with window length, while the completed fraction barely moves. Report this
  figure as "mean wait among samples completing within a 7-day window," not as the system's
  steady-state queueing behavior.
- Cross-references: `lab_sim/v2/` (superseded, stays frozen and runnable via
  `python -m lab_sim.v2`). No arrival, capacity, or pathway parameters changed from v2 - see
  `config.py`'s `MODEL_VERSION` docstring.
- Out of scope so far (see also the project-wide "Out of scope so far" section below):
  resource-level statistics (utilization, queue length over time) - this version is
  sample-centric (per sample type and per cohort), not per resource. A natural next v3 step,
  not done here. `analysis/` stays pinned to `lab_sim.v2` - nothing about queueing
  instrumentation touches arrivals or calibration, so repointing it would be pure churn.

## v2

- **Arrivals**: adds hour-of-day to the NHPP rate, using `received_hour` - a reliable,
  directly-extracted hour field (0-23) added in a later data export. The rate is now
  factorized: `arrivals_per_day_by_weekday[weekday] * hourly_fraction_of_day[hour]` (24
  calibrated values per type, summing to 1.0), thinned the same Lewis-Shedler way v1 already
  did, with the envelope now the product of both factors' maxima. `arrivals_per_day_by_weekday`
  itself is unchanged from v1 - same source data, same computation, unaffected by the new
  field.
- **Why**: the real-data recheck (`analysis/`'s NHPP review, now extended to hour-of-day)
  found that rescaling real inter-arrival gaps against the joint (weekday, hour) rate drops
  the K-S statistic substantially below the day-of-week-only rescaling for every group (e.g.
  Blood culture K-S 0.654 day-of-week-rescaled -> 0.489 day+hour-rescaled; Swab 0.610 ->
  0.384) - hour-of-day is a real, worthwhile signal. It does not fully resolve the
  non-exponential shape, though: the Weibull shape fit to the rescaled gaps stays ~0.4-0.5
  either way, essentially unchanged, consistent with the standing theory that `anon_received`
  is a booking-in (staff-paced, bursty) timestamp, not a smooth external physical-arrival
  process - see `diagnostics/v2/real_data_fit_report.html`'s "Inter-arrival distribution
  review" for the full writeup. A Weibull-gap renewal process (replacing the NHPP's
  exponential gap distribution within each bucket) would be a materially different arrival
  model, not a rate-function tweak, and wasn't implemented here.
- **Capacity**: unchanged from v1 - hour-of-day arrivals redistribute the same weekly volume
  within each day rather than adding any, so there was no calibrated reason to rescale it.
  v2's observed arrival total (~2693 over the same seed/window) tracks v1's (~2709) closely,
  confirming the factorization doesn't change overall volume, only its within-day timing.
- Calibrated the same way as v1: offline via a scratchpad script against `Data/`, then
  hand-transcribed as static literals into `v2/config.py`.
- Cross-references: `lab_sim/v1/` (superseded, stays frozen and runnable via
  `python -m lab_sim.v1`).
- **Blood culture and urine pathways** (later v2 update, landed in place rather than as a
  new frozen version): `Background/v2/Microbiology Context` describes sample-type-specific
  workflows for these two types that the model didn't implement - every type ran through
  one generic pipeline. Added: a dedicated `_blood_culture_journey` (`processes.py`) with
  up to 5-day bottle incubation, a gram stain + primary plate + direct susceptibility
  testing sequence gated on the bottle flagging, a non-blocking 4-hours-in identification
  attempt, and susceptibility "repeated from the primary plate"; and a urine cell-counting
  gate (`SimulationConfig.urine_culture_criteria_probability`, calibrated from the brief's
  ~63.9% figure) ahead of plating, which finally exercises `StatsCollector`'s previously
  vestigial `record_rejection`/`rejected_samples`. Two brief details have no supporting
  data and are documented simplifications rather than calibrated figures: identification
  success is a single flat placeholder probability, not organism-dependent (the brief
  itself says this "can be modelled later"), and the brief's pregnancy/clinical-area urine
  exemptions are folded into the single calibrated base rate rather than modelled
  separately (no patient attribute exists for either) - only the <12-year-old exemption is
  modelled explicitly, reusing the existing `Patient.age` field.
- **Observation window widened to 7 days** (later v2 update): `sim_duration_minutes`
  increased from 3 to 7 days (`warmup_minutes` unchanged at 3 days, 10 simulated days per
  run total). The blood-culture pathway above added a non-flagging bottle's up to-5-day
  incubation (`blood_culture_max_incubation_minutes`) - longer than the old 3-day window,
  so most blood cultures arriving during observation could never be counted as completed.
- **Replication-based aggregate statistics** (same update): new `lab_sim/v2/replications.py`
  - `run_replications` runs a config `N` times, varying only `random_seed`; `aggregate_
  replications` computes the mean and an empirical 95% interval (2.5th/97.5th percentile
  across replications) per overall summary metric. This is the standard discrete-event-
  simulation "method of replications" approach to run-to-run variability, not a Bayesian
  credible interval - there's no posterior here, just repeated independent runs. Exposed via
  `python -m lab_sim.v2 --replications N` (default 100, `--replications 1` to skip it) and
  rendered as a new "Replication analysis" section in `summary_report.html`.

## v1

- **Specimen types**: expanded from 6 placeholder types to 20 - every real specimen type
  with more than 20 occurrences in `Data/Received_sample_data.xlsx` gets its own type;
  everything rarer folds into `OTHER`.
- **Arrivals**: switched from a constant-rate Poisson process to a day-of-week
  non-homogeneous Poisson process, simulated via Lewis-Shedler thinning against real
  per-weekday arrival rates (candidates drawn at the week's max rate, accepted with
  probability `current_rate / max_rate`).
- **Positivity and organism mix**: calibrated from real data for all 20 types (previously
  placeholder values for everything except organism mix, which v0 already had calibrated -
  see the `model-v0` tag, which sits after that calibration).
- **Capacity**: scaled up roughly 38-45% to match the larger type set and arrival volume
  (HSSW 5->7, BMS 3->4, clinical microbiologists 1->2, identification analyzers 1->2,
  plate incubator slots 5000->7230; the blood-culture incubator pool is unaffected and
  stays at 2200).
- All calibration was done offline via scratchpad scripts against `Data/`, then
  hand-transcribed as static literals into `v1/config.py` - `lab_sim` has no runtime
  dependency on `Data/`.
- Cross-references: the pre-expansion model is tagged `model-v0` in git; the calibration
  and restructuring landed in this session's commits.

**Known limitation**: at v1's scaled capacity, the lab no longer clears its queue within
the simulation's observation window the way v0 did (~57% of arrivals complete within 3
days, vs. ~99% for v0; mean turnaround roughly doubles, from ~24h to ~58h). This is an
emergent finding from the higher, unevenly-distributed real arrival volume, not a bug -
see `README.md`'s "Emergent behavior" section for detail. Still present in v2, at similar
magnitude (~56% complete within 3 days, mean turnaround ~58h) - expected, since v2 doesn't
change capacity or overall volume. v3 doesn't change capacity or volume either, so the same
congestion persists there too - now with the queueing component of it directly measured
(see the v3 section above) rather than only inferred from turnaround.

## v0

Initial model: 6 specimen types (blood culture, tissue, urine, swab, stool, sputum),
constant-rate Poisson arrivals per type. Organism mix was later calibrated from real data
(the version tagged `model-v0` includes that calibration); arrival rate and positivity
stayed placeholder values throughout v0's lifetime. Tagged `model-v0` in git.

## Diagnostics output convention

Each version's plots and HTML reports land under `diagnostics/<version>/` rather than a
single flat `diagnostics/` folder, so running one version's outputs doesn't overwrite
another's. `lab_sim/v3/plotting.py` and `lab_sim/v3/report.py` default their `output_path`
arguments to `diagnostics/v3/...`; `analysis/` still reports against a v2 `SimulationConfig`
and writes to `diagnostics/v2/...` (see `analysis/distribution_fits.py`'s module docstring,
and the "Out of scope so far" section below) rather than following the current version;
`lab_sim/v2/`'s and `lab_sim/v1/`'s own defaults still point at `diagnostics/v2/...` and
`diagnostics/v1/...` respectively, unchanged, since each was current when those defaults
were set and is now frozen rather than edited. `lab_sim/v0/`'s own module defaults still
point at the flat `diagnostics/...` path, unchanged, because those files are frozen exactly
as they were at the `model-v0` tag - instead, `lab_sim/v0/__main__.py` (new tooling, not
part of the frozen snapshot) passes `diagnostics/v0/...` explicitly on every call rather
than the frozen defaults being edited. See "Standalone entry points" below.

## Standalone entry points

Each version can be run on its own: `python -m lab_sim.v3` (equivalently, `python main.py` at
the repo root) runs the current model; `python -m lab_sim.v2`, `python -m lab_sim.v1`, or
`python -m lab_sim.v0` runs an earlier frozen snapshot. All are
`lab_sim/<version>/__main__.py` - a `main()` function plus a `if __name__ == "__main__":`
guard, so they're importable too. `lab_sim/v3/__main__.py`, `lab_sim/v2/__main__.py`, and
`lab_sim/v1/__main__.py` use each version's own output defaults (`diagnostics/v3/...`,
`diagnostics/v2/...`, `diagnostics/v1/...`); `lab_sim/v0/__main__.py` passes
`diagnostics/v0/...` explicitly, per the convention above.

## Background reference per version

`Background/<version>/Microbiology Context` holds the clinical-pathway brief that version was
built against - split into per-version copies (originally one shared, unversioned file) so
each can independently record what information was actually available at that version's
design time, rather than one file being silently rewritten out from under an earlier version's
documented assumptions. `lab_sim/v3/`'s own source comments/docstrings reference
`Background/v3/Microbiology Context` specifically (identical content to v2's copy - v3 adds
no new clinical-pathway information, only queueing instrumentation); `lab_sim/v2/`'s own code
references `Background/v2/Microbiology Context`; `lab_sim/v0/` and `lab_sim/v1/` still say
the bare, unqualified "Background/Microbiology Context" in their own frozen code, since that's
what the reference actually looked like when each was current and is not something the freeze
policy allows retroactively "fixing."

## Out of scope so far

- There is no permanent regression test for older versions - `tests/test_smoke.py` tests
  only the current version (v3).
- `analysis/` (the real-data comparison and distribution-fit tooling) still imports from
  `lab_sim.v2` specifically, not whichever version is current - it was never repointed at
  v3 since v3 doesn't change arrivals, calibration, or anything else `analysis/` compares
  against (only queueing instrumentation, which has no real-data analogue to fit). It does
  not compare across model versions either way.
- v3's queueing statistics are sample-centric (per sample type, and for the whole cohort) -
  there is no resource-level view yet (utilization, queue length over time per resource).
  A natural next v3 step.
