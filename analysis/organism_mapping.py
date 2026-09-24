"""Maps a real result's free-text organism name to the simulation's
Organism enum (see lab_sim/v1/entities.py). Anything that doesn't match a
known substring maps to Organism.OTHER.

Match order matters: species-specific entries (e.g. "pseudomonas
aeruginosa") must come before the genus-level fallback for the same genus
(e.g. "pseudomonas" -> PSEUDOMONAS_SPP), since map_organism returns the
first match.
"""

from lab_sim.v1.entities import Organism

_ORGANISM_SUBSTRINGS: list[tuple[str, Organism]] = [
    ("escherichia coli", Organism.ESCHERICHIA_COLI),
    ("staphylococcus aureus", Organism.STAPHYLOCOCCUS_AUREUS),
    ("staphylococcus epidermidis", Organism.STAPHYLOCOCCUS_EPIDERMIDIS),
    ("pseudomonas aeruginosa", Organism.PSEUDOMONAS_AERUGINOSA),
    ("pseudomonas", Organism.PSEUDOMONAS_SPP),
    ("klebsiella pneumoniae", Organism.KLEBSIELLA_PNEUMONIAE),
    ("klebsiella oxytoca", Organism.KLEBSIELLA_OXYTOCA),
    ("enterococcus", Organism.ENTEROCOCCUS_SPP),
    ("candida", Organism.CANDIDA_SPP),
    ("streptococcus agalactiae", Organism.STREPTOCOCCUS_AGALACTIAE),
    ("streptococcus dysgalactiae", Organism.STREPTOCOCCUS_DYSGALACTIAE),
    ("proteus", Organism.PROTEUS_SPP),
    ("enterobacter hormaechei", Organism.ENTEROBACTER_HORMAECHEI),
    ("citrobacter koseri", Organism.CITROBACTER_KOSERI),
    ("haemophilus influenzae", Organism.HAEMOPHILUS_INFLUENZAE),
    ("trichophyton rubrum", Organism.TRICHOPHYTON_RUBRUM),
    ("mixed skin flora", Organism.MIXED_SKIN_FLORA),
    ("mixed gram-negative flora", Organism.MIXED_GRAM_NEGATIVE_FLORA),
    ("heavy mixed growth", Organism.HEAVY_MIXED_GROWTH),
]


def map_organism(organism_text: str) -> Organism:
    lowered = organism_text.lower()
    for substring, organism in _ORGANISM_SUBSTRINGS:
        if substring in lowered:
            return organism
    return Organism.OTHER
