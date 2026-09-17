import itertools
from dataclasses import dataclass, field
from enum import Enum, auto


_id_counter = itertools.count(1)


class SampleType(Enum):
    BLOOD_CULTURE = auto()
    URINE = auto()
    SWAB = auto()
    STOOL = auto()
    SPUTUM = auto()


class Priority(Enum):
    ROUTINE = auto()
    URGENT = auto()


@dataclass
class Sample:
    id: int = field(default_factory=lambda: next(_id_counter))
    sample_type: SampleType = SampleType.SWAB
    priority: Priority = Priority.ROUTINE
    arrival_time: float = 0.0
    is_culture_positive: bool | None = None
    timestamps: dict[str, float] = field(default_factory=dict)

    def mark(self, event_name: str, sim_time: float) -> None:
        self.timestamps[event_name] = sim_time

    def turnaround_time(self, end_event: str = "reported") -> float | None:
        end = self.timestamps.get(end_event)
        if end is None:
            return None
        return end - self.arrival_time
