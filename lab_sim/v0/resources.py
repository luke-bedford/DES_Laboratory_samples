import simpy

from .config import SimulationConfig


class LabResources:
    """SimPy resources representing staff, benches, and equipment shared by
    samples. Staff pools follow the three roles in
    Background/Microbiology Context: HSSW, BMS, and clinical
    microbiologists."""

    def __init__(self, env: simpy.Environment, config: SimulationConfig):
        self.hssw = simpy.Resource(env, capacity=config.num_hssw)
        self.bms = simpy.Resource(env, capacity=config.num_bms)
        self.clinical_microbiologists = simpy.Resource(
            env, capacity=config.num_clinical_microbiologists
        )
        self.blood_culture_incubator_slots = simpy.Resource(
            env, capacity=config.num_blood_culture_incubator_slots
        )
        self.plate_incubator_slots = simpy.Resource(
            env, capacity=config.num_plate_incubator_slots
        )
        self.identification_analyzers = simpy.Resource(
            env, capacity=config.num_identification_analyzers
        )
