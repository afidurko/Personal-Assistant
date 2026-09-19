from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.embodiment_service import embodiment_service
from app.services.session_log_service import session_log

router = APIRouter()


class EmbodimentResolveRequest(BaseModel):
    card_info: Dict[str, Any]
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


@router.get("/health")
async def health_check():
    return {"status": "healthy"}


@router.get("/session/{session_id}/history")
async def get_session_history(session_id: str):
    """Return the stored analysis results for a session (newest first, max 50)."""
    results = session_log.get_session(session_id)
    if results is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "count": len(results), "results": results}


@router.get("/embodiment/catalog")
async def embodiment_catalog():
    """List original procedural archetypes (no third-party character IP)."""
    return {
        "source": "joshinator-original-catalog",
        "license_note": (
            "Original procedural embodiments only. No licensed character meshes, "
            "logos, or franchise assets."
        ),
        "archetypes": embodiment_service.list_archetypes(),
    }


@router.post("/embodiment/resolve")
async def embodiment_resolve(body: EmbodimentResolveRequest):
    """Resolve card_info → original 3D embodiment spawn payload."""
    result = embodiment_service.resolve_dict(
        body.card_info, confidence=body.confidence
    )
    if result is None:
        raise HTTPException(
            status_code=422,
            detail="player_name is required to resolve an embodiment",
        )
    return result