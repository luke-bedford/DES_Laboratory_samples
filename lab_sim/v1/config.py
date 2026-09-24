from dataclasses import dataclass, field

from .entities import Gender, Organism, Priority, SampleType

# v0 was the original 6-sample-type, constant-rate-Poisson model (tagged
# `model-v0` in git). v1 covers every real specimen type with a count over
# 20 (see SampleType) and replaces constant-rate arrivals with the
# day-of-week NHPP (see arrivals.py) - see this module's docstrings for what
# changed and how it was calibrated.
MODEL_VERSION = "v1"


@dataclass
class SampleTypeProfile:
    """Every distributional assumption specific to one specimen type,
    gathered in one place so a new sample type - or updated real-world
    arrival/positivity data - only needs changes here.
    """

    # Real arrivals/day by weekday (Monday..Sunday), event-level - the
    # day-of-week NHPP rate this type's arrivals are drawn from
    # (arrivals.py). For a batched type (see `batched`) this is the rate of
    # arrival *events* (batches), not individual samples. Replaces a single
    # constant rate since every type's real arrival rate depends
    # significantly on weekday (diagnostics/v1/real_data_fit_report.html's
    # day-of-week section).
    arrivals_per_day_by_weekday: dict[str, float]

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
    """Every field on every profile here - arrival rate, positivity, and
    organism mix - is calibrated directly from the real dataset
    (Data/Received_sample_data/Received_sample_data.xlsx), grouped by each
    real specimen type's exact raw string (see analysis/load_real_data.py).
    Regenerate by re-running the day_of_week_rates/organism_counts
    computations in analysis/distribution_fits.py per group if the dataset
    changes; there's no runtime dependency on Data/ here, since it's
    gitignored and not guaranteed to exist for every checkout - these are
    static, hand-transcribed snapshots of that calibration.

    arrivals_per_day_by_weekday is row-level real data divided by the mean
    batch size (sum(batch_size_range)/2 = 4) for batched types, to convert
    real per-specimen rates into the per-arrival-*event* rate arrivals.py
    actually draws from. For MULTI_SITE specifically, that /4 reproduces the
    real row-level volume but isn't itself a calibrated batch size - the
    real dataset has no episode linkage to confirm samples genuinely arrive
    in batches of ~4; batching Multi-site (unlike the other new types) was a
    deliberate modeling choice, and its event rate is coupled to
    batch_size_range - changing that shared range later silently rescales
    Multi-site's (and every other batched type's) arrival volume.

    gender_positivity_modifier isn't calibrated for any new type - the real
    dataset has no gender field (see TODO.md) - so only URINE's existing
    domain-motivated modifier is set.
    """

    return {
        SampleType.BLOOD_CULTURE: SampleTypeProfile(
            arrivals_per_day_by_weekday={
                "Monday": 96.7500,
                "Tuesday": 110.2000,
                "Wednesday": 113.4000,
                "Thursday": 106.6667,
                "Friday": 128.2222,
                "Saturday": 81.3846,
                "Sunday": 67.6667,
            },
            batched=False,
            positive_probability=0.0931,
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
            arrivals_per_day_by_weekday={
                "Monday": 9.2222,
                "Tuesday": 10.6667,
                "Wednesday": 9.0000,
                "Thursday": 6.8182,
                "Friday": 6.7000,
                "Saturday": 5.7273,
                "Sunday": 2.7000,
            },
            batched=False,
            positive_probability=0.7066,
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
            arrivals_per_day_by_weekday={
                "Monday": 30.7250,
                "Tuesday": 31.8269,
                "Wednesday": 27.2500,
                "Thursday": 48.9375,
                "Friday": 37.8958,
                "Saturday": 31.2045,
                "Sunday": 26.7750,
            },
            batched=True,
            positive_probability=0.4978,
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
            arrivals_per_day_by_weekday={
                "Monday": 75.8077,
                "Tuesday": 73.3958,
                "Wednesday": 120.2222,
                "Thursday": 66.0625,
                "Friday": 89.5833,
                "Saturday": 62.7727,
                "Sunday": 49.9167,
            },
            batched=True,
            positive_probability=0.2925,
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
            arrivals_per_day_by_weekday={
                "Monday": 9.5227,
                "Tuesday": 12.6818,
                "Wednesday": 15.7727,
                "Thursday": 10.8409,
                "Friday": 16.4318,
                "Saturday": 15.9444,
                "Sunday": 9.3269,
            },
            batched=True,
            positive_probability=0.0570,
            # Real positives are only ever E. coli or Other (which covers
            # enteric pathogens like Salmonella/Campylobacter - none of them
            # individually clear the >20-count threshold that got a
            # SampleType, or >100 for Organism, see lab_sim/entities.py).
            organism_weights={
                Organism.OTHER: 0.7455,
                Organism.ESCHERICHIA_COLI: 0.2545,
            },
        ),
        SampleType.SPUTUM: SampleTypeProfile(
            arrivals_per_day_by_weekday={
                "Monday": 9.4167,
                "Tuesday": 15.2500,
                "Wednesday": 14.5000,
                "Thursday": 9.3654,
                "Friday": 12.3750,
                "Saturday": 13.7250,
                "Sunday": 5.0227,
            },
            batched=True,
            positive_probability=0.4484,
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
        SampleType.MULTI_SITE: SampleTypeProfile(
            # Batched by modeling choice, not real evidence - see this
            # function's docstring on the /4 coupling to batch_size_range.
            arrivals_per_day_by_weekday={
                "Monday": 55.7500,
                "Tuesday": 53.6042,
                "Wednesday": 66.9250,
                "Thursday": 61.2500,
                "Friday": 35.9583,
                "Saturday": 54.0250,
                "Sunday": 36.1667,
            },
            batched=True,
            positive_probability=0.0119,
            organism_weights={
                Organism.STAPHYLOCOCCUS_AUREUS: 1.0000,
            },
        ),
        SampleType.NAIL: SampleTypeProfile(
            # Zero real rows on Saturday/Sunday - a routine outpatient
            # dermatophyte-testing collection, not a 24/7 service.
            arrivals_per_day_by_weekday={
                "Monday": 23.0000,
                "Tuesday": 21.7143,
                "Wednesday": 15.2500,
                "Thursday": 13.2222,
                "Friday": 17.1667,
                "Saturday": 0.0,
                "Sunday": 0.0,
            },
            batched=False,
            positive_probability=0.4551,
            organism_weights={
                Organism.TRICHOPHYTON_RUBRUM: 0.5385,
                Organism.OTHER: 0.2475,
                Organism.CANDIDA_SPP: 0.2140,
            },
        ),
        SampleType.BODY_FLUID: SampleTypeProfile(
            arrivals_per_day_by_weekday={
                "Monday": 5.4444,
                "Tuesday": 7.4444,
                "Wednesday": 5.6923,
                "Thursday": 5.6000,
                "Friday": 6.5556,
                "Saturday": 5.0000,
                "Sunday": 2.2222,
            },
            batched=False,
            positive_probability=0.6421,
            organism_weights={
                Organism.OTHER: 0.3115,
                Organism.ESCHERICHIA_COLI: 0.1844,
                Organism.STAPHYLOCOCCUS_AUREUS: 0.1189,
                Organism.MIXED_SKIN_FLORA: 0.0820,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.0574,
                Organism.MIXED_GRAM_NEGATIVE_FLORA: 0.0492,
                Organism.ENTEROCOCCUS_SPP: 0.0410,
                Organism.KLEBSIELLA_PNEUMONIAE: 0.0369,
                Organism.STAPHYLOCOCCUS_EPIDERMIDIS: 0.0246,
                Organism.ENTEROBACTER_HORMAECHEI: 0.0246,
                Organism.PROTEUS_SPP: 0.0205,
                Organism.CANDIDA_SPP: 0.0205,
                Organism.KLEBSIELLA_OXYTOCA: 0.0164,
                Organism.CITROBACTER_KOSERI: 0.0041,
                Organism.STREPTOCOCCUS_AGALACTIAE: 0.0041,
                Organism.STREPTOCOCCUS_DYSGALACTIAE: 0.0041,
            },
        ),
        SampleType.BREAST_MILK: SampleTypeProfile(
            arrivals_per_day_by_weekday={
                "Monday": 6.0000,
                "Tuesday": 10.5000,
                "Wednesday": 10.1667,
                "Thursday": 10.1667,
                "Friday": 12.7143,
                "Saturday": 6.0000,
                "Sunday": 10.0000,
            },
            batched=False,
            positive_probability=0.0994,
            organism_weights={
                Organism.OTHER: 0.9714,
                Organism.STAPHYLOCOCCUS_AUREUS: 0.0286,
            },
        ),
        SampleType.BRONCHO_ALVEOLAR_LAVAGE: SampleTypeProfile(
            arrivals_per_day_by_weekday={
                "Monday": 2.8750,
                "Tuesday": 2.7143,
                "Wednesday": 6.5000,
                "Thursday": 5.9167,
                "Friday": 6.9000,
                "Saturday": 4.2222,
                "Sunday": 1.8000,
            },
            batched=False,
            positive_probability=0.7239,
            organism_weights={
                Organism.OTHER: 0.4175,
                Organism.CANDIDA_SPP: 0.1340,
                Organism.STAPHYLOCOCCUS_AUREUS: 0.0928,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.0876,
                Organism.HAEMOPHILUS_INFLUENZAE: 0.0722,
                Organism.MIXED_GRAM_NEGATIVE_FLORA: 0.0619,
                Organism.ESCHERICHIA_COLI: 0.0567,
                Organism.KLEBSIELLA_PNEUMONIAE: 0.0206,
                Organism.ENTEROCOCCUS_SPP: 0.0206,
                Organism.KLEBSIELLA_OXYTOCA: 0.0155,
                Organism.ENTEROBACTER_HORMAECHEI: 0.0155,
                Organism.CITROBACTER_KOSERI: 0.0052,
            },
        ),
        SampleType.ENVIRONMENTAL: SampleTypeProfile(
            arrivals_per_day_by_weekday={
                "Monday": 10.0000,
                "Tuesday": 13.3333,
                "Wednesday": 13.3333,
                "Thursday": 1.0000,
                "Friday": 7.3333,
                "Saturday": 5.1667,
                "Sunday": 5.7500,
            },
            batched=False,
            # Near-universally positive: environmental swabs are largely
            # surveillance samples expected to grow something, unlike
            # patient specimens.
            positive_probability=0.9904,
            organism_weights={
                Organism.OTHER: 0.8932,
                Organism.STAPHYLOCOCCUS_EPIDERMIDIS: 0.0388,
                Organism.PSEUDOMONAS_SPP: 0.0291,
                Organism.CANDIDA_SPP: 0.0243,
                Organism.MIXED_GRAM_NEGATIVE_FLORA: 0.0146,
            },
        ),
        SampleType.STEM_CELLS: SampleTypeProfile(
            # Zero real rows on Saturday/Sunday, and zero real positives
            # (0/184) - stem-cell product sterility testing, expected to
            # come back clean.
            arrivals_per_day_by_weekday={
                "Monday": 8.0000,
                "Tuesday": 4.0000,
                "Wednesday": 6.5000,
                "Thursday": 7.0000,
                "Friday": 7.4286,
                "Saturday": 0.0,
                "Sunday": 0.0,
            },
            batched=False,
            positive_probability=0.0,
            organism_weights={},
        ),
        SampleType.DRAIN_TUBE_OTHER_DEVICE: SampleTypeProfile(
            arrivals_per_day_by_weekday={
                "Monday": 3.0000,
                "Tuesday": 2.1429,
                "Wednesday": 1.5556,
                "Thursday": 2.2857,
                "Friday": 2.6000,
                "Saturday": 2.7500,
                "Sunday": 2.0000,
            },
            batched=False,
            positive_probability=0.6642,
            organism_weights={
                Organism.OTHER: 0.3736,
                Organism.MIXED_SKIN_FLORA: 0.1758,
                Organism.STAPHYLOCOCCUS_EPIDERMIDIS: 0.0879,
                Organism.CANDIDA_SPP: 0.0769,
                Organism.STAPHYLOCOCCUS_AUREUS: 0.0549,
                Organism.KLEBSIELLA_PNEUMONIAE: 0.0549,
                Organism.ENTEROCOCCUS_SPP: 0.0440,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.0330,
                Organism.MIXED_GRAM_NEGATIVE_FLORA: 0.0220,
                Organism.ENTEROBACTER_HORMAECHEI: 0.0220,
                Organism.ESCHERICHIA_COLI: 0.0220,
                Organism.CITROBACTER_KOSERI: 0.0110,
                Organism.KLEBSIELLA_OXYTOCA: 0.0110,
                Organism.PROTEUS_SPP: 0.0110,
            },
        ),
        SampleType.FLUID: SampleTypeProfile(
            arrivals_per_day_by_weekday={
                "Monday": 2.1667,
                "Tuesday": 2.0000,
                "Wednesday": 2.0000,
                "Thursday": 1.1429,
                "Friday": 1.7500,
                "Saturday": 2.0000,
                "Sunday": 1.0000,
            },
            batched=False,
            positive_probability=0.6667,
            organism_weights={
                Organism.OTHER: 0.3235,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.1765,
                Organism.KLEBSIELLA_PNEUMONIAE: 0.1176,
                Organism.STAPHYLOCOCCUS_EPIDERMIDIS: 0.0588,
                Organism.ENTEROBACTER_HORMAECHEI: 0.0588,
                Organism.ENTEROCOCCUS_SPP: 0.0588,
                Organism.STAPHYLOCOCCUS_AUREUS: 0.0588,
                Organism.MIXED_SKIN_FLORA: 0.0294,
                Organism.MIXED_GRAM_NEGATIVE_FLORA: 0.0294,
                Organism.ESCHERICHIA_COLI: 0.0294,
                Organism.PSEUDOMONAS_SPP: 0.0294,
                Organism.PROTEUS_SPP: 0.0294,
            },
        ),
        SampleType.POST_MORTEM_SWAB: SampleTypeProfile(
            arrivals_per_day_by_weekday={
                "Monday": 1.0000,
                "Tuesday": 2.5000,
                "Wednesday": 1.6667,
                "Thursday": 1.5000,
                "Friday": 1.5000,
                "Saturday": 3.0000,
                "Sunday": 2.0000,
            },
            batched=False,
            positive_probability=0.9524,
            organism_weights={
                Organism.OTHER: 0.2750,
                Organism.MIXED_GRAM_NEGATIVE_FLORA: 0.2000,
                Organism.MIXED_SKIN_FLORA: 0.1500,
                Organism.ENTEROCOCCUS_SPP: 0.1250,
                Organism.STAPHYLOCOCCUS_AUREUS: 0.0750,
                Organism.PSEUDOMONAS_SPP: 0.0500,
                Organism.CANDIDA_SPP: 0.0500,
                Organism.STAPHYLOCOCCUS_EPIDERMIDIS: 0.0250,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.0250,
                Organism.ENTEROBACTER_HORMAECHEI: 0.0250,
            },
        ),
        SampleType.CEREBROSPINAL_FLUID: SampleTypeProfile(
            arrivals_per_day_by_weekday={
                "Monday": 1.0000,
                "Tuesday": 1.2500,
                "Wednesday": 1.3333,
                "Thursday": 1.2500,
                "Friday": 1.5000,
                "Saturday": 1.0000,
                "Sunday": 1.0000,
            },
            batched=False,
            positive_probability=0.8000,
            organism_weights={
                Organism.OTHER: 0.6000,
                Organism.CANDIDA_SPP: 0.1500,
                Organism.STAPHYLOCOCCUS_EPIDERMIDIS: 0.1000,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.0500,
                Organism.STAPHYLOCOCCUS_AUREUS: 0.0500,
                Organism.STREPTOCOCCUS_AGALACTIAE: 0.0500,
            },
        ),
        SampleType.SYNOVIAL_FLUID: SampleTypeProfile(
            arrivals_per_day_by_weekday={
                "Monday": 1.0000,
                "Tuesday": 1.0000,
                "Wednesday": 1.0000,
                "Thursday": 1.5000,
                "Friday": 1.0000,
                "Saturday": 1.3333,
                "Sunday": 1.0000,
            },
            batched=False,
            positive_probability=0.1818,
            organism_weights={
                Organism.STAPHYLOCOCCUS_AUREUS: 0.5000,
                Organism.PROTEUS_SPP: 0.2500,
                Organism.STAPHYLOCOCCUS_EPIDERMIDIS: 0.2500,
            },
        ),
        SampleType.HAIR: SampleTypeProfile(
            # Zero real rows on Saturday/Sunday - same routine-outpatient
            # pattern as NAIL.
            arrivals_per_day_by_weekday={
                "Monday": 2.5000,
                "Tuesday": 1.2500,
                "Wednesday": 1.2000,
                "Thursday": 1.0000,
                "Friday": 1.0000,
                "Saturday": 0.0,
                "Sunday": 0.0,
            },
            batched=False,
            positive_probability=0.0455,
            organism_weights={
                Organism.CANDIDA_SPP: 1.0000,
            },
        ),
        SampleType.OTHER: SampleTypeProfile(
            # Catch-all for every real specimen type with n <= 20 (Dialysis
            # fluid, Transport solution, Other, Vitreous humor, Aspirate,
            # Tissue-Post mortem, Tissue-Biopsy - 31 rows total), calibrated
            # as one combined group rather than left unmodeled.
            arrivals_per_day_by_weekday={
                "Monday": 1.0000,
                "Tuesday": 1.0000,
                "Wednesday": 1.0000,
                "Thursday": 1.0000,
                "Friday": 1.0000,
                "Saturday": 1.4000,
                "Sunday": 2.6667,
            },
            batched=False,
            positive_probability=0.6452,
            organism_weights={
                Organism.ENTEROCOCCUS_SPP: 0.3000,
                Organism.OTHER: 0.2500,
                Organism.PSEUDOMONAS_AERUGINOSA: 0.1000,
                Organism.PSEUDOMONAS_SPP: 0.1000,
                Organism.CANDIDA_SPP: 0.1000,
                Organism.STAPHYLOCOCCUS_EPIDERMIDIS: 0.0500,
                Organism.PROTEUS_SPP: 0.0500,
                Organism.STAPHYLOCOCCUS_AUREUS: 0.0500,
            },
        ),
    }


@dataclass
class SimulationConfig:
    """Every parameter controlling the simulation, gathered in one place so
    the model can be recalibrated without touching any process logic.

    Times are in minutes. Arrivals are a day-of-week non-homogeneous Poisson
    process per sample type (`arrivals.py`, thinning against each
    `SampleTypeProfile.arrivals_per_day_by_weekday`), service times are
    Gaussian (`random.gauss`, floored at 0.1 minutes), and sample
    type/priority/organism/positivity draws are independent categorical or
    Bernoulli trials - see `SampleTypeProfile` for the per-sample-type ones.
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

    # --- Staffing -----------------------------------------------------------
    # Scaled up from model v0's 5/3/1/1/5000 for the v1 specimen-type
    # expansion: adding every real type with n>20 (Multi-site dominates) is
    # a ~38% increase in total daily arrivals overall, and specifically a
    # ~45% increase on the shared plate-incubator/HSSW/BMS/clinical-
    # microbiologist pools (blood culture has its own dedicated incubator
    # and its volume is unaffected by this change) - see
    # lab_sim/entities.py's SampleType docstring and the `model-v0` git tag
    # for the pre-expansion baseline these numbers were scaled from.
    # HSSW: receive/book in samples, accession, plate, set up susceptibility
    # testing.
    num_hssw: int = 7
    # BMS: read initial plates and susceptibilities, enter results on the LIS.
    num_bms: int = 4
    # Clinical microbiologists: verify/sign off results on the LIS. Can't
    # scale fractionally at this base (1 -> 1.38); doubling is the smallest
    # change that isn't flat.
    num_clinical_microbiologists: int = 2
    # Blood culture bottles incubate in dedicated blood-culture cabinets,
    # separate from the general plate incubators used by every other sample
    # type (and by blood culture subcultures once a bottle flags positive -
    # see processes.sample_journey). Capacities reflect physical lab storage;
    # unchanged from v0 since blood culture volume itself doesn't change.
    num_blood_culture_incubator_slots: int = 2200
    num_plate_incubator_slots: int = 7230
    num_identification_analyzers: int = 2
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
