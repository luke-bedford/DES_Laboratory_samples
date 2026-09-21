"""Maps a real result's free-text organism name to the simulation's small
Organism enum (see lab_sim/entities.py). Anything that doesn't match a known
genus/species substring maps to Organism.OTHER, matching the model's existing
granularity - it only names six specific organisms.
"""

from lab_sim.entities import Organism

# (substring matched case-insensitively against the free-text result, Organism).
# Specific enough that match order doesn't matter.
_ORGANISM_SUBSTRINGS: list[tuple[str, Organism]] = [
    ("escherichia coli", Organism.ESCHERICHIA_COLI),
    ("staphylococcus aureus", Organism.STAPHYLOCOCCUS_AUREUS),
    ("pseudomonas aeruginosa", Organism.PSEUDOMONAS_AERUGINOSA),
    ("klebsiella pneumoniae", Organism.KLEBSIELLA_PNEUMONIAE),
    ("enterococcus", Organism.ENTEROCOCCUS_SPP),
    ("candida", Organism.CANDIDA_SPP),
]


def map_organism(organism_text: str) -> Organism:
    lowered = organism_text.lower()
    for substring, organism in _ORGANISM_SUBSTRINGS:
        if substring in lowered:
            return organism
    return Organism.OTHER
