import random

from .config import SimulationConfig
from .entities import Patient


def generate_patient(config: SimulationConfig) -> Patient:
    """Draws a new patient's age and gender from the configured population
    distributions. Each sample currently comes from its own unique patient
    (see Background/Microbiology Context)."""

    age = random.gauss(config.patient_age_mean, config.patient_age_stdev)
    age = min(config.patient_age_max, max(config.patient_age_min, age))

    genders = list(config.patient_gender_weights.keys())
    weights = list(config.patient_gender_weights.values())
    gender = random.choices(genders, weights=weights, k=1)[0]

    return Patient(age=age, gender=gender)
