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
    """Pathogens the model can assign to a positive culture. A placeholder
    set, intended to be replaced or extended once real isolate-frequency
    data is available."""

    ESCHERICHIA_COLI = auto()
    STAPHYLOCOCCUS_AUREUS = auto()
    PSEUDOMONAS_AERUGINOSA = auto()
    KLEBSIELLA_PNEUMONIAE = auto()
    ENTEROCOCCUS_SPP = auto()
    CANDIDA_SPP = auto()
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
