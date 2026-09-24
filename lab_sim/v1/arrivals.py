import random

import simpy

from .config import SimulationConfig
from .entities import Priority, Sample, SampleType
from .patients import generate_patient
from .processes import sample_journey
from .resources import LabResources
from .stats import StatsCollector

# Local to lab_sim - not imported from analysis, which depends on lab_sim
# and never the other way around (Data/ is gitignored and not guaranteed to
# exist for every checkout, so lab_sim itself must stay independent of it).
_DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _weekday_at(sim_minutes: float) -> str:
    # t=0 is anchored to Monday by convention (arbitrary but fixed).
    return _DAY_ORDER[int(sim_minutes // (24 * 60)) % 7]


def _draw_priority(config: SimulationConfig) -> Priority:
    priorities = list(config.priority_weights.keys())
    weights = list(config.priority_weights.values())
    return random.choices(priorities, weights=weights, k=1)[0]


def _spawn_sample(
    env: simpy.Environment,
    sample_type: SampleType,
    config: SimulationConfig,
    resources: LabResources,
    stats: StatsCollector,
) -> None:
    sample = Sample(
        sample_type=sample_type,
        priority=_draw_priority(config),
        patient=generate_patient(config),
        arrival_time=env.now,
    )
    sample.mark("arrived", env.now)
    stats.record_arrival(sample)
    env.process(sample_journey(env, sample, config, resources, stats))


def _sample_type_arrivals(
    env: simpy.Environment,
    sample_type: SampleType,
    config: SimulationConfig,
    resources: LabResources,
    stats: StatsCollector,
):
    """Spawns arrivals of one sample type as a day-of-week non-homogeneous
    Poisson process (NHPP), via Lewis-Shedler thinning against
    SampleTypeProfile.arrivals_per_day_by_weekday: draw candidate gaps at the
    week's max rate (the thinning envelope), then accept each candidate with
    probability current_weekday_rate / max_rate - a rejected candidate
    simply doesn't spawn a sample and the loop continues. This exactly
    reproduces a piecewise-constant-rate NHPP, unlike drawing a fresh
    exponential at "today's" rate each time, which is only an approximation
    once a gap can straddle a rate-change boundary. Batched types (urine,
    swabs, ... - see SampleTypeProfile.batched) release several samples,
    each from a different patient, per accepted arrival event."""

    profile = config.sample_type_profiles[sample_type]
    rates = profile.arrivals_per_day_by_weekday
    # Computed once and reused for both the envelope and the acceptance
    # test below - two separate max(rates.values()) calls (one per use)
    # would risk desynchronizing if either is edited independently later.
    max_rate_per_day = max(rates.values())
    max_rate_per_minute = max_rate_per_day / (24 * 60)

    while True:
        yield env.timeout(random.expovariate(max_rate_per_minute))

        current_rate = rates[_weekday_at(env.now)]
        if random.random() < current_rate / max_rate_per_day:
            batch_size = random.randint(*config.batch_size_range) if profile.batched else 1
            for _ in range(batch_size):
                _spawn_sample(env, sample_type, config, resources, stats)


def start_arrivals(
    env: simpy.Environment,
    config: SimulationConfig,
    resources: LabResources,
    stats: StatsCollector,
) -> None:
    """Starts one independent arrival process per sample type, each with its
    own inter-arrival mean (see SampleTypeProfile)."""

    for sample_type in config.sample_type_profiles:
        env.process(_sample_type_arrivals(env, sample_type, config, resources, stats))
