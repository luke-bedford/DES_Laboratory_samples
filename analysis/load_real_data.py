"""Loads and cleans the real specimen-results dataset for distribution fitting.

See Data/Received_sample_data/Received_sample_data.xlsx. Row-cleaning decisions
here (interim-result filtering, the "no growth" positivity classifier, the
Multi-site handling) come from hand-verifying the raw data against the model's
assumptions - see the plan this analysis was built from for the reasoning.

IMPORTANT: anon_received is the sample's booking-in time (when reception logs
it on the LIS), not the moment the physical sample reaches the lab - see
TODO.md. Anything derived from received_days (inter-arrival gaps, the
day-of-week NHPP review) is really describing the booking-in process, not the
true external arrival process lab_sim/arrivals.py models; turnaround
(verified - received) likewise excludes whatever wait happens before
booking-in.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import openpyxl

from lab_sim.entities import SampleType

DEFAULT_DATA_PATH = Path("Data/Received_sample_data/Received_sample_data.xlsx")

# Real specimen_type strings -> SampleType, for the 6 types the simulation
# currently models.
SPECIMEN_TYPE_MAP: dict[str, SampleType] = {
    "Blood": SampleType.BLOOD_CULTURE,
    "Tissue": SampleType.TISSUE,
    "Urine": SampleType.URINE,
    "Swab": SampleType.SWAB,
    "Stool": SampleType.STOOL,
    "Sputum": SampleType.SPUTUM,
}

# Not in SampleType, but analyzed alongside the modeled types: almost
# certainly genuine multi-site screening swabs (e.g. MRSA/CPE screens) rather
# than a data artifact, but the simulation doesn't model it yet.
MULTI_SITE_LABEL = "Multi-site"

# The order every per-group table/plot in this analysis iterates in.
ANALYSIS_GROUPS: list[str] = [t.name for t in SPECIMEN_TYPE_MAP.values()] + [
    MULTI_SITE_LABEL
]

# A result containing one of these substrings is a preliminary report
# superseded by a later final row for the same culture (observed only on a
# handful of Blood rows) - drop it so one culture isn't double-counted.
_INTERIM_MARKERS = ("continuing", "to follow")


@dataclass(frozen=True)
class RealResultRow:
    specimen_type_raw: str
    # ANALYSIS_GROUPS entry this row belongs to, or "Other" if it's one of the
    # ~18 real specimen types this analysis doesn't cover.
    analysis_group: str
    mapped_sample_type: SampleType | None
    is_positive: bool
    # The raw result text, only populated when is_positive (used for organism
    # mapping) - None for a "no growth" result.
    organism_text: str | None
    received_days: float  # booking-in time, not physical arrival - see module docstring
    verified_days: float
    turnaround_days: float
    day_of_week: str


def _is_interim(result: str) -> bool:
    lowered = result.lower()
    return any(marker in lowered for marker in _INTERIM_MARKERS)


_NEGATIVE_MARKERS = ("no significant growth", "no growth")


def _is_negative(result: str) -> bool:
    # Two distinct phrasings in the data: "No significant growth" (agar-culture
    # types) and blood culture's "No growth; incubation completed...". Neither
    # is a substring of the other ("no growth" alone does NOT match "no
    # significant growth" - the word "significant" breaks it), so both must be
    # checked explicitly.
    lowered = result.lower()
    return any(marker in lowered for marker in _NEGATIVE_MARKERS)


def load_rows(path: Path = DEFAULT_DATA_PATH) -> list[RealResultRow]:
    """Reads and cleans the raw dataset: drops interim/preliminary rows and
    rows missing a specimen type or a valid received/verified time, then
    classifies each remaining row as positive/negative and assigns it to an
    analysis group."""

    workbook = openpyxl.load_workbook(path, data_only=True)
    sheet = workbook.active

    rows: list[RealResultRow] = []
    header: tuple | None = None
    for raw_row in sheet.iter_rows(values_only=True):
        if header is None:
            header = raw_row
            continue
        record = dict(zip(header, raw_row))

        specimen_type = record.get("specimen_type")
        result = record.get("result")
        received = record.get("anon_received")
        verified = record.get("anon_verified")
        if not specimen_type or not result or received is None or verified is None:
            continue
        if _is_interim(str(result)):
            continue
        try:
            received_days = float(received)
            verified_days = float(verified)
        except (TypeError, ValueError):
            continue

        mapped = SPECIMEN_TYPE_MAP.get(specimen_type)
        if mapped is not None:
            group = mapped.name
        elif specimen_type == MULTI_SITE_LABEL:
            group = MULTI_SITE_LABEL
        else:
            group = "Other"

        is_negative = _is_negative(str(result))
        rows.append(
            RealResultRow(
                specimen_type_raw=specimen_type,
                analysis_group=group,
                mapped_sample_type=mapped,
                is_positive=not is_negative,
                organism_text=None if is_negative else str(result),
                received_days=received_days,
                verified_days=verified_days,
                turnaround_days=verified_days - received_days,
                day_of_week=str(record.get("day_received") or ""),
            )
        )
    return rows


def rows_by_group(rows: list[RealResultRow]) -> dict[str, list[RealResultRow]]:
    grouped: dict[str, list[RealResultRow]] = {group: [] for group in ANALYSIS_GROUPS}
    for row in rows:
        if row.analysis_group in grouped:
            grouped[row.analysis_group].append(row)
    return grouped


def unmapped_type_counts(rows: list[RealResultRow]) -> dict[str, int]:
    """Real specimen types that are neither modeled nor Multi-site, with row
    counts - for the 'not yet modeled' reference table."""

    counts: dict[str, int] = {}
    for row in rows:
        if row.analysis_group == "Other":
            counts[row.specimen_type_raw] = counts.get(row.specimen_type_raw, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
