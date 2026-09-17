from dataclasses import dataclass


@dataclass
class SimulationConfig:
    """Parameters controlling arrivals, resource capacity, and process durations.

    Times are in minutes. Distributions are mean values sampled with
    random.expovariate (interarrival) or random.gauss (service times) in the
    process/arrival generators.
    """

    random_seed: int = 42
    # Overnight culture incubation alone takes ~18h, so a useful run needs to
    # span multiple days rather than a single shift for samples to complete.
    sim_duration_minutes: float = 3 * 24 * 60

    # Arrivals
    mean_interarrival_minutes: float = 6.0

    # Resource capacity
    num_reception_staff: int = 2
    num_technicians: int = 4
    num_incubator_slots: int = 20
    num_identification_analyzers: int = 1
    num_senior_reviewers: int = 1

    # Process durations (mean, stdev) in minutes
    reception_time: tuple[float, float] = (3.0, 1.0)
    accessioning_time: tuple[float, float] = (4.0, 1.5)
    plating_time: tuple[float, float] = (6.0, 2.0)
    incubation_time: tuple[float, float] = (18 * 60, 2 * 60)
    reading_time: tuple[float, float] = (5.0, 2.0)
    identification_time: tuple[float, float] = (20.0, 5.0)
    sensitivity_incubation_time: tuple[float, float] = (16 * 60, 2 * 60)
    sensitivity_reading_time: tuple[float, float] = (8.0, 3.0)
    reporting_time: tuple[float, float] = (5.0, 2.0)

    # Probability a culture grows a pathogen requiring identification/sensitivity
    positive_culture_probability: float = 0.35
