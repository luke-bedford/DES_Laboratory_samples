# DES Laboratory Samples

A discrete event simulation (built on [SimPy](https://simpy.readthedocs.io/)) of microbiology
samples flowing from reception through processing, incubation, identification, sensitivity
testing, and reporting.

## Narrative: how the simulation behaves

> This section is a living description of the model's mechanics. Update it whenever an
> entity, resource, process step, or distribution changes, so it stays a true account of
> what `python main.py` actually does rather than what it did when first written.

**Entities.** The only entity that flows through the model is a `Sample`
(`lab_sim/entities.py`). Each one carries an id, a `SampleType` (`BLOOD_CULTURE`, `URINE`,
`SWAB`, `STOOL`, `SPUTUM` — assigned uniformly at random on arrival), a `Priority`
(`ROUTINE` or `URGENT`, drawn 85%/15% — currently recorded but not yet used to jump any
queue), its arrival time, a three-state `is_culture_positive` flag that starts as `None`
and is resolved partway through the journey, and a `timestamps` dict that gets a new entry
every time the sample changes stage. Turnaround time is simply `reported - arrival_time`.

**Resources.** Five `simpy.Resource` pools represent shared lab capacity
(`lab_sim/resources.py`), each a plain FIFO queue with no priority ordering: reception
staff (2), technicians (4, shared across accessioning, plating, reading, and sensitivity
reading), incubator slots (20, shared between primary culture incubation and — for
positive cultures — the second sensitivity-testing incubation), identification analyzers
(1), and senior reviewers (1) who sign off the final report.

**Arrivals.** New samples appear via a Poisson process: interarrival gaps are drawn from
`random.expovariate(1 / mean_interarrival_minutes)`, with a default mean of 6 minutes
(~10 samples/hour). Because the arrival-type assignment is independent of timing, the
arrival-thinning property applies — each of the 5 sample types is itself an independent
Poisson stream at one-fifth the overall rate.

**The journey** (`lab_sim/processes.py`) is a strict sequence of resource requests, with
every service duration drawn from `random.gauss(mean, stdev)` and floored at 0.1 minutes:

1. **Reception** — reception staff, ~3 min (sd 1).
2. **Accessioning then plating** — one technician holds both steps back to back, ~4 min
   (sd 1.5) then ~6 min (sd 2).
3. **Primary incubation** — an incubator slot, ~18 hours (sd 2h). This single stage
   dominates total turnaround time.
4. **Reading** — a technician, ~5 min (sd 2). This is also the moment
   `is_culture_positive` is resolved, as a Bernoulli draw with probability
   `positive_culture_probability` (default 0.35).
5. **If positive only** — identification on an analyzer (~20 min, sd 5), a second
   incubator-slot request for sensitivity incubation (~16 hours, sd 2h), then a
   technician for sensitivity reading (~8 min, sd 3). Positive samples therefore take
   roughly double the incubator time of negative ones and compete with primary
   incubations for the same slot pool.
6. **Reporting** — a senior reviewer, ~5 min (sd 2), after which the sample is marked
   `reported` and handed to `StatsCollector.record_completion`.

**Distributional assumptions in one place:** interarrival times are exponential (Poisson
arrivals), every service duration is Gaussian, sample type and the 85/15 priority split
are uniform/categorical draws independent of everything else, and culture positivity is
a single Bernoulli trial per sample. Nothing currently rejects or reneges — there's no
queue capacity ceiling — so a `rejected_samples` bucket exists in `StatsCollector` but is
always empty at present.

**A known emergent behavior**, found by the diagnostic plots rather than designed in: at
the current defaults, the 20-shared incubator slots cap throughput at roughly one
sample-cycle per slot every 18–34 hours, well below the ~10/hour arrival rate. The system
is not in steady state over the default 3-day run — most samples are still queued when
the simulation ends, and positive-culture samples (needing the longest path) rarely
finish at all. `diagnostics/distribution_checks.png` shows this directly: bucketed
arrival counts track the Poisson fit closely (the arrival assumption holds), but the
completed-sample turnaround histograms, faceted by sample type, are dominated by queueing
delay and show almost no positive-culture completions.

## Structure

- `lab_sim/config.py` — simulation parameters (arrival rate, resource capacities, process
  time distributions).
- `lab_sim/entities.py` — the `Sample` entity and its type/priority enums.
- `lab_sim/resources.py` — shared SimPy resources (reception staff, technicians, incubator
  slots, identification analyzers, senior reviewers).
- `lab_sim/arrivals.py` — the arrival process that spawns new samples.
- `lab_sim/processes.py` — the sample's journey through each lab stage.
- `lab_sim/stats.py` — collects per-sample timestamps and reports turnaround times.
- `lab_sim/plotting.py` — renders the arrival-count and turnaround-time diagnostic plots,
  faceted by sample type, to `diagnostics/distribution_checks.png`.
- `lab_sim/simulation.py` — wires everything together and runs the simulation clock.
- `main.py` — entry point that runs a default simulation, prints a report, and writes the
  diagnostic plot.

## Usage

```bash
pip install -r requirements.txt
python main.py
```

Run tests with:

```bash
pytest
```
