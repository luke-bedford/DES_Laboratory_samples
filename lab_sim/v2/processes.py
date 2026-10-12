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
    gender characteristic will influence sample positivity rate...").

    For blood cultures this is reused as the probability a bottle *flags*
    (see _blood_culture_journey) - flagging is the blood-culture equivalent
    of a positive culture.
    """

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


def _susceptibility_testing(
    env: simpy.Environment,
    sample: Sample,
    config: SimulationConfig,
    resources: LabResources,
):
    """Sets up susceptibility testing from a positive primary plate, incubates
    it, then has a BMS read the result. Shared by the generic pipeline and,
    for blood cultures, the susceptibility "repeated from the primary plate"
    per Background/v2/Microbiology Context."""

    with (
        resources.hssw.request() as hssw_req,
        resources.identification_analyzers.request() as analyzer_req,
    ):
        yield hssw_req
        yield analyzer_req
        sample.mark("susceptibility_setup_start", env.now)
        yield env.timeout(_duration(config.susceptibility_setup_time))
        sample.mark("susceptibility_setup_end", env.now)

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


def _report_result(
    env: simpy.Environment,
    sample: Sample,
    config: SimulationConfig,
    resources: LabResources,
    stats: StatsCollector,
):
    """A BMS enters the result onto the LIS; a clinical microbiologist then
    verifies and signs it off. Terminal stage for every sample type."""

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


def _attempt_identification(
    env: simpy.Environment, sample: Sample, config: SimulationConfig
):
    """Fires 4 hours into the post-flag primary plate incubation (per
    Background/v2/Microbiology Context) and resolves whether identification
    succeeded. Runs as its own process, independent of the incubation it's
    timed against - purely informational, and doesn't gate anything
    downstream, since the brief itself says the (organism-dependent)
    success probability "can be modelled later"."""

    yield env.timeout(config.blood_culture_identification_delay_minutes)
    sample.identification_successful = (
        random.random() < config.identification_success_probability
    )
    sample.mark("identification_attempted", env.now)


def _blood_culture_journey(
    env: simpy.Environment,
    sample: Sample,
    config: SimulationConfig,
    resources: LabResources,
    stats: StatsCollector,
    profile: SampleTypeProfile,
):
    """Blood culture bottles incubate separately and only proceed to a plate
    if they flag, per Background/v2/Microbiology Context. Reception and
    accessioning have already happened (sample_journey); there is no upfront
    plating step - the bottle itself is what's loaded onto the incubator."""

    will_flag = random.random() < _positive_probability(profile, sample, config)
    if will_flag:
        sample.organism = _draw_organism(profile)
        time_to_flag = min(
            _duration(config.blood_culture_time_to_flag),
            config.blood_culture_max_incubation_minutes,
        )
    else:
        time_to_flag = config.blood_culture_max_incubation_minutes

    with resources.blood_culture_incubator_slots.request() as req:
        yield req
        sample.mark("incubation_start", env.now)
        yield env.timeout(time_to_flag)
        sample.mark("incubation_end", env.now)

    sample.is_culture_positive = will_flag

    if not will_flag:
        # Never flagged within 5 days: reported negative, no plate is ever
        # made.
        with resources.bms.request() as req:
            yield req
            sample.mark("reading_start", env.now)
            yield env.timeout(_duration(config.reading_time))
            sample.mark("reading_end", env.now)

        yield from _report_result(env, sample, config, resources, stats)
        return

    # Flagged: gram stain, then a primary plate with direct susceptibility
    # testing set up alongside it.
    with resources.bms.request() as req:
        yield req
        sample.mark("gram_stain_start", env.now)
        yield env.timeout(_duration(config.gram_stain_time))
        sample.mark("gram_stain_end", env.now)

    with resources.hssw.request() as req:
        yield req
        sample.mark("plating_start", env.now)
        yield env.timeout(_duration(config.plating_time))
        sample.mark("plating_end", env.now)

    with (
        resources.hssw.request() as hssw_req,
        resources.identification_analyzers.request() as analyzer_req,
    ):
        yield hssw_req
        yield analyzer_req
        sample.mark("direct_susceptibility_setup_start", env.now)
        yield env.timeout(_duration(config.susceptibility_setup_time))
        sample.mark("direct_susceptibility_setup_end", env.now)

    with resources.plate_incubator_slots.request() as req:
        yield req
        sample.mark("post_flag_incubation_start", env.now)
        env.process(_attempt_identification(env, sample, config))
        yield env.timeout(_duration(config.incubation_time))
        sample.mark("post_flag_incubation_end", env.now)

    # A BMS reads the primary plate; positivity/organism are already known
    # from the flag, so this just confirms and marks timestamps.
    with resources.bms.request() as req:
        yield req
        sample.mark("reading_start", env.now)
        yield env.timeout(_duration(config.reading_time))
        sample.mark("reading_end", env.now)

    # Susceptibility testing "repeated from the primary plate".
    yield from _susceptibility_testing(env, sample, config, resources)
    yield from _report_result(env, sample, config, resources, stats)


