"""Pydantic-free embodiment catalog view.

Hot-path 3T / CI fuzz imports this module so catalog + IP invariants
run when `pydantic` is missing (restricted egress / offline Cloud Agent).
Full resolve still lives in embodiment_service (Pydantic models).
"""

from __future__ import annotations

from typing import NamedTuple


class LiteArchetype(NamedTuple):
    id: str
    name: str
    blurb: str


# Keep id / name / blurb aligned with embodiment_catalog.ARCHETYPES.
ARCHETYPE_LITE: dict[str, LiteArchetype] = {
    "diamond_arc": LiteArchetype(
        "diamond_arc",
        "Diamond Arc",
        "Original arena runner built for diamond-lane sprints.",
    ),
    "court_pulse": LiteArchetype(
        "court_pulse",
        "Court Pulse",
        "Original vertical jumper for half-court arenas.",
    ),
    "grid_surge": LiteArchetype(
        "grid_surge",
        "Grid Surge",
        "Original line-breaker for yard-grid arenas.",
    ),
    "ice_vector": LiteArchetype(
        "ice_vector",
        "Ice Vector",
        "Original glide striker for rink-vector arenas.",
    ),
    "pitch_orbit": LiteArchetype(
        "pitch_orbit",
        "Pitch Orbit",
        "Original midfield orbiter for pitch arenas.",
    ),
    "neutral_echo": LiteArchetype(
        "neutral_echo",
        "Neutral Echo",
        "Fallback original avatar when sport class is unknown.",
    ),
}

# Keyword → archetype (manufacturer / set cues only; no logo assets).
SPORT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "diamond_arc": (
        "baseball",
        "mlb",
        "topps",
        "bowman",
        "donruss",
        "stadium club",
        "heritage",
        "update",
        "chrome",
        "gypsy queen",
    ),
    "court_pulse": (
        "basketball",
        "nba",
        "hoops",
        "prizm",
        "select",
        "mosaic",
        "optic",
        "chronicles",
        "court kings",
    ),
    "grid_surge": (
        "football",
        "nfl",
        "panini",
        "score",
        "absolute",
        "contenders",
        "gridiron",
        "leaf",
    ),
    "ice_vector": (
        "hockey",
        "nhl",
        "upper deck",
        "sp authentic",
        "opc",
        "ice",
    ),
    "pitch_orbit": (
        "soccer",
        "football club",
        "futera",
        "panini soccer",
        "mls",
        "premier",
        "fifa",
    ),
}
