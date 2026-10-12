import random

import simpy

from .arrivals import start_arrivals
from .config import SimulationConfig
from .resources import LabResources
from .stats import StatsCollector


def run_simulation(config: SimulationConfig) -> StatsCollector:
    random.seed(config.random_seed)

    env = simpy.Environment()
    resources = LabResources(env, config)
    stats = StatsCollector(warmup_minutes=config.warmup_minutes)

    start_arrivals(env, config, resources, stats)
    env.run(until=config.warmup_minutes + config.sim_duration_minutes)

    return stats