def _generic_journey(
    env: simpy.Environment,
    sample: Sample,
    config: SimulationConfig,
    resources: LabResources,
    stats: StatsCollector,
    profile: SampleTypeProfile,
):
    """Primary incubation through to a verified, reported result - every
    sample type except blood culture. Reception, accessioning, plating (and,
    for urine, the cell-counting gate) have already happened in
    sample_journey."""

    with resources.plate_incubator_slots.request() as req:
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
        yield from _susceptibility_testing(env, sample, config, resources)

    yield from _report_result(env, sample, config, resources, stats)


def sample_journey(
    env: simpy.Environment,
    sample: Sample,
    config: SimulationConfig,
    resources: LabResources,
    stats: StatsCollector,
):
    """Carries one sample from reception through to a verified, reported
    result (or, for urine samples that don't meet culture criteria, to a
    rejection)."""

    profile = config.sample_type_profiles[sample.sample_type]

    # HSSW receive and book in every sample, then accession it. Urine
    # samples are then run through the automated cell counter; every other
    # sample type is plated here directly - except blood culture, which has
    # no upfront plating step at all (the bottle itself is loaded onto the
    # incubator - see _blood_culture_journey).
    with resources.hssw.request() as req:
        yield req
        sample.mark("reception_start", env.now)
        yield env.timeout(_duration(config.reception_time))
        sample.mark("reception_end", env.now)

        sample.mark("accessioning_start", env.now)
        yield env.timeout(_duration(config.accessioning_time))
        sample.mark("accessioning_end", env.now)

        if sample.sample_type is SampleType.URINE:
            sample.mark("cell_counting_start", env.now)
            yield env.timeout(_duration(config.cell_counting_time))
            sample.mark("cell_counting_end", env.now)

            # Per Background/v2/Microbiology Context: WCC > 100 is cultured;
            # patients under the pediatric exemption threshold are always
            # cultured regardless of WCC. The brief's other exemptions
            # (pregnancy, certain clinical areas) have no supporting patient
            # data, so they stay folded into the calibrated base rate below
            # rather than being modelled separately.
            meets_culture_criteria = (
                sample.patient.age < config.urine_pediatric_exemption_age_threshold
                or random.random() < config.urine_culture_criteria_probability
            )
            if not meets_culture_criteria:
                sample.mark("rejected", env.now)
                stats.record_rejection(sample)
                return

        if sample.sample_type is not SampleType.BLOOD_CULTURE:
            sample.mark("plating_start", env.now)
            yield env.timeout(_duration(config.plating_time))
            sample.mark("plating_end", env.now)

    if sample.sample_type is SampleType.BLOOD_CULTURE:
        yield from _blood_culture_journey(env, sample, config, resources, stats, profile)
    else:
        yield from _generic_journey(env, sample, config, resources, stats, profile)
