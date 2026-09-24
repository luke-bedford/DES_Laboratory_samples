# DES Laboratory Samples

A discrete event simulation (built on [SimPy](https://simpy.readthedocs.io/)) of microbiology
samples flowing from reception through processing, incubation, identification, sensitivity
testing, and reporting.

**Model versions**: each model version is a complete, independent package under its own
subfolder - `lab_sim/v0/` (the original 6-specimen-type, constant-rate-Poisson model, also
tagged `model-v0` in git) and `lab_sim/v1/` (the current model, `lab_sim.v1.MODEL_VERSION`),
which covers every real specimen type with a count over 20 in the real dataset (20
`SampleType`s total) and replaces constant-rate arrivals with a day-of-week non-homogeneous
Poisson process (NHPP) calibrated from that same dataset - see the Arrivals section below and
`lab_sim/v1/entities.py`'s `SampleType` docstring. There is no implicit "current" version at
the top of the package; every import states its version explicitly
(`from lab_sim.v1 import ...`). See `lab_sim/CHANGES.md` for what changed between versions
and why.

## Narrative: how the simulation behaves

> This section is a living description of the model's mechanics. Update it whenever an
> entity, resource, process step, or distribution changes, so it stays a true account of
> what `python main.py` actually does rather than what it did when first written.

**Entities** (`lab_sim/v1/entities.py`). A `Sample` is generated from a unique `Patient` (id,
`age`, `Gender`) — see Background/Microbiology Context, which notes that for now each
sample comes from its own patient. Each sample carries an id, a `SampleType` (20 members as
of model v1 — every real specimen type with a count over 20 in the real dataset, plus an
`OTHER` catch-all for everything rarer; see the enum's docstring), a `Priority` (`ROUTINE` or
`URGENT`, drawn 85%/15% — currently recorded but not yet used to jump any queue), its
patient, arrival time, a three-state `is_culture_positive` flag that starts as `None` and
is resolved partway through the journey, an `Organism` (set only if positive), and a
`timestamps` dict that gets a new entry every time the sample changes stage. Turnaround
time is simply `reported - arrival_time`.

**Resources** (`lab_sim/v1/resources.py`) model the three staff groups from
Background/Microbiology Context, plus shared equipment, as `simpy.Resource` pools — plain
FIFO queues with no priority ordering: HSSW (7) who receive/book in, accession, plate, and
set up susceptibility testing; BMS (4) who read plates and susceptibilities and enter
results on the LIS; clinical microbiologists (2) who verify and sign off the final report;
and identification analyzers (2). (These were scaled up from v0's 5/3/1/1 for the v1
specimen-type expansion — see `SimulationConfig`'s Staffing comment for the reasoning.)
Incubation capacity is split into two pools: a dedicated blood-culture incubator (2,200
bottle slots, unchanged from v0 since blood culture volume itself doesn't change), used only
for blood culture samples' primary incubation, and a general plate incubator (7,230 slots,
scaled up ~45% for the added volume), used for every other sample type's primary incubation
and for *all* sensitivity incubation — a positive flag, blood culture or otherwise, triggers
a subculture onto a plate, so the follow-up incubation always draws from the plate pool. Each
sample currently occupies exactly one plate-incubator slot per incubation stage
(`config.plates_per_sample = 1`); real samples are plated onto several media types at once
and will eventually need to consume several slots concurrently — see the comment on
`plates_per_sample` in `lab_sim/v1/config.py`.

**Arrivals** (`lab_sim/v1/arrivals.py`). Each `SampleType` runs its own independent arrival
process, and as of model v1 that process is a **day-of-week non-homogeneous Poisson process
(NHPP)**, not a constant-rate one — the real dataset shows every specimen type's arrival rate
depends significantly on weekday (see `diagnostics/v1/real_data_fit_report.html`'s day-of-week
section), so each `SampleTypeProfile.arrivals_per_day_by_weekday` holds seven real,
calibrated arrivals-per-day figures (Monday–Sunday) instead of one placeholder mean.
Simulated via Lewis-Shedler **thinning**: candidate inter-arrival gaps are drawn at the
week's max rate (the envelope), and each candidate is accepted with probability
`current_weekday_rate / max_rate` — a rejected candidate simply doesn't spawn a sample and
the loop continues. This exactly reproduces a piecewise-constant-rate NHPP, unlike drawing a
fresh exponential at "today's" rate each time, which would only approximate it once a gap can
straddle a rate-change boundary. Simulated time `t=0` is anchored to Monday by convention.
Blood culture, tissue, and most of the newly-added types arrive one at a time; urine, swabs,
stool, sputum, and multi-site arrive in batches (`batch_size_range`, default 2–6 samples per
arrival event, each from a different patient) — multi-site's batching is a modeling choice,
not a real-data finding (the real dataset has no episode linkage to confirm actual batch
sizes), and its calibrated event rate is coupled to `batch_size_range` as a result. Every
rate, batch size, and the priority split live in `SimulationConfig` (`lab_sim/v1/config.py`).

**Patients** (`lab_sim/v1/patients.py`). Each new sample's patient gets an age (Gaussian,
clipped to a configurable range) and a gender (weighted categorical draw). These feed into
positivity — see below — per Background/Microbiology Context's note that patient age and
gender "influence sample positivity rate."

**The journey** (`lab_sim/v1/processes.py`) is a strict sequence of resource requests, with
every service duration drawn from `random.gauss(mean, stdev)` and floored at 0.1 minutes:

1. **Reception, accessioning, plating** — one HSSW holds all three steps back to back,
   ~3 min (sd 1) + ~4 min (sd 1.5) + ~6 min (sd 2).
2. **Primary incubation** — a blood-culture incubator slot for blood cultures, a plate
   incubator slot for everything else, ~18 hours (sd 2h). This single stage dominates
   total turnaround time.
3. **Reading** — a BMS, ~5 min (sd 2). This is also the moment `is_culture_positive` is
   resolved, as a Bernoulli draw against that sample type's `positive_probability`
   (`SampleTypeProfile`, `lab_sim/v1/config.py`), adjusted by the patient's gender and age
   (elderly/young multipliers). If positive, an `Organism` is drawn from that sample
   type's `organism_weights`.
4. **If positive only** — an HSSW sets up susceptibility testing on an identification
   analyzer (~20 min, sd 5; both resources held together), a plate-incubator slot request
   for sensitivity incubation (~16 hours, sd 2h; always the plate pool, even for a blood
   culture subculture), then a BMS reads the susceptibilities (~8 min, sd 3). Positive
   samples therefore take roughly double the incubation time of negative ones.
5. **Result entry** — a BMS enters the result onto the LIS, ~4 min (sd 1.5).
6. **Verification** — a clinical microbiologist verifies and signs off the result on the
   system, ~5 min (sd 2), after which the sample is marked `reported` and handed to
   `StatsCollector.record_completion`.

**Distributional assumptions in one place:** interarrival times follow a day-of-week NHPP per
sample type (exponential within each weekday's constant rate, thinned against the week's max —
see Arrivals above), every service duration is Gaussian, the 85/15 priority split and
each patient's gender are categorical draws, patient age is a clipped Gaussian, and culture
positivity is a per-sample-type Bernoulli trial modulated by patient gender/age, with the
resulting organism (if positive) a per-sample-type categorical draw. All of it lives in
`SimulationConfig` / `SampleTypeProfile` (`lab_sim/v1/config.py`) rather than scattered
through the process/arrival code. Nothing currently rejects or reneges — there's no queue
capacity ceiling — so a `rejected_samples` bucket exists in `StatsCollector` but is always
empty at present.

**Warm-up period** (`lab_sim/v1/stats.py`, `lab_sim/v1/simulation.py`). Starting the clock from an
empty lab and recording from `t=0` isn't representative of a real snapshot, where queues,
incubators, and staff are already mid-flow. `run_simulation` therefore runs the clock for
`config.warmup_minutes + config.sim_duration_minutes` in total (3 days + 3 days by default),
but samples arriving or completing during the first `warmup_minutes` are simulated exactly
like any other — they occupy staff and incubator capacity, so the backlog genuinely builds
up — while being excluded from the numbers everyone actually reads.
`StatsCollector` records every arrival and completion regardless of when it happened, and
exposes `observed_arrivals()` / `observed_completions()`, which filter to what happened
during the observation window (arrivals by `arrival_time`, completions by when they were
`reported` — the standard "clear statistics at `T_w`" convention). `summary()`,
`plot_distribution_checks`, and `render_html_report` all read through these two methods
rather than the raw lists, so nothing needs its own warm-up logic. `stats.summary()` also
reports `arrivals_during_warmup` / `completions_during_warmup` so the warm-up's effect stays
visible rather than silently discarded.

**Emergent behavior at the current (v1) defaults**: with the v1 specimen-type expansion and
scaled-up capacity (7,230 plate slots, 7 HSSW, 4 BMS, 2 clinical microbiologists), a 3-day
warm-up followed by a 3-day observation window (seed 42) sees roughly 2,700 samples arrive —
about 4x v0's ~690, consistent with the ~38% daily-volume increase compounding with a longer
memory in the queueing system — but only around 57% of them (compared to v0's ~99%) complete
within the 3-day window, and mean turnaround among those that do roughly doubles to ~58 hours
(v0: ~24). This is a genuine finding, not a bug: capacity was scaled by the same ~38-45%
factor as the added volume (see `SimulationConfig`'s Staffing comment), but queueing delay is
nonlinear in utilization, and a 3-day window is barely 2-4x the ~18-34 hour minimum pipeline
latency to begin with, so a bigger, busier system leaves proportionally more arrivals still
mid-pipeline at the window's end. Positive-culture completions (213 in the seed-42 run) show
up across every sample type, including the newly-added ones. `diagnostics/v1/distribution_checks.png`
shows the day-of-week NHPP's effect directly: the flat Poisson overlay (now just the
week-average rate, see `lab_sim/v1/plotting.py`) visibly diverges from bucketed arrival counts on
particularly busy or quiet weekdays, which is expected now that arrivals are genuinely
NHPP rather than constant-rate. With 20 sample types the plot is a wide 2×20 grid, and its
shared per-row y-axis flattens sparse types (e.g. `OTHER`) next to high-volume ones (e.g.
`SWAB`) — a known, accepted limitation, not redesigned as part of the v1 change.

## Structure

- `lab_sim/v1/config.py` — **the parameter file.** Every simulation parameter lives here:
  the warm-up and observation window lengths, arrival rates and batch sizes, patient
  age/gender distributions, staffing levels, process time distributions, and each sample
  type's positivity/organism profile (`SampleTypeProfile`). Nothing that controls
  simulation behavior should be hardcoded anywhere else.
- `lab_sim/v1/entities.py` — the `Sample` and `Patient` entities and the `SampleType`,
  `Priority`, `Gender`, `Organism` enums.
- `lab_sim/v1/resources.py` — shared SimPy resources (HSSW, BMS, clinical microbiologists,
  the blood-culture and plate incubator pools, identification analyzers).
- `lab_sim/v1/patients.py` — draws a new patient's age and gender.
- `lab_sim/v1/arrivals.py` — one independent day-of-week NHPP arrival process per sample type
  (Lewis-Shedler thinning against `SampleTypeProfile.arrivals_per_day_by_weekday`); spawns
  batches for batched types.
- `lab_sim/v1/processes.py` — the sample's journey through each lab stage, including
  positivity and organism resolution.
- `lab_sim/v1/stats.py` — collects every sample's timestamps (warm-up included) and exposes
  `observed_arrivals()`/`observed_completions()`, which filter to the post-warm-up
  observation window; `summary()` reports turnaround times and organism counts from those.
- `lab_sim/v1/plotting.py` — renders the arrival-count and turnaround-time diagnostic plots,
  faceted by sample type, to `diagnostics/v1/distribution_checks.png`; also renders
  `diagnostics/v1/stage_time_distributions.png`, one small panel per process stage plotting the
  Gaussian PDF each stage's duration is actually drawn from (`SimulationConfig`'s `(mean,
  stdev)` pairs, floored at 0.1 minutes).
- `lab_sim/v1/report.py` — renders a standalone HTML summary to `diagnostics/v1/summary_report.html`:
  arrival/completion counts and turnaround times and average per-phase durations by sample
  type, turnaround time and average per-phase durations compared between culture-positive
  and culture-negative samples, and patient demographics (gender split, age summary, and
  age bands against the positivity-modifier thresholds); an appendix at the end documents and
  plots the per-stage service-time parameters behind every phase-duration figure above (the
  simulation's own assumptions - not fitted to anything, kept separate from `analysis/`'s
  real-data comparison since the real export has no per-stage timestamps to fit against).
- `lab_sim/v1/simulation.py` — wires everything together and runs the simulation clock for
  `warmup_minutes + sim_duration_minutes`.
- `main.py` — entry point that runs a default simulation, prints a report, and writes the
  diagnostic plot and HTML summary.

## Real data analysis

`Data/Received_sample_data/Received_sample_data.xlsx` is a real, anonymized export of
~67k specimen results (specimen type, organism/result, booking-in and verification time,
day of week) from an actual microbiology lab. `analysis/` fits the simulation's
distributional assumptions against it — as a standalone, read-only comparison; `analysis/`
itself never writes to `lab_sim/v1/config.py` at runtime (it can't - `Data/` is gitignored and
not guaranteed to exist for every checkout). Its *outputs* have, however, been hand-transcribed
into `lab_sim/v1/config.py` as static calibrated values on several occasions since (organism
mix, then the full v1 arrival-rate/positivity/organism recalibration across all 20 sample
types) - see the `model-v0` git tag for the pre-calibration baseline. `analysis/` itself still
covers only the original 6 modeled types + Multi-site, not the full v1 20-type set; extending
it is a natural follow-up, not yet done. Note that the export's
`anon_received` timestamp is when the sample is **booked in** at reception, not when it
physically reaches the lab (see `TODO.md`) — so the inter-arrival gaps `analysis/` fits
against `lab_sim/v1/arrivals.py`'s Poisson assumption are really inter-booking-in gaps,
staff-paced rather than a clean external process, and turnaround (verified − received)
excludes whatever wait happens before booking-in.

- `analysis/load_real_data.py` — loads and cleans the raw export: maps 6 of its specimen
  types onto `SampleType` (`Blood`→`BLOOD_CULTURE`, `Tissue`→`TISSUE`, `Urine`→`URINE`,
  `Swab`→`SWAB`, `Stool`→`STOOL`, `Sputum`→`SPUTUM`); keeps `Multi-site` (24% of the
  data, almost certainly genuine multi-site screening swabs, not a data artifact) as a
  7th analysis-only group; drops a handful of preliminary/interim result rows; and
  classifies each row positive/negative on whether its result text contains `"no
  growth"` or `"no significant growth"` (two distinct phrasings in the data — neither is
  a substring of the other, so both are checked).
- `analysis/organism_mapping.py` — matches a result's free-text organism name to the
  `Organism` enum by substring; anything else falls under `OTHER`. `Organism` was
  extended from its original 6-member placeholder set to every organism with a count
  over 100 in the real data (19 members total) - see the docstring on `Organism` in
  `lab_sim/v1/entities.py`.
- `analysis/distribution_fits.py` — per group: fits an exponential to inter-arrival gaps
  and runs a K-S test against it (the Poisson-arrival assumption every
  `SampleTypeProfile.arrivals_per_day_by_weekday` rests on - as of model v1 that's a
  day-of-week NHPP rate rather than a single mean, so the "configured mean" comparison
  converts the week-average back into an equivalent mean-minutes figure); fits
  normal/lognormal/gamma to aggregate turnaround time (receipt to verification) and picks
  the best by AIC; and compares real positivity rates and organism mixes against what's
  currently configured, for the 6 original types (this module still covers only the
  original 6 + Multi-site groups, not the full v1 20-type model - see Real data analysis
  below). The real data has no per-stage timestamps, so only *aggregate* turnaround can be
  checked this way — not individual stage assumptions (reception, plating, incubation, …).
- `analysis/plots.py` / `analysis/report.py` — write
  `diagnostics/v1/real_data_distribution_fits.png` (histogram + fitted-curve overlay per
  group, axes independently scaled and clipped to the 99th percentile since arrival
  rates and turnaround spans differ by orders of magnitude between groups),
  `diagnostics/v1/real_data_interarrival_qq.png` (log-log Q-Q plots per group: raw
  exponential fit vs. the same gaps after day-of-week NHPP time-rescaling), and
  `diagnostics/v1/real_data_fit_report.html` (the numeric tables, including a review of
  candidate inter-arrival models - day-of-week NHPP via the time-rescaling theorem vs.
  Weibull vs. index of dispersion - against the day-of-week effect the chi-square test
  found), in the same visual style as `lab_sim/v1/plotting.py`/`lab_sim/v1/report.py`.
- `analyze_real_data.py` — entry point (`python analyze_real_data.py`).

## Usage

```bash
pip install -r requirements.txt
python main.py
python analyze_real_data.py
```

Run tests with:

```bash
pytest
```
