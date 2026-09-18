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
    stats = StatsCollector()

    start_arrivals(env, config, resources, stats)
    env.run(until=config.sim_duration_minutes)

    return stats
