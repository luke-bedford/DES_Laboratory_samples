import random

import simpy

from .config import SampleTypeProfile, SimulationConfig
from .entities import Organism, Sample, SampleType
from .resources import LabResources
from .stats import StatsCollector


def _duration(mean_std: tuple[float, float]) -> float:
    mean, std = mean_std
    return max(0.1, random.gauss(mean, std))


def _positive_probability(
    profile: SampleTypeProfile, sample: Sample, config: SimulationConfig
) -> float:
    """Combines the sample type's base positivity with the patient's gender
    and age, per Background/v2/Microbiology Context ("Patient have an age and
    gender characteristic will influence sample positivity rate...")."""

    probability = profile.positive_probability
    probability *= profile.gender_positivity_modifier.get(sample.patient.gender, 1.0)

    age = sample.patient.age
    if age >= config.elderly_age_threshold:
        probability *= config.elderly_positivity_modifier
    elif age <= config.young_age_threshold:
        probability *= config.young_positivity_modifier

    return min(1.0, max(0.0, probability))


def _draw_organism(profile: SampleTypeProfile) -> Organism:
    organisms = list(profile.organism_weights.keys())
    weights = list(profile.organism_weights.values())
    return random.choices(organisms, weights=weights, k=1)[0]


def sample_journey(
    env: simpy.Environment,
    sample: Sample,
    config: SimulationConfig,
    resources: LabResources,
    stats: StatsCollector,
):
    """Carries one sample from reception through to a verified, reported
    result."""

    profile = config.sample_type_profiles[sample.sample_type]

    # HSSW receive and book in the sample, then accession and plate it.
    with resources.hssw.request() as req:
        yield req
        sample.mark("reception_start", env.now)
        yield env.timeout(_duration(config.reception_time))
        sample.mark("reception_end", env.now)

        sample.mark("accessioning_start", env.now)
        yield env.timeout(_duration(config.accessioning_time))
        sample.mark("accessioning_end", env.now)

        sample.mark("plating_start", env.now)
        yield env.timeout(_duration(config.plating_time))
        sample.mark("plating_end", env.now)

    # Blood culture bottles incubate in the dedicated blood-culture
    # incubator; every other sample type is plated (one incubator slot per
    # plate - see config.plates_per_sample) and goes into the general plate
    # incubator pool.
    primary_incubator = (
        resources.blood_culture_incubator_slots
        if sample.sample_type is SampleType.BLOOD_CULTURE
        else resources.plate_incubator_slots
    )
    with primary_incubator.request() as req:
        yield req
        sample.mark("incubation_start", env.now)
        yield env.timeout(_duration(config.incubation_time))
        sample.mark("incubation_end", env.now)

    # A BMS reads the initial plate; this resolves whether the culture is
    # positive, and if so, which organism grew.
    with resources.bms.request() as req:
        yield req
        sample.mark("reading_start", env.now)
        yield env.timeout(_duration(config.reading_time))
        sample.is_culture_positive = random.random() < _positive_probability(
            profile, sample, config
        )
        if sample.is_culture_positive:
            sample.organism = _draw_organism(profile)
        sample.mark("reading_end", env.now)

    if sample.is_culture_positive:
        # An HSSW sets up susceptibility testing on an identification
        # analyzer, then the plate goes back into an incubator slot.
        with (
            resources.hssw.request() as hssw_req,
            resources.identification_analyzers.request() as analyzer_req,
        ):
            yield hssw_req
            yield analyzer_req
            sample.mark("susceptibility_setup_start", env.now)
            yield env.timeout(_duration(config.susceptibility_setup_time))
            sample.mark("susceptibility_setup_end", env.now)

        # A positive flag - blood culture or otherwise - triggers a
        # subculture onto a plate, so sensitivity incubation always uses
        # general plate incubator capacity, never the blood-culture pool.
        with resources.plate_incubator_slots.request() as req:
            yield req
            sample.mark("sensitivity_incubation_start", env.now)
            yield env.timeout(_duration(config.sensitivity_incubation_time))
            sample.mark("sensitivity_incubation_end", env.now)

        with resources.bms.request() as req:
            yield req
            sample.mark("sensitivity_reading_start", env.now)
            yield env.timeout(_duration(config.sensitivity_reading_time))
            sample.mark("sensitivity_reading_end", env.now)

    # A BMS enters the result onto the LIS; a clinical microbiologist then
    # verifies and signs it off.
    with resources.bms.request() as req:
        yield req
        sample.mark("result_entry_start", env.now)
        yield env.timeout(_duration(config.result_entry_time))
        sample.mark("result_entry_end", env.now)

    with resources.clinical_microbiologists.request() as req:
        yield req
        sample.mark("verification_start", env.now)
        yield env.timeout(_duration(config.verification_time))
        sample.mark("reported", env.now)

    stats.record_completion(sample)
