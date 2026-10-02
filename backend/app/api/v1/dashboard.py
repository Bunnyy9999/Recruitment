from fastapi import APIRouter

from backend.app.database.crud import dashboard_db
from backend.app.schemas.jobs_schema import CommandCenterSummary


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=CommandCenterSummary)
def command_center_summary_route() -> CommandCenterSummary:
    return dashboard_db.get_command_center_summary()