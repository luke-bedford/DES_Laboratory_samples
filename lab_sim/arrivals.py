import random

import simpy

from .config import SimulationConfig
from .entities import Priority, Sample, SampleType
from .processes import sample_journey
from .resources import LabResources
from .stats import StatsCollector


def sample_generator(
    env: simpy.Environment,
    config: SimulationConfig,
    resources: LabResources,
    stats: StatsCollector,
):
    """Spawns new samples at reception according to the interarrival distribution."""

    while True:
        yield env.timeout(random.expovariate(1.0 / config.mean_interarrival_minutes))

        sample = Sample(
            sample_type=random.choice(list(SampleType)),
            priority=random.choices(
                list(Priority), weights=[0.85, 0.15], k=1
            )[0],
            arrival_time=env.now,
        )
        sample.mark("arrived", env.now)
        stats.record_arrival(sample)
        env.process(sample_journey(env, sample, config, resources, stats))
