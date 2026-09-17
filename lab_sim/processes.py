import random

import simpy

from .config import SimulationConfig
from .entities import Sample
from .resources import LabResources
from .stats import StatsCollector


def _duration(mean_std: tuple[float, float]) -> float:
    mean, std = mean_std
    return max(0.1, random.gauss(mean, std))


def sample_journey(
    env: simpy.Environment,
    sample: Sample,
    config: SimulationConfig,
    resources: LabResources,
    stats: StatsCollector,
):
    """Carries one sample from reception through to a reported result."""

    with resources.reception_staff.request() as req:
        yield req
        sample.mark("reception_start", env.now)
        yield env.timeout(_duration(config.reception_time))
        sample.mark("reception_end", env.now)

    with resources.technicians.request() as req:
        yield req
        sample.mark("accessioning_start", env.now)
        yield env.timeout(_duration(config.accessioning_time))
        sample.mark("accessioning_end", env.now)

        sample.mark("plating_start", env.now)
        yield env.timeout(_duration(config.plating_time))
        sample.mark("plating_end", env.now)

    with resources.incubator_slots.request() as req:
        yield req
        sample.mark("incubation_start", env.now)
        yield env.timeout(_duration(config.incubation_time))
        sample.mark("incubation_end", env.now)

    with resources.technicians.request() as req:
        yield req
        sample.mark("reading_start", env.now)
        yield env.timeout(_duration(config.reading_time))
        sample.is_culture_positive = (
            random.random() < config.positive_culture_probability
        )
        sample.mark("reading_end", env.now)

    if sample.is_culture_positive:
        with resources.identification_analyzers.request() as req:
            yield req
            sample.mark("identification_start", env.now)
            yield env.timeout(_duration(config.identification_time))
            sample.mark("identification_end", env.now)

        with resources.incubator_slots.request() as req:
            yield req
            sample.mark("sensitivity_incubation_start", env.now)
            yield env.timeout(_duration(config.sensitivity_incubation_time))
            sample.mark("sensitivity_incubation_end", env.now)

        with resources.technicians.request() as req:
            yield req
            sample.mark("sensitivity_reading_start", env.now)
            yield env.timeout(_duration(config.sensitivity_reading_time))
            sample.mark("sensitivity_reading_end", env.now)

    with resources.senior_reviewers.request() as req:
        yield req
        sample.mark("reporting_start", env.now)
        yield env.timeout(_duration(config.reporting_time))
        sample.mark("reported", env.now)

    stats.record_completion(sample)
