from dataclasses import dataclass, field

from .entities import Sample


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
            "arrivals_during_warmup": len(self.arrivals) - len(self.observed_arrivals()),
            "completions_during_warmup": len(self.completed_samples) - n,
        }

    def print_report(self) -> None:
        summary = self.summary()
        print("=== Simulation Report ===")
        for key, value in summary.items():
            if isinstance(value, float):
                print(f"{key}: {value:.2f}")
            else:
                print(f"{key}: {value}")
