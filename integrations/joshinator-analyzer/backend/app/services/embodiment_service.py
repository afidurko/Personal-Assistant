"""Resolve detected card identity → original procedural 3D embodiment.

Strong path:
  detect/OCR card → classify sport bucket → original archetype
  → tint mesh from stable hash → emit spawn payload for the frontend.

Never loads or references licensed character meshes, logos, or franchise IP.
"""

from __future__ import annotations

import hashlib
import logging
import re
from copy import deepcopy
from typing import Any, Dict, Optional

from app.models.embodiment import Embodiment, MeshRecipe
from app.services.embodiment_catalog import ARCHETYPES, SPORT_KEYWORDS

logger = logging.getLogger(__name__)


def _stable_hex_colors(seed: str) -> tuple[str, str, str]:
    """Derive original palette from identity seed (not team brand books)."""
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    # Prefer mid-saturation hues so procedural meshes stay readable.
    h = int(digest[0:2], 16) / 255.0
    s = 0.45 + (int(digest[2:4], 16) / 255.0) * 0.35
    v = 0.55 + (int(digest[4:6], 16) / 255.0) * 0.35

    def hsv_to_hex(hh: float, ss: float, vv: float) -> str:
        i = int(hh * 6) % 6
        f = hh * 6 - int(hh * 6)
        p = vv * (1 - ss)
        q = vv * (1 - f * ss)
        t = vv * (1 - (1 - f) * ss)
        if i == 0:
            r, g, b = vv, t, p
        elif i == 1:
            r, g, b = q, vv, p
        elif i == 2:
            r, g, b = p, vv, t
        elif i == 3:
            r, g, b = p, q, vv
        elif i == 4:
            r, g, b = t, p, vv
        else:
            r, g, b = vv, p, q
        return "#{:02X}{:02X}{:02X}".format(
            int(r * 255), int(g * 255), int(b * 255)
        )

    primary = hsv_to_hex(h, s, v)
    secondary = hsv_to_hex((h + 0.42) % 1.0, max(0.15, s - 0.25), min(1.0, v + 0.25))
    emissive = hsv_to_hex(h, min(1.0, s + 0.1), min(1.0, v + 0.15))
    return primary, secondary, emissive


def _blob(card_info: Dict[str, Any]) -> str:
    parts = [
        str(card_info.get("sport") or ""),
        str(card_info.get("set_name") or ""),
        str(card_info.get("manufacturer") or ""),
        str(card_info.get("position") or ""),
        str(card_info.get("player_name") or ""),
        str(card_info.get("year") or ""),
    ]
    return " ".join(parts).lower()


def classify_sport(card_info: Dict[str, Any]) -> str:
    """Map card text cues → generic sport_class archetype id."""
    explicit = (card_info.get("sport") or "").strip().lower()
    explicit_map = {
        "baseball": "diamond_arc",
        "basketball": "court_pulse",
        "football": "grid_surge",
        "hockey": "ice_vector",
        "soccer": "pitch_orbit",
    }
    if explicit in explicit_map:
        return explicit_map[explicit]

    text = _blob(card_info)
    best_id = "neutral_echo"
    best_hits = 0
    for archetype_id, keywords in SPORT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits > best_hits:
            best_hits = hits
            best_id = archetype_id
    return best_id


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return cleaned or "unknown"


def _hp_for_card(card_info: Dict[str, Any], base_hp: int) -> Dict[str, int]:
    """Map grade cues to HP without referencing third-party grade logos as assets."""
    grade = str(card_info.get("grade") or "").upper()
    mult = 1.0
    if "10" in grade:
        mult = 1.25
    elif "9" in grade:
        mult = 1.1
    elif "8" in grade:
        mult = 1.0
    elif grade:
        mult = 0.9
    if card_info.get("rookie"):
        mult += 0.05
    max_hp = max(60, min(150, int(round(base_hp * mult))))
    return {"current": max_hp, "max": max_hp}


class EmbodimentService:
    """Catalog-backed resolver used by the analyze pipeline."""

    def list_archetypes(self) -> list[dict]:
        return [a.model_dump() for a in ARCHETYPES.values()]

    def resolve(
        self,
        card_info: Optional[Dict[str, Any]],
        *,
        confidence: float = 0.0,
    ) -> Optional[Embodiment]:
        if not card_info:
            return None
        player = (card_info.get("player_name") or "").strip()
        if not player:
            return None

        archetype_id = classify_sport(card_info)
        archetype = ARCHETYPES.get(archetype_id) or ARCHETYPES["neutral_echo"]

        seed = "|".join(
            [
                player,
                str(card_info.get("year") or ""),
                str(card_info.get("set_name") or ""),
                str(card_info.get("card_number") or ""),
                archetype.id,
            ]
        )
        primary, secondary, emissive = _stable_hex_colors(seed)
        mesh = MeshRecipe(**deepcopy(archetype.mesh_defaults.model_dump()))
        mesh.primary_hex = primary
        mesh.secondary_hex = secondary
        mesh.emissive_hex = emissive

        # Slight per-card silhouette variance (still original primitives).
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        mesh.height = round(0.95 + (int(digest[6:8], 16) / 255.0) * 0.7, 3)
        mesh.bulk = round(0.75 + (int(digest[8:10], 16) / 255.0) * 0.7, 3)

        year = card_info.get("year") or ""
        set_name = card_info.get("set_name") or "Unknown set"
        subtitle = f"{year} · {set_name}".strip(" ·")

        entity_id = f"embody.{archetype.id}.{_slug(player)}"
        embodiment = Embodiment(
            entity_id=entity_id,
            archetype_id=archetype.id,
            display_name=player,
            subtitle=subtitle,
            sport_class=archetype.sport_class,
            actions=list(archetype.actions),
            anim_map=dict(archetype.anim_map),
            mesh=mesh,
            arena_motif=archetype.arena_motif,
            hp=_hp_for_card(card_info, archetype.base_hp),
            confidence=float(confidence or 0.0),
            card_ref={
                "player_name": player,
                "year": card_info.get("year"),
                "set_name": card_info.get("set_name"),
                "card_number": card_info.get("card_number"),
                "grade": card_info.get("grade"),
            },
        )
        logger.debug("Embodiment resolved: %s → %s", player, entity_id)
        return embodiment

    def resolve_dict(
        self,
        card_info: Optional[Dict[str, Any]],
        *,
        confidence: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        emb = self.resolve(card_info, confidence=confidence)
        return emb.model_dump() if emb else None


embodiment_service = EmbodimentService()
