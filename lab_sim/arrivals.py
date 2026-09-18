import random

import simpy

from .config import SimulationConfig
from .entities import Priority, Sample, SampleType
from .patients import generate_patient
from .processes import sample_journey
from .resources import LabResources
from .stats import StatsCollector


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
    """Spawns arrivals of one sample type at its own Poisson rate. Batched
    types (urine, swabs - see SampleTypeProfile.batched) release several
    samples, each from a different patient, per arrival event."""

    profile = config.sample_type_profiles[sample_type]

    while True:
        yield env.timeout(random.expovariate(1.0 / profile.mean_interarrival_minutes))

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
