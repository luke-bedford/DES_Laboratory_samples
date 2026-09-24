from dataclasses import dataclass, field

from .entities import Gender, Organism, Priority, SampleType


@dataclass
class SampleTypeProfile:
    """Every distributional assumption specific to one specimen type,
    gathered in one place so a new sample type - or updated real-world
    arrival/positivity data, per Background/Microbiology Context - only
    needs changes here.
    """

    # Mean minutes between arrival *events* of this type. For a batched type
    # (see `batched`) this is the mean gap between batches, not between
    # individual samples.
    mean_interarrival_minutes: float

    # Urine, swabs, stool, and sputum are sent up from wards/clinics in
    # batches rather than one at a time; blood cultures and tissue samples
    # arrive individually.
    batched: bool = False

    # Base probability a culture of this sample type grows a pathogen,
    # before the patient age/gender modifiers on SimulationConfig are
    # applied.
    positive_probability: float = 0.3

    # Relative likelihood of each organism, conditional on the culture being
    # positive. Need not sum to 1 - random.choices normalises at draw time.
    organism_weights: dict[Organism, float] = field(default_factory=dict)

    # Multiplies positive_probability for patients of each gender (1.0 = no
    # effect). A gender missing from the dict defaults to 1.0.
    gender_positivity_modifier: dict[Gender, float] = field(default_factory=dict)


def _default_sample_type_profiles() -> dict[SampleType, SampleTypeProfile]:
    """Arrival rates and positive_probability remain rough, plausible NHS
    microbiology placeholders (see Background/Microbiology Context) pending
    future calibration. organism_weights, however, are calibrated directly
    from the real dataset (Data/Received_sample_data/Received_sample_data.xlsx):
    each SampleType's weights are the exact proportion of real positive
    results that mapped to that Organism among positive cultures of that
    type (see analysis/organism_mapping.py and
    diagnostics/real_data_fit_report.html's organism-mix table - regenerate
    via `python analyze_real_data.py` if the dataset changes). Multi-site
    isn't included here since SampleType doesn't model it.
    """

    return {
        SampleType.BLOOD_CULTURE: SampleTypeProfile(
            mean_interarrival_minutes=40.0,
            batched=False,
            positive_probability=0.12,
            organism_weights={
                Organism.OTHER: 0.3586,
                Organism.ESCHERICHIA_COLI: 0.1629,
                Organism.STAPHYLOCOCCUS_EPIDERMIDIS: 0.1571,
                Organism.STAPHYLOCOCCUS_AUREUS: 0.1086,
                Organism.KLEBSIELLA_PNEUMONIAE: 0.0529,
                Organism.ENTEROCOCCUS_SPP: 0.0486,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.0314,
                Organism.CANDIDA_SPP: 0.0143,
                Organism.ENTEROBACTER_HORMAECHEI: 0.0129,
                Organism.KLEBSIELLA_OXYTOCA: 0.0129,
                Organism.PROTEUS_SPP: 0.0100,
                Organism.STREPTOCOCCUS_DYSGALACTIAE: 0.0100,
                Organism.STREPTOCOCCUS_AGALACTIAE: 0.0086,
                Organism.CITROBACTER_KOSERI: 0.0071,
                Organism.PSEUDOMONAS_SPP: 0.0043,
            },
        ),
        SampleType.TISSUE: SampleTypeProfile(
            mean_interarrival_minutes=120.0,
            batched=False,
            positive_probability=0.25,
            organism_weights={
                Organism.OTHER: 0.2853,
                Organism.STAPHYLOCOCCUS_AUREUS: 0.2740,
                Organism.ESCHERICHIA_COLI: 0.0791,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.0650,
                Organism.STAPHYLOCOCCUS_EPIDERMIDIS: 0.0593,
                Organism.CANDIDA_SPP: 0.0565,
                Organism.TRICHOPHYTON_RUBRUM: 0.0537,
                Organism.ENTEROBACTER_HORMAECHEI: 0.0367,
                Organism.PROTEUS_SPP: 0.0198,
                Organism.ENTEROCOCCUS_SPP: 0.0169,
                Organism.MIXED_SKIN_FLORA: 0.0169,
                Organism.MIXED_GRAM_NEGATIVE_FLORA: 0.0141,
                Organism.KLEBSIELLA_PNEUMONIAE: 0.0085,
                Organism.CITROBACTER_KOSERI: 0.0056,
                Organism.STREPTOCOCCUS_AGALACTIAE: 0.0056,
                Organism.STREPTOCOCCUS_DYSGALACTIAE: 0.0028,
            },
        ),
        SampleType.URINE: SampleTypeProfile(
            mean_interarrival_minutes=70.0,
            batched=True,
            positive_probability=0.30,
            organism_weights={
                Organism.ESCHERICHIA_COLI: 0.4897,
                Organism.ENTEROCOCCUS_SPP: 0.1022,
                Organism.OTHER: 0.0934,
                Organism.KLEBSIELLA_PNEUMONIAE: 0.0728,
                Organism.PROTEUS_SPP: 0.0449,
                Organism.HEAVY_MIXED_GROWTH: 0.0400,
                Organism.CANDIDA_SPP: 0.0308,
                Organism.PSEUDOMONAS_SPP: 0.0294,
                Organism.CITROBACTER_KOSERI: 0.0241,
                Organism.ENTEROBACTER_HORMAECHEI: 0.0171,
                Organism.STAPHYLOCOCCUS_EPIDERMIDIS: 0.0137,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.0131,
                Organism.KLEBSIELLA_OXYTOCA: 0.0131,
                Organism.STAPHYLOCOCCUS_AUREUS: 0.0090,
                Organism.STREPTOCOCCUS_AGALACTIAE: 0.0061,
                Organism.STREPTOCOCCUS_DYSGALACTIAE: 0.0004,
            },
            # Urinary tract infections are diagnosed more often in women.
            gender_positivity_modifier={Gender.FEMALE: 1.4, Gender.MALE: 0.7},
        ),
        SampleType.SWAB: SampleTypeProfile(
            mean_interarrival_minutes=120.0,
            batched=True,
            positive_probability=0.40,
            organism_weights={
                Organism.CANDIDA_SPP: 0.2447,
                Organism.STAPHYLOCOCCUS_AUREUS: 0.2252,
                Organism.MIXED_SKIN_FLORA: 0.2236,
                Organism.OTHER: 0.0643,
                Organism.MIXED_GRAM_NEGATIVE_FLORA: 0.0552,
                Organism.STREPTOCOCCUS_AGALACTIAE: 0.0469,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.0445,
                Organism.ESCHERICHIA_COLI: 0.0236,
                Organism.STREPTOCOCCUS_DYSGALACTIAE: 0.0170,
                Organism.ENTEROCOCCUS_SPP: 0.0122,
                Organism.KLEBSIELLA_PNEUMONIAE: 0.0111,
                Organism.ENTEROBACTER_HORMAECHEI: 0.0105,
                Organism.PSEUDOMONAS_SPP: 0.0056,
                Organism.PROTEUS_SPP: 0.0047,
                Organism.KLEBSIELLA_OXYTOCA: 0.0037,
                Organism.CITROBACTER_KOSERI: 0.0032,
                Organism.STAPHYLOCOCCUS_EPIDERMIDIS: 0.0025,
                Organism.HAEMOPHILUS_INFLUENZAE: 0.0013,
                Organism.HEAVY_MIXED_GROWTH: 0.0001,
            },
        ),
        SampleType.STOOL: SampleTypeProfile(
            mean_interarrival_minutes=240.0,
            batched=True,
            positive_probability=0.15,
            # Real positives are only ever E. coli or Other (which covers
            # enteric pathogens like Salmonella/Campylobacter - none of them
            # individually clear the >100-count threshold that got an
            # Organism member of their own, see lab_sim/entities.py).
            organism_weights={
                Organism.OTHER: 0.7455,
                Organism.ESCHERICHIA_COLI: 0.2545,
            },
        ),
        SampleType.SPUTUM: SampleTypeProfile(
            mean_interarrival_minutes=240.0,
            batched=True,
            positive_probability=0.30,
            organism_weights={
                Organism.CANDIDA_SPP: 0.3048,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.2027,
                Organism.OTHER: 0.1830,
                Organism.HAEMOPHILUS_INFLUENZAE: 0.0980,
                Organism.STAPHYLOCOCCUS_AUREUS: 0.0592,
                Organism.PSEUDOMONAS_SPP: 0.0327,
                Organism.MIXED_GRAM_NEGATIVE_FLORA: 0.0306,
                Organism.ESCHERICHIA_COLI: 0.0259,
                Organism.KLEBSIELLA_PNEUMONIAE: 0.0204,
                Organism.PROTEUS_SPP: 0.0122,
                Organism.ENTEROBACTER_HORMAECHEI: 0.0102,
                Organism.CITROBACTER_KOSERI: 0.0088,
                Organism.KLEBSIELLA_OXYTOCA: 0.0068,
                Organism.STREPTOCOCCUS_AGALACTIAE: 0.0048,
            },
        ),
    }


@dataclass
class SimulationConfig:
    """Every parameter controlling the simulation, gathered in one place so
    the model can be recalibrated without touching any process logic.

    Times are in minutes. Interarrival gaps are exponential
    (`random.expovariate`), service times are Gaussian (`random.gauss`,
    floored at 0.1 minutes), and sample type/priority/organism/positivity
    draws are independent categorical or Bernoulli trials - see
    `SampleTypeProfile` for the per-sample-type ones.
    """

    random_seed: int = 42
    # A simulation starting from an empty lab isn't representative of a real
    # snapshot, where queues, incubators, and staff are already mid-flow. The
    # clock runs for this long first - samples arrive and are processed
    # normally - before StatsCollector starts counting anything as "observed"
    # (see StatsCollector.observed_arrivals/observed_completions). Total
    # simulated time is warmup_minutes + sim_duration_minutes.
    warmup_minutes: float = 3 * 24 * 60
    # Length of the *observation* window that follows the warm-up - i.e. how
    # long stats are actually recorded for, not the total run length.
    # Overnight culture incubation alone takes ~18h, so a useful window needs
    # to span multiple days rather than a single shift for samples to complete.
    sim_duration_minutes: float = 3 * 24 * 60

    # --- Arrivals ---------------------------------------------------------
    # One profile per SampleType holds its arrival rate, positivity, and
    # organism mix. See SampleTypeProfile / _default_sample_type_profiles.
    sample_type_profiles: dict[SampleType, SampleTypeProfile] = field(
        default_factory=_default_sample_type_profiles
    )
    # Batched sample types (SampleTypeProfile.batched) release this many
    # samples - each from a different patient - per arrival event, drawn
    # uniformly at random (inclusive).
    batch_size_range: tuple[int, int] = (2, 6)
    priority_weights: dict[Priority, float] = field(
        default_factory=lambda: {Priority.ROUTINE: 0.85, Priority.URGENT: 0.15}
    )

    # --- Patients -----------------------------------------------------------
    # Age is drawn from a Gaussian, clipped to [patient_age_min, patient_age_max].
    patient_age_mean: float = 55.0
    patient_age_stdev: float = 22.0
    patient_age_min: float = 0.0
    patient_age_max: float = 100.0
    patient_gender_weights: dict[Gender, float] = field(
        default_factory=lambda: {Gender.FEMALE: 0.52, Gender.MALE: 0.48}
    )
    # Multiply a sample's positive_probability when its patient is at/beyond
    # or at/below these age thresholds (stacks with the gender modifier, not
    # with each other).
    elderly_age_threshold: float = 65.0
    elderly_positivity_modifier: float = 1.2
    young_age_threshold: float = 5.0
    young_positivity_modifier: float = 1.15

    # --- Staffing (roles per Background/Microbiology Context) -------------
    # HSSW: receive/book in samples, accession, plate, set up susceptibility
    # testing.
    num_hssw: int = 5
    # BMS: read initial plates and susceptibilities, enter results on the LIS.
    num_bms: int = 3
    # Clinical microbiologists: verify/sign off results on the LIS.
    num_clinical_microbiologists: int = 1
    # Blood culture bottles incubate in dedicated blood-culture cabinets,
    # separate from the general plate incubators used by every other sample
    # type (and by blood culture subcultures once a bottle flags positive -
    # see processes.sample_journey). Capacities reflect physical lab storage.
    num_blood_culture_incubator_slots: int = 2200
    num_plate_incubator_slots: int = 5000
    num_identification_analyzers: int = 1
    # Each sample currently occupies exactly one plate-incubator slot per
    # incubation stage, i.e. is modelled as producing a single plate. Real
    # samples are plated onto several media types at once (e.g. blood agar,
    # chocolate agar, a selective/differential plate) and so actually consume
    # several plate-incubator slots concurrently. This will need to become a
    # per-sample-type plate count that scales incubator slot consumption
    # accordingly - left at 1 for now.
    plates_per_sample: int = 1

    # --- Process durations (mean, stdev) in minutes ------------------------
    reception_time: tuple[float, float] = (3.0, 1.0)
    accessioning_time: tuple[float, float] = (4.0, 1.5)
    plating_time: tuple[float, float] = (6.0, 2.0)
    incubation_time: tuple[float, float] = (18 * 60, 2 * 60)
    reading_time: tuple[float, float] = (5.0, 2.0)
    susceptibility_setup_time: tuple[float, float] = (20.0, 5.0)
    sensitivity_incubation_time: tuple[float, float] = (16 * 60, 2 * 60)
    sensitivity_reading_time: tuple[float, float] = (8.0, 3.0)
    result_entry_time: tuple[float, float] = (4.0, 1.5)
    verification_time: tuple[float, float] = (5.0, 2.0)
