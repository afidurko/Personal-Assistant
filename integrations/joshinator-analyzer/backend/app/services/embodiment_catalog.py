"""Original champion archetypes — no franchise characters or logos.

Archetypes are fictional sports-arena personas owned by this project.
Colors are generated per card via hashing; they are not team brand palettes.
"""

from __future__ import annotations

from app.models.embodiment import Archetype, MeshRecipe

# Sport classes are generic activity buckets, not league trademarks.
ARCHETYPES: dict[str, Archetype] = {
    "diamond_arc": Archetype(
        id="diamond_arc",
        name="Diamond Arc",
        sport_class="diamond",
        blurb="Original arena runner built for diamond-lane sprints.",
        actions=["lane_dash", "arc_cut", "retreat"],
        anim_map={
            "lane_dash": "run_burst",
            "arc_cut": "twist_strike",
            "retreat": "backstep",
            "idle": "breathe",
            "hit": "react_hit",
        },
        mesh_defaults=MeshRecipe(
            body="capsule",
            head="sphere",
            accent="ring",
            height=1.4,
            bulk=0.95,
            primary_hex="#2F6FED",
            secondary_hex="#E8F0FF",
            emissive_hex="#6AA8FF",
        ),
        arena_motif="hex_grid",
        base_hp=100,
    ),
    "court_pulse": Archetype(
        id="court_pulse",
        name="Court Pulse",
        sport_class="court",
        blurb="Original vertical jumper for half-court arenas.",
        actions=["lift_shot", "screen_burst", "retreat"],
        anim_map={
            "lift_shot": "jump_release",
            "screen_burst": "plant_push",
            "retreat": "backstep",
            "idle": "breathe",
            "hit": "react_hit",
        },
        mesh_defaults=MeshRecipe(
            body="capsule",
            head="sphere",
            accent="fins",
            height=1.55,
            bulk=1.05,
            primary_hex="#E4572E",
            secondary_hex="#FFE8DF",
            emissive_hex="#FF8A5B",
        ),
        arena_motif="circle_pulse",
        base_hp=110,
    ),
    "grid_surge": Archetype(
        id="grid_surge",
        name="Grid Surge",
        sport_class="gridiron",
        blurb="Original line-breaker for yard-grid arenas.",
        actions=["power_drive", "cut_block", "retreat"],
        anim_map={
            "power_drive": "charge",
            "cut_block": "shoulder_check",
            "retreat": "backstep",
            "idle": "breathe",
            "hit": "react_hit",
        },
        mesh_defaults=MeshRecipe(
            body="capsule",
            head="box",
            accent="spikes",
            height=1.5,
            bulk=1.25,
            primary_hex="#1B8A5A",
            secondary_hex="#E6FFF4",
            emissive_hex="#3DDC97",
        ),
        arena_motif="lane_rings",
        base_hp=120,
    ),
    "ice_vector": Archetype(
        id="ice_vector",
        name="Ice Vector",
        sport_class="ice",
        blurb="Original glide striker for rink-vector arenas.",
        actions=["vector_slash", "edge_spin", "retreat"],
        anim_map={
            "vector_slash": "slash",
            "edge_spin": "spin",
            "retreat": "backstep",
            "idle": "breathe",
            "hit": "react_hit",
        },
        mesh_defaults=MeshRecipe(
            body="cone",
            head="sphere",
            accent="fins",
            height=1.35,
            bulk=0.9,
            primary_hex="#3D7EA6",
            secondary_hex="#E8F7FF",
            emissive_hex="#7EC8E3",
        ),
        arena_motif="circle_pulse",
        base_hp=95,
    ),
    "pitch_orbit": Archetype(
        id="pitch_orbit",
        name="Pitch Orbit",
        sport_class="pitch",
        blurb="Original midfield orbiter for pitch arenas.",
        actions=["orbit_pass", "strike_curve", "retreat"],
        anim_map={
            "orbit_pass": "pass_arc",
            "strike_curve": "kick_curve",
            "retreat": "backstep",
            "idle": "breathe",
            "hit": "react_hit",
        },
        mesh_defaults=MeshRecipe(
            body="capsule",
            head="dodecahedron",
            accent="ring",
            height=1.38,
            bulk=1.0,
            primary_hex="#6B4EFF",
            secondary_hex="#F0ECFF",
            emissive_hex="#A894FF",
        ),
        arena_motif="hex_grid",
        base_hp=105,
    ),
    "neutral_echo": Archetype(
        id="neutral_echo",
        name="Neutral Echo",
        sport_class="neutral",
        blurb="Fallback original avatar when sport class is unknown.",
        actions=["pulse_wave", "scan_burst", "retreat"],
        anim_map={
            "pulse_wave": "wave",
            "scan_burst": "scan",
            "retreat": "backstep",
            "idle": "breathe",
            "hit": "react_hit",
        },
        mesh_defaults=MeshRecipe(
            body="octahedron",
            head="sphere",
            accent="none",
            height=1.25,
            bulk=1.0,
            primary_hex="#5A6678",
            secondary_hex="#EEF1F5",
            emissive_hex="#9AA7B8",
        ),
        arena_motif="circle_pulse",
        base_hp=90,
    ),
}

# Keyword → archetype (manufacturer / set cues only; no logo assets).
SPORT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "diamond_arc": (
        "baseball", "mlb", "topps", "bowman", "donruss", "stadium club",
        "heritage", "update", "chrome", "gypsy queen",
    ),
    "court_pulse": (
        "basketball", "nba", "hoops", "prizm", "select", "mosaic",
        "optic", "chronicles", "court kings",
    ),
    "grid_surge": (
        "football", "nfl", "panini", "score", "absolute", "contenders",
        "gridiron", "leaf",
    ),
    "ice_vector": (
        "hockey", "nhl", "upper deck", "sp authentic", "opc", "ice",
    ),
    "pitch_orbit": (
        "soccer", "football club", "futera", "panini soccer", "mls",
        "premier", "fifa",
    ),
}
