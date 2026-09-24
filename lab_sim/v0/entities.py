import itertools
from dataclasses import dataclass, field
from enum import Enum, auto


_id_counter = itertools.count(1)
_patient_id_counter = itertools.count(1)


class SampleType(Enum):
    BLOOD_CULTURE = auto()
    TISSUE = auto()
    URINE = auto()
    SWAB = auto()
    STOOL = auto()
    SPUTUM = auto()


class Priority(Enum):
    ROUTINE = auto()
    URGENT = auto()


class Gender(Enum):
    FEMALE = auto()
    MALE = auto()


class Organism(Enum):
    """Pathogens (and a couple of non-specific culture calls) the model can
    assign to a positive culture. Extended from the original placeholder set
    to include every organism with a count over 100 in
    Data/Received_sample_data/Received_sample_data.xlsx (see
    analysis/organism_mapping.py, which maps the real free-text result to
    these) - anything rarer still falls under OTHER."""

    ESCHERICHIA_COLI = auto()
    STAPHYLOCOCCUS_AUREUS = auto()
    STAPHYLOCOCCUS_EPIDERMIDIS = auto()
    PSEUDOMONAS_AERUGINOSA = auto()
    PSEUDOMONAS_SPP = auto()
    KLEBSIELLA_PNEUMONIAE = auto()
    KLEBSIELLA_OXYTOCA = auto()
    ENTEROCOCCUS_SPP = auto()
    CANDIDA_SPP = auto()
    STREPTOCOCCUS_AGALACTIAE = auto()
    STREPTOCOCCUS_DYSGALACTIAE = auto()
    PROTEUS_SPP = auto()
    ENTEROBACTER_HORMAECHEI = auto()
    CITROBACTER_KOSERI = auto()
    HAEMOPHILUS_INFLUENZAE = auto()
    TRICHOPHYTON_RUBRUM = auto()
    MIXED_SKIN_FLORA = auto()
    MIXED_GRAM_NEGATIVE_FLORA = auto()
    HEAVY_MIXED_GROWTH = auto()
    OTHER = auto()


@dataclass
class Patient:
    """The patient a sample was taken from. For now each sample comes from
    its own unique patient; linking repeat samples to a shared patient is a
    future extension (see Background/Microbiology Context)."""

    id: int = field(default_factory=lambda: next(_patient_id_counter))
    age: float = 50.0
    gender: Gender = Gender.FEMALE


@dataclass
class Sample:
    id: int = field(default_factory=lambda: next(_id_counter))
    sample_type: SampleType = SampleType.SWAB
    priority: Priority = Priority.ROUTINE
    patient: Patient = field(default_factory=Patient)
    arrival_time: float = 0.0
    is_culture_positive: bool | None = None
    organism: Organism | None = None
    timestamps: dict[str, float] = field(default_factory=dict)

    def mark(self, event_name: str, sim_time: float) -> None:
        self.timestamps[event_name] = sim_time

    def turnaround_time(self, end_event: str = "reported") -> float | None:
        end = self.timestamps.get(end_event)
        if end is None:
            return None
        return end - self.arrival_time
