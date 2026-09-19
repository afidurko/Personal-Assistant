"""IP-safe 3D embodiment models.

All mesh recipes are original procedural parameters — no licensed character
meshes, logos, or franchise assets are referenced or shipped.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MeshRecipe(BaseModel):
    """Procedural geometry description rendered client-side (no binary assets)."""

    body: str = Field(
        description="Primitive body shape: capsule | cone | octahedron | torus"
    )
    head: str = Field(description="Primitive head shape: sphere | box | dodecahedron")
    accent: str = Field(
        description="Accent primitive: ring | spikes | fins | none"
    )
    height: float = Field(ge=0.6, le=2.2, default=1.35)
    bulk: float = Field(ge=0.4, le=1.6, default=1.0)
    primary_hex: str
    secondary_hex: str
    emissive_hex: str


class Embodiment(BaseModel):
    """Resolved 3D actor for a detected card identity."""

    entity_id: str
    archetype_id: str
    display_name: str
    subtitle: str
    sport_class: str
    actions: List[str]
    anim_map: Dict[str, str]
    mesh: MeshRecipe
    arena_motif: str = Field(
        description="Original arena motif id (circle_pulse | hex_grid | lane_rings)"
    )
    hp: Dict[str, int]
    confidence: float = 0.0
    source: str = "joshinator-original-catalog"
    license_note: str = (
        "Original procedural embodiment. No third-party character IP, logos, "
        "or franchise assets."
    )
    card_ref: Optional[Dict] = None


class Archetype(BaseModel):
    """Catalog entry for an original champion archetype."""

    id: str
    name: str
    sport_class: str
    blurb: str
    actions: List[str]
    anim_map: Dict[str, str]
    mesh_defaults: MeshRecipe
    arena_motif: str
    base_hp: int = 100
