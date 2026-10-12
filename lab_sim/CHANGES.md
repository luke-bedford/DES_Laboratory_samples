# Changes between model versions

Each version below lives in its own subfolder (`lab_sim/v0/`, `lab_sim/v1/`, ...) as a
complete, independent copy of the package - not a shared codebase with version-specific
overrides. This is deliberate: the whole point of keeping an old version around is being
able to run *exactly* what it was, indefinitely, even after later versions change shared
code. See `lab_sim/__init__.py` for how to import a specific version.

## v2 (current)

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
change capacity or overall volume.

## v0

Initial model: 6 specimen types (blood culture, tissue, urine, swab, stool, sputum),
constant-rate Poisson arrivals per type. Organism mix was later calibrated from real data
(the version tagged `model-v0` includes that calibration); arrival rate and positivity
stayed placeholder values throughout v0's lifetime. Tagged `model-v0` in git.

## Diagnostics output convention

Each version's plots and HTML reports land under `diagnostics/<version>/` rather than a
single flat `diagnostics/` folder, so running one version's outputs doesn't overwrite
another's. `lab_sim/v2/plotting.py` and `lab_sim/v2/report.py` default their `output_path`
arguments to `diagnostics/v2/...`, as does `analysis/` (which reports against a v2
`SimulationConfig` - see `analysis/distribution_fits.py`'s module docstring); `lab_sim/v1/`'s
own defaults still point at `diagnostics/v1/...`, unchanged, since v1 was current when those
defaults were set and it's now frozen rather than edited. `lab_sim/v0/`'s own module defaults
still point at the flat `diagnostics/...` path, unchanged, because those files are frozen
exactly as they were at the `model-v0` tag - instead, `lab_sim/v0/__main__.py` (new tooling,
not part of the frozen snapshot) passes `diagnostics/v0/...` explicitly on every call rather
than the frozen defaults being edited. See "Standalone entry points" below.

## Standalone entry points

Each version can be run on its own: `python -m lab_sim.v2` (equivalently, `python main.py` at
the repo root) runs the current model; `python -m lab_sim.v1` or `python -m lab_sim.v0` runs
an earlier frozen snapshot. All are `lab_sim/<version>/__main__.py` - a `main()` function
plus a `if __name__ == "__main__":` guard, so they're importable too. `lab_sim/v2/__main__.py`
and `lab_sim/v1/__main__.py` use each version's own output defaults (`diagnostics/v2/...`,
`diagnostics/v1/...`); `lab_sim/v0/__main__.py` passes `diagnostics/v0/...` explicitly, per
the convention above.

## Background reference per version

`Background/<version>/Microbiology Context` holds the clinical-pathway brief that version was
built against - split into per-version copies (originally one shared, unversioned file) so
each can independently record what information was actually available at that version's
design time, rather than one file being silently rewritten out from under an earlier version's
documented assumptions. `lab_sim/v2/`'s own source comments/docstrings reference
`Background/v2/Microbiology Context` specifically; `lab_sim/v0/` and `lab_sim/v1/` still say
the bare, unqualified "Background/Microbiology Context" in their own frozen code, since that's
what the reference actually looked like when each was current and is not something the freeze
policy allows retroactively "fixing."

## Out of scope so far

- There is no permanent regression test for older versions - `tests/test_smoke.py` tests
  only the current version (v2).
- `analysis/` (the real-data comparison and distribution-fit tooling) is scoped to the
  current version only; it does not compare across model versions.
