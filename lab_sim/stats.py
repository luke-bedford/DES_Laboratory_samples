from dataclasses import dataclass, field

from .entities import Sample


@dataclass
class StatsCollector:
    """Accumulates per-sample records for reporting once the run finishes."""

    completed_samples: list[Sample] = field(default_factory=list)
    rejected_samples: list[Sample] = field(default_factory=list)
    arrivals: list[Sample] = field(default_factory=list)

    def record_arrival(self, sample: Sample) -> None:
        self.arrivals.append(sample)

    def record_completion(self, sample: Sample) -> None:
        self.completed_samples.append(sample)

    def record_rejection(self, sample: Sample) -> None:
        self.rejected_samples.append(sample)

    def summary(self) -> dict:
        turnaround_times = [
            t
            for s in self.completed_samples
            if (t := s.turnaround_time("reported")) is not None
        ]
        n = len(turnaround_times)
        mean_tat = sum(turnaround_times) / n if n else 0.0

        positive_completed = [s for s in self.completed_samples if s.is_culture_positive]
        organism_counts: dict[str, int] = {}
        for sample in positive_completed:
            if sample.organism is not None:
                organism_counts[sample.organism.name] = (
                    organism_counts.get(sample.organism.name, 0) + 1
                )

        return {
            "samples_completed": n,
            "samples_rejected": len(self.rejected_samples),
            "samples_positive": len(positive_completed),
            "mean_turnaround_minutes": mean_tat,
            "max_turnaround_minutes": max(turnaround_times) if n else 0.0,
            "min_turnaround_minutes": min(turnaround_times) if n else 0.0,
            "organism_counts": organism_counts,
        }

    def print_report(self) -> None:
        summary = self.summary()
        print("=== Simulation Report ===")
        for key, value in summary.items():
            if isinstance(value, float):
                print(f"{key}: {value:.2f}")
            else:
                print(f"{key}: {value}")
