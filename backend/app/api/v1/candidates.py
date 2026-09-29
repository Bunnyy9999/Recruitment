from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from backend.app.database.crud import candidates_db
from backend.app.database.crud.errors import AmbiguousCandidateMatchError
from backend.app.schemas.candidates_schema import CandidateHistoryRecord

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("/{candidate_id}/history", response_model=list[CandidateHistoryRecord])
def candidate_history_route(candidate_id: UUID) -> list[CandidateHistoryRecord]:
    return candidates_db.get_candidate_history(candidate_id)


