from dataclasses import dataclass, field
from statistics import mean

from .entities import Sample, SampleType

# (label, queue-start timestamp key, resource-acquired timestamp key) - one
# entry per resources.<x>.request() site in processes.py. A sample's total
# queueing time is the sum of (acquired - queue_start) over whichever of
# these stages it actually passed through (see total_queue_wait_minutes) -
# which stages apply depends on sample type, blood-culture flag status, and
# culture positivity, same as report.py's _PHASES list for service times.
# Plating's queue wait is only ever nonzero for blood culture samples (see
# processes.py's _blood_culture_journey): every other type plates while
# still holding the reception-stage HSSW request, so its marginal queue
# wait is already folded into "Reception".
QUEUE_STAGES: list[tuple[str, str, str]] = [
    ("Reception", "reception_queue_start", "reception_start"),
    ("Primary incubation", "incubation_queue_start", "incubation_start"),
    ("Gram stain", "gram_stain_queue_start", "gram_stain_start"),
    ("Plating", "plating_queue_start", "plating_start"),
    (
        "Direct susceptibility setup",
        "direct_susceptibility_setup_queue_start",
        "direct_susceptibility_setup_start",
    ),
    (
        "Post-flag plate incubation",
        "post_flag_incubation_queue_start",
        "post_flag_incubation_start",
    ),
    ("Reading", "reading_queue_start", "reading_start"),
    ("Susceptibility setup", "susceptibility_setup_queue_start", "susceptibility_setup_start"),
    (
        "Sensitivity incubation",
        "sensitivity_incubation_queue_start",
        "sensitivity_incubation_start",
    ),
    (
        "Sensitivity reading",
        "sensitivity_reading_queue_start",
        "sensitivity_reading_start",
    ),
    ("Result entry", "result_entry_queue_start", "result_entry_start"),
    ("Verification", "verification_queue_start", "verification_start"),
]


def total_queue_wait_minutes(sample: Sample) -> float:
    """Sums queueing delay (time between requesting a resource and it being
    granted) across every QUEUE_STAGES entry the sample's timestamps show it
    actually passed through."""
    total = 0.0
    for _label, queue_start_key, start_key in QUEUE_STAGES:
        queue_start = sample.timestamps.get(queue_start_key)
        start = sample.timestamps.get(start_key)
        if queue_start is not None and start is not None:
            total += start - queue_start
    return total


@dataclass
class StatsCollector:
    """Accumulates per-sample records for reporting once the run finishes.

    Every arrival and completion is recorded, warm-up period included - see
    `observed_arrivals`/`observed_completions`, which is what `summary()` and
    every diagnostic actually read. Recording everything (rather than
    discarding warm-up samples at record time) keeps the pre-observation
    backlog inspectable, e.g. to confirm the warm-up period had an effect.
    """

    completed_samples: list[Sample] = field(default_factory=list)
    rejected_samples: list[Sample] = field(default_factory=list)
    arrivals: list[Sample] = field(default_factory=list)
    # Discard period: see SimulationConfig.warmup_minutes. Samples recorded
    # before this simulation time are excluded by the observed_* methods.
    warmup_minutes: float = 0.0

    def record_arrival(self, sample: Sample) -> None:
        self.arrivals.append(sample)

    def record_completion(self, sample: Sample) -> None:
        self.completed_samples.append(sample)

    def record_rejection(self, sample: Sample) -> None:
        self.rejected_samples.append(sample)

    def observed_arrivals(self) -> list[Sample]:
        return [s for s in self.arrivals if s.arrival_time >= self.warmup_minutes]

    def observed_completions(self) -> list[Sample]:
        # Filtered by when the sample was reported, not when it arrived, per
        # the standard "clear statistics at T_w" warm-up convention - a
        # sample that arrived just before T_w but finished after it still
        # counts; one still mid-pipeline at run end does not.
        return [
            s
            for s in self.completed_samples
            if s.timestamps.get("reported", s.arrival_time) >= self.warmup_minutes
        ]

    def observed_rejections(self) -> list[Sample]:
        return [s for s in self.rejected_samples if s.arrival_time >= self.warmup_minutes]

    def queueing_summary(self) -> dict:
        """Per-sample-type and whole-cohort queueing statistics (total
        minutes a completed sample spent waiting for a resource across its
        journey - see total_queue_wait_minutes) for this run alone.

        Every SampleType is included, not just ones with completions this
        run, so replications.aggregate_queueing_replications can align on a
        fixed key set across runs; a type with no completions this run
        reports n=0 and mean_minutes=None rather than being omitted.

        Only observed_completions() are covered - urine samples rejected at
        the cell-counting gate (see processes.py's sample_journey) never
        reach any QUEUE_STAGES stage, so URINE's figure here is implicitly
        conditional on having passed that gate, not on every urine arrival."""
        observed_completions = self.observed_completions()

        def _stats_for(samples: list[Sample]) -> dict:
            waits = [total_queue_wait_minutes(s) for s in samples]
            return {
                "n": len(waits),
                "mean_minutes": mean(waits) if waits else None,
            }

        by_type = {
            sample_type.name: _stats_for(
                [s for s in observed_completions if s.sample_type is sample_type]
            )
            for sample_type in SampleType
        }
        overall = _stats_for(observed_completions)

        return {"by_type": by_type, "overall": overall}

    def summary(self) -> dict:
        observed_completions = self.observed_completions()
        turnaround_times = [
            t
            for s in observed_completions
            if (t := s.turnaround_time("reported")) is not None
        ]
        n = len(turnaround_times)
        mean_tat = sum(turnaround_times) / n if n else 0.0

        positive_completed = [s for s in observed_completions if s.is_culture_positive]
        organism_counts: dict[str, int] = {}
        for sample in positive_completed:
            if sample.organism is not None:
                organism_counts[sample.organism.name] = (
                    organism_counts.get(sample.organism.name, 0) + 1
                )

        return {
            "warmup_minutes": self.warmup_minutes,
            "samples_arrived": len(self.observed_arrivals()),
            "samples_completed": n,
            "samples_rejected": len(self.observed_rejections()),
            "samples_positive": len(positive_completed),
            "mean_turnaround_minutes": mean_tat,
            "max_turnaround_minutes": max(turnaround_times) if n else 0.0,
            "min_turnaround_minutes": min(turnaround_times) if n else 0.0,
            "organism_counts": organism_counts,
            "queueing": self.queueing_summary(),
            "arrivals_during_warmup": len(self.arrivals) - len(self.observed_arrivals()),
            "completions_during_warmup": len(self.completed_samples) - n,
        }

    def print_report(self) -> None:
        summary = self.summary()
        print("=== Simulation Report ===")
        for key, value in summary.items():
            # organism_counts and queueing are nested dicts, not single
            # values - dumping them inline here is unreadable. organism_counts
            # has no dedicated printer; queueing does (see
            # replications.print_queueing_summary for the per-type breakdown,
            # over replications rather than this one run) - just surface the
            # overall mean here.
            if key == "queueing":
                overall_mean = value["overall"]["mean_minutes"]
                if overall_mean is not None:
                    print(f"mean_queue_wait_minutes: {overall_mean:.2f}")
                continue
            if isinstance(value, float):
                print(f"{key}: {value:.2f}")
            else:
                print(f"{key}: {value}")
