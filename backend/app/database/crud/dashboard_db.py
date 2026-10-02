from backend.app.database.crud.errors import DatabaseOperationError, execute_query
from backend.app.schemas.jobs_schema import CommandCenterSummary
from backend.app.services.supabase_service import supabase_client


def get_command_center_summary() -> CommandCenterSummary:
    rows = execute_query(
        supabase_client.rpc("get_command_center_summary", {}),
        operation="get command center summary",
    )
    if len(rows) != 1:
        raise DatabaseOperationError("get command center summary returned an invalid row count")
    return CommandCenterSummary.model_validate(rows[0])