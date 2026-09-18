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
    """Placeholder profiles reflecting rough, plausible NHS microbiology
    patterns. Per Background/Microbiology Context, arrival rates and
    positivity/organism mixes are eventually meant to be inferred from real
    testing data rather than estimated here.
    """

    return {
        SampleType.BLOOD_CULTURE: SampleTypeProfile(
            mean_interarrival_minutes=40.0,
            batched=False,
            positive_probability=0.12,
            organism_weights={
                Organism.STAPHYLOCOCCUS_AUREUS: 0.35,
                Organism.ESCHERICHIA_COLI: 0.25,
                Organism.ENTEROCOCCUS_SPP: 0.15,
                Organism.KLEBSIELLA_PNEUMONIAE: 0.15,
                Organism.OTHER: 0.10,
            },
        ),
        SampleType.TISSUE: SampleTypeProfile(
            mean_interarrival_minutes=120.0,
            batched=False,
            positive_probability=0.25,
            organism_weights={
                Organism.STAPHYLOCOCCUS_AUREUS: 0.40,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.20,
                Organism.ESCHERICHIA_COLI: 0.15,
                Organism.OTHER: 0.25,
            },
        ),
        SampleType.URINE: SampleTypeProfile(
            mean_interarrival_minutes=70.0,
            batched=True,
            positive_probability=0.30,
            organism_weights={
                Organism.ESCHERICHIA_COLI: 0.50,
                Organism.KLEBSIELLA_PNEUMONIAE: 0.15,
                Organism.ENTEROCOCCUS_SPP: 0.15,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.10,
                Organism.OTHER: 0.10,
            },
            # Urinary tract infections are diagnosed more often in women.
            gender_positivity_modifier={Gender.FEMALE: 1.4, Gender.MALE: 0.7},
        ),
        SampleType.SWAB: SampleTypeProfile(
            mean_interarrival_minutes=120.0,
            batched=True,
            positive_probability=0.40,
            organism_weights={
                Organism.STAPHYLOCOCCUS_AUREUS: 0.45,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.20,
                Organism.OTHER: 0.35,
            },
        ),
        SampleType.STOOL: SampleTypeProfile(
            mean_interarrival_minutes=240.0,
            batched=True,
            positive_probability=0.15,
            # Enteric pathogens (Salmonella, Campylobacter, ...) aren't
            # modelled individually yet.
            organism_weights={Organism.OTHER: 1.0},
        ),
        SampleType.SPUTUM: SampleTypeProfile(
            mean_interarrival_minutes=240.0,
            batched=True,
            positive_probability=0.30,
            organism_weights={
                Organism.STAPHYLOCOCCUS_AUREUS: 0.20,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.25,
                Organism.KLEBSIELLA_PNEUMONIAE: 0.20,
                Organism.OTHER: 0.35,
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
    # Overnight culture incubation alone takes ~18h, so a useful run needs to
    # span multiple days rather than a single shift for samples to complete.
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
