# DES Laboratory Samples

A discrete event simulation (built on [SimPy](https://simpy.readthedocs.io/)) of microbiology
samples flowing from reception through processing, incubation, identification, sensitivity
testing, and reporting.

## Narrative: how the simulation behaves

> This section is a living description of the model's mechanics. Update it whenever an
> entity, resource, process step, or distribution changes, so it stays a true account of
> what `python main.py` actually does rather than what it did when first written.

**Entities** (`lab_sim/entities.py`). A `Sample` is generated from a unique `Patient` (id,
`age`, `Gender`) — see Background/Microbiology Context, which notes that for now each
sample comes from its own patient. Each sample carries an id, a `SampleType`
(`BLOOD_CULTURE`, `TISSUE`, `URINE`, `SWAB`, `STOOL`, `SPUTUM`), a `Priority` (`ROUTINE` or
`URGENT`, drawn 85%/15% — currently recorded but not yet used to jump any queue), its
patient, arrival time, a three-state `is_culture_positive` flag that starts as `None` and
is resolved partway through the journey, an `Organism` (set only if positive), and a
`timestamps` dict that gets a new entry every time the sample changes stage. Turnaround
time is simply `reported - arrival_time`.

**Resources** (`lab_sim/resources.py`) model the three staff groups from
Background/Microbiology Context, plus shared equipment, as `simpy.Resource` pools — plain
FIFO queues with no priority ordering: HSSW (5) who receive/book in, accession, plate, and
set up susceptibility testing; BMS (3) who read plates and susceptibilities and enter
results on the LIS; clinical microbiologists (1) who verify and sign off the final report;
and identification analyzers (1). Incubation capacity is split into two pools sized to the
lab's actual physical storage: a dedicated blood-culture incubator (2,200 bottle slots),
used only for blood culture samples' primary incubation, and a general plate incubator
(5,000 slots), used for every other sample type's primary incubation and for *all*
sensitivity incubation — a positive flag, blood culture or otherwise, triggers a
subculture onto a plate, so the follow-up incubation always draws from the plate pool. Each
sample currently occupies exactly one plate-incubator slot per incubation stage
(`config.plates_per_sample = 1`); real samples are plated onto several media types at once
and will eventually need to consume several slots concurrently — see the comment on
`plates_per_sample` in `lab_sim/config.py`.

**Arrivals** (`lab_sim/arrivals.py`). Each `SampleType` runs its own independent Poisson
arrival process — interarrival gaps drawn from `random.expovariate(1 /
mean_interarrival_minutes)` — with its own mean, rather than one shared process split
evenly across types, per Background/Microbiology Context ("a number of specimen types with
different inter-arrival means"). Blood culture and tissue samples arrive one at a time;
urine, swabs, stool, and sputum arrive in batches (`batch_size_range`, default 2–6 samples
per arrival event, each from a different patient), matching the note that "urine and swabs
arrive as batches" (extended here to stool and sputum, which are also collected and sent up
in rounds rather than singly). Every rate, batch size, and the priority split live in
`SimulationConfig` (`lab_sim/config.py`).

**Patients** (`lab_sim/patients.py`). Each new sample's patient gets an age (Gaussian,
clipped to a configurable range) and a gender (weighted categorical draw). These feed into
positivity — see below — per Background/Microbiology Context's note that patient age and
gender "influence sample positivity rate."

**The journey** (`lab_sim/processes.py`) is a strict sequence of resource requests, with
every service duration drawn from `random.gauss(mean, stdev)` and floored at 0.1 minutes:

1. **Reception, accessioning, plating** — one HSSW holds all three steps back to back,
   ~3 min (sd 1) + ~4 min (sd 1.5) + ~6 min (sd 2).
2. **Primary incubation** — a blood-culture incubator slot for blood cultures, a plate
   incubator slot for everything else, ~18 hours (sd 2h). This single stage dominates
   total turnaround time.
3. **Reading** — a BMS, ~5 min (sd 2). This is also the moment `is_culture_positive` is
   resolved, as a Bernoulli draw against that sample type's `positive_probability`
   (`SampleTypeProfile`, `lab_sim/config.py`), adjusted by the patient's gender and age
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

**Distributional assumptions in one place:** interarrival times are exponential per sample
type (Poisson arrivals), every service duration is Gaussian, the 85/15 priority split and
each patient's gender are categorical draws, patient age is a clipped Gaussian, and culture
positivity is a per-sample-type Bernoulli trial modulated by patient gender/age, with the
resulting organism (if positive) a per-sample-type categorical draw. All of it lives in
`SimulationConfig` / `SampleTypeProfile` (`lab_sim/config.py`) rather than scattered
through the process/arrival code. Nothing currently rejects or reneges — there's no queue
capacity ceiling — so a `rejected_samples` bucket exists in `StatsCollector` but is always
empty at present.

**Warm-up period** (`lab_sim/stats.py`, `lab_sim/simulation.py`). Starting the clock from an
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

**Emergent behavior at the current defaults**: with incubation capacity sized to the lab's
real physical storage (2,200 blood-culture slots, 5,000 plate slots) and the system already
warmed up before recording starts, a 3-day warm-up followed by a 3-day observation window
sees roughly 690 samples arrive and essentially all of them (~99%) complete within the
window — a stark contrast to a cold start, where the same 3 observed days would show most
samples still queued (see the git history for that comparison). Positive-culture completions
(177 of ~680, roughly a quarter) now show up for every sample type in normal proportions.
What still shapes turnaround is the ~18-34 hour minimum pipeline latency itself, plus
queueing for the much smaller HSSW (5) and BMS (3) pools — not incubator contention, and no
longer the cold-start transient. `diagnostics/distribution_checks.png` shows this: bucketed
arrival counts (bucketed relative to the end of warm-up) track each sample type's own
Poisson (or, for the four batched types, compound Poisson-of-batches) shape closely, and the
completed-sample turnaround histograms show a clean negative/positive split for every sample
type.

## Structure

- `lab_sim/config.py` — **the parameter file.** Every simulation parameter lives here:
  the warm-up and observation window lengths, arrival rates and batch sizes, patient
  age/gender distributions, staffing levels, process time distributions, and each sample
  type's positivity/organism profile (`SampleTypeProfile`). Nothing that controls
  simulation behavior should be hardcoded anywhere else.
- `lab_sim/entities.py` — the `Sample` and `Patient` entities and the `SampleType`,
  `Priority`, `Gender`, `Organism` enums.
- `lab_sim/resources.py` — shared SimPy resources (HSSW, BMS, clinical microbiologists,
  the blood-culture and plate incubator pools, identification analyzers).
- `lab_sim/patients.py` — draws a new patient's age and gender.
- `lab_sim/arrivals.py` — one independent arrival process per sample type; spawns batches
  for batched types.
- `lab_sim/processes.py` — the sample's journey through each lab stage, including
  positivity and organism resolution.
- `lab_sim/stats.py` — collects every sample's timestamps (warm-up included) and exposes
  `observed_arrivals()`/`observed_completions()`, which filter to the post-warm-up
  observation window; `summary()` reports turnaround times and organism counts from those.
- `lab_sim/plotting.py` — renders the arrival-count and turnaround-time diagnostic plots,
  faceted by sample type, to `diagnostics/distribution_checks.png`.
- `lab_sim/report.py` — renders a standalone HTML summary to `diagnostics/summary_report.html`:
  arrival/completion counts and turnaround times and average per-phase durations by sample
  type, turnaround time and average per-phase durations compared between culture-positive
  and culture-negative samples, and patient demographics (gender split, age summary, and
  age bands against the positivity-modifier thresholds).
- `lab_sim/simulation.py` — wires everything together and runs the simulation clock for
  `warmup_minutes + sim_duration_minutes`.
- `main.py` — entry point that runs a default simulation, prints a report, and writes the
  diagnostic plot and HTML summary.

## Usage

```bash
pip install -r requirements.txt
python main.py
```

Run tests with:

```bash
pytest
```
