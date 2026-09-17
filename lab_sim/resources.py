import simpy

from .config import SimulationConfig


class LabResources:
    """SimPy resources representing staff, benches, and equipment shared by samples."""

    def __init__(self, env: simpy.Environment, config: SimulationConfig):
        self.reception_staff = simpy.Resource(env, capacity=config.num_reception_staff)
        self.technicians = simpy.Resource(env, capacity=config.num_technicians)
        self.incubator_slots = simpy.Resource(env, capacity=config.num_incubator_slots)
        self.identification_analyzers = simpy.Resource(
            env, capacity=config.num_identification_analyzers
        )
        self.senior_reviewers = simpy.Resource(env, capacity=config.num_senior_reviewers)
