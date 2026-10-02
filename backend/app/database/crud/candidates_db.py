from uuid import UUID

from backend.app.database.crud.errors import (
    AmbiguousCandidateMatchError,
    DatabaseOperationError,
    execute_query,
)
from backend.app.schemas.candidates_schema import (
    ApplicationCreate,
    ApplicationDashboardRecord,
    ApplicationApplicantPage,
    ApplicationApplicantRead,
    ApplicationRead,
    CandidateCreate,
    CandidateHistoryRecord,
    CandidateIdentityLookup,
    CandidateRead,
    ExecutiveWorkspace,
    JobDashboardFilter,
    JobDashboardPage,
    ApplicationScreeningResult,
    ScreeningDecision,
    ApplicationScreeningResult,
    ScreeningDecision,
    PipelineStatus,
)
from backend.app.services.supabase_service import supabase_client


def create_candidate(candidate: CandidateCreate) -> CandidateRead:
    rows = execute_query(
        supabase_client.table("candidates")
        .insert(candidate.model_dump(mode="json"))
        .select("*"),
        operation="create candidate",
    )
    if not rows:
        raise DatabaseOperationError("create candidate returned no row")
    return CandidateRead.model_validate(rows[0])


def get_candidate(candidate_id: UUID) -> CandidateRead | None:
    rows = execute_query(
        supabase_client.table("candidates")
        .select("*")
        .eq("id", str(candidate_id))
        .limit(1),
        operation="get candidate",
    )
    return CandidateRead.model_validate(rows[0]) if rows else None


def find_candidate_by_identity(
    identity: CandidateIdentityLookup,
) -> CandidateRead | None:
    matches: dict[UUID, dict[str, object]] = {}
    keys: list[tuple[str, str, bool]] = []
    if identity.email is not None:
        keys.append(("email", str(identity.email).lower(), True))
    if identity.phone is not None:
        keys.append(("phone", identity.phone, False))
    if identity.linkedin_url is not None:
        keys.append(("linkedin_url", str(identity.linkedin_url).rstrip("/"), False))

    for column, value, case_insensitive in keys:
        query = supabase_client.table("candidates").select("*")
        if case_insensitive:
            query = query.ilike(column, value)
        else:
            query = query.eq(column, value)
        rows = execute_query(
            query.limit(2),
            operation="match candidate identity",
        )
        if len(rows) > 1:
            raise AmbiguousCandidateMatchError(
                f"Multiple candidate profiles matched {column}"
            )
        if rows:
            candidate = CandidateRead.model_validate(rows[0])
            matches[candidate.id] = rows[0]

    if len(matches) > 1:
        raise AmbiguousCandidateMatchError(
            "Supplied identity keys matched different candidate profiles"
        )
    if not matches:
        return None
    return CandidateRead.model_validate(next(iter(matches.values())))


def create_application(application: ApplicationCreate) -> ApplicationRead:
    rows = execute_query(
        supabase_client.table("applications")
        .insert(
            {
                "candidate_id": str(application.candidate_id),
                "job_id": str(application.job_id),
            }
        )
        .select("*"),
        operation="create application",
    )
    if not rows:
        raise DatabaseOperationError("create application returned no row")
    return ApplicationRead.model_validate(rows[0])


def get_application(application_id: UUID) -> ApplicationRead | None:
    rows = execute_query(
        supabase_client.table("applications")
        .select("*")
        .eq("id", str(application_id))
        .limit(1),
        operation="get application",
    )
    return ApplicationRead.model_validate(rows[0]) if rows else None


def get_application_for_candidate_job(
    candidate_id: UUID,
    job_id: UUID,
) -> ApplicationRead | None:
    rows = execute_query(
        supabase_client.table("applications")
        .select("*")
        .eq("candidate_id", str(candidate_id))
        .eq("job_id", str(job_id))
        .limit(1),
        operation="get candidate application for job",
    )
    return ApplicationRead.model_validate(rows[0]) if rows else None


def get_application_for_job_identity(
    job_id: UUID,
    identity: CandidateIdentityLookup,
) -> ApplicationRead | None:
    candidate_ids: set[str] = set()
    keys: list[tuple[str, str, bool]] = []
    if identity.email is not None:
        keys.append(("email", str(identity.email).lower(), True))
    if identity.phone is not None:
        keys.append(("phone", identity.phone, False))
    if identity.linkedin_url is not None:
        keys.append(("linkedin_url", str(identity.linkedin_url).rstrip("/"), False))

    for column, value, case_insensitive in keys:
        query = supabase_client.table("candidates").select("id")
        query = query.ilike(column, value) if case_insensitive else query.eq(column, value)
        rows = execute_query(query, operation="match duplicate applicant identity")
        candidate_ids.update(str(row["id"]) for row in rows)

    if not candidate_ids:
        return None

    rows = execute_query(
        supabase_client.table("applications")
        .select("*")
        .eq("job_id", str(job_id))
        .in_("candidate_id", sorted(candidate_ids))
        .limit(1),
        operation="find same-job application by identity",
    )
    return ApplicationRead.model_validate(rows[0]) if rows else None


def get_application_for_form_response(
    job_id: UUID,
    response_id: str,
) -> ApplicationRead | None:
    rows = execute_query(
        supabase_client.table("applications")
        .select("*")
        .eq("job_id", str(job_id))
        .eq("google_form_response_id", response_id)
        .limit(1),
        operation="get application for form response",
    )
    return ApplicationRead.model_validate(rows[0]) if rows else None


def list_job_applications(
    job_id: UUID,
    *,
    pipeline_status: PipelineStatus | None = None,
) -> list[ApplicationApplicantRead]:
    query = supabase_client.table("applications").select(
        "*, candidates(full_name,email,phone)"
    ).eq(
        "job_id", str(job_id)
    )
    if pipeline_status is not None:
        query = query.eq("pipeline_status", pipeline_status.value)
    rows = execute_query(
        query.order("created_at", desc=True),
        operation="list job applications",
    )
    applications: list[ApplicationApplicantRead] = []
    for row in rows:
        candidate = row.pop("candidates", None)
        if isinstance(candidate, list):
            candidate = candidate[0] if candidate else None
        if not isinstance(candidate, dict):
            raise DatabaseOperationError("job application row is missing candidate data")
        applications.append(
            ApplicationApplicantRead.model_validate(
                {
                    **row,
                    "candidate_name": candidate.get("full_name"),
                    "email": candidate.get("email"),
                    "phone": candidate.get("phone"),
                }
            )
        )

    candidate_ids = sorted({str(application.candidate_id) for application in applications})
    candidates_with_other_applications: set[str] = set()
    if candidate_ids:
        other_job_rows = execute_query(
            supabase_client.table("applications")
            .select("candidate_id")
            .in_("candidate_id", candidate_ids)
            .neq("job_id", str(job_id)),
            operation="list candidate applications for other jobs",
        )
        candidates_with_other_applications = {
            str(row["candidate_id"]) for row in other_job_rows
        }

    for application in applications:
        application.has_other_applications = (
            str(application.candidate_id) in candidates_with_other_applications
        )
    return applications


def list_job_applicants_page(
    job_id: UUID,
    *,
    agent_decision: ScreeningDecision | None = None,
    has_other_applications: bool | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> ApplicationApplicantPage:
    rows = execute_query(
        supabase_client.rpc(
            "list_job_applicants_page",
            {
                "p_job_id": str(job_id),
                "p_agent_decision": agent_decision.value if agent_decision else None,
                "p_has_other_applications": has_other_applications,
                "p_search": search,
                "p_offset": offset,
                "p_limit": limit,
            },
        ),
        operation="list paginated job applicants",
    )
    if len(rows) != 1:
        raise DatabaseOperationError("list paginated job applicants returned an invalid row count")
    return ApplicationApplicantPage.model_validate(
        {
            "items": rows[0].get("applicants") or [],
            "total_count": rows[0].get("total_count", 0),
            "job_exists": rows[0].get("job_exists", False),
        }
    )


def get_candidate_history(candidate_id: UUID) -> list[CandidateHistoryRecord]:
    rows = execute_query(
        supabase_client.table("applications")
        .select(
            "id,job_id,current_stage,pipeline_status,final_decision,remarks,screening_summary,created_at,jobs(title)"
        )
        .eq("candidate_id", str(candidate_id))
        .order("created_at", desc=True),
        operation="get candidate application history",
    )
    history: list[CandidateHistoryRecord] = []
    for row in rows:
        job_data = row.get("jobs")
        if isinstance(job_data, list):
            job_data = job_data[0] if job_data else None
        if not isinstance(job_data, dict) or not isinstance(job_data.get("title"), str):
            raise DatabaseOperationError("history row is missing related job data")
        history.append(
            CandidateHistoryRecord.model_validate(
                {
                    "application_id": row["id"],
                    "job_id": row["job_id"],
                    "job_title": job_data["title"],
                    "current_stage": row["current_stage"],
                    "pipeline_status": row["pipeline_status"],
                    "final_decision": row["final_decision"],
                    "remarks": row.get("remarks"),
                    "screening_summary": row.get("screening_summary"),
                    "created_at": row["created_at"],
                }
            )
        )
    return history


def list_passed_dashboard(
    *,
    job_id: UUID | None = None,
) -> list[ApplicationDashboardRecord]:
    return _list_dashboard(
        "hr_passed_candidates_dashboard",
        job_id=job_id,
        operation="list passed dashboard",
    )


def list_failed_dashboard(
    *,
    job_id: UUID | None = None,
) -> list[ApplicationDashboardRecord]:
    return _list_dashboard(
        "hr_failed_candidates_dashboard",
        job_id=job_id,
        operation="list failed dashboard",
    )


def _list_dashboard(
    view_name: str,
    *,
    job_id: UUID | None,
    operation: str,
) -> list[ApplicationDashboardRecord]:
    query = supabase_client.table(view_name).select("*")
    if job_id is not None:
        query = query.eq("job_id", str(job_id))
    rows = execute_query(
        query.order("application_created_at", desc=True),
        operation=operation,
    )
    return [ApplicationDashboardRecord.model_validate(row) for row in rows]


def apply_hr_pass_override(
    application_id: UUID,
    *,
    hr_username: str,
) -> ApplicationRead | None:
    username = hr_username.strip()
    if not username:
        raise ValueError("hr_username must not be empty")
    rows = execute_query(
        supabase_client.table("applications")
        .update(
            {
                "hr_override_status": "pass",
                "pipeline_status": "active_pipeline",
                "final_decision": "pending",
                "examiner": username,
            }
        )
        .eq("id", str(application_id))
        .eq("pipeline_status", "failed_at_sync")
        .select("*"),
        operation="apply HR pass override",
    )
    return ApplicationRead.model_validate(rows[0]) if rows else None


def save_application_screening(
    application_id: UUID,
    result: ApplicationScreeningResult,
) -> ApplicationRead | None:
    passed = result.agent_decision is ScreeningDecision.passed
    values = {
        "agent_decision": result.agent_decision.value,
        "screening_summary": result.screening_summary,
        "pipeline_status": "active_pipeline" if passed else "failed_at_sync",
        "final_decision": "pending" if passed else "fail",
    }
    rows = execute_query(
        supabase_client.table("applications")
        .update(values)
        .eq("id", str(application_id))
        .select("*"),
        operation="save application screening",
    )
    return ApplicationRead.model_validate(rows[0]) if rows else None

def create_screened_application(
    application: ApplicationCreate,
    *,
    response_id: str,
    form_responses: dict[str, str],
    screening: ApplicationScreeningResult,
) -> ApplicationRead:
    passed = screening.agent_decision is ScreeningDecision.passed
    rows = execute_query(
        supabase_client.table("applications")
        .insert(
            {
                "candidate_id": str(application.candidate_id),
                "job_id": str(application.job_id),
                "google_form_response_id": response_id,
                "form_responses": form_responses,
                "agent_decision": screening.agent_decision.value,
                "screening_summary": screening.screening_summary,
                "pipeline_status": "active_pipeline" if passed else "failed_at_sync",
                "final_decision": "pending" if passed else "fail",
            }
        )
        .select("*"),
        operation="create screened application",
    )
    if not rows:
        raise DatabaseOperationError("create screened application returned no row")
    return ApplicationRead.model_validate(rows[0])


def save_application_screening(
    application_id: UUID,
    result: ApplicationScreeningResult,
) -> ApplicationRead | None:
    passed = result.agent_decision is ScreeningDecision.passed
    rows = execute_query(
        supabase_client.table("applications")
        .update(
            {
                "agent_decision": result.agent_decision.value,
                "screening_summary": result.screening_summary,
                "pipeline_status": "active_pipeline" if passed else "failed_at_sync",
                "final_decision": "pending" if passed else "fail",
            }
        )
        .eq("id", str(application_id))
        .select("*"),
        operation="save application screening",
    )
    return ApplicationRead.model_validate(rows[0]) if rows else None


def move_application_to_ceo(application_id: UUID) -> ApplicationRead | None:
    rows = execute_query(
        supabase_client.table("applications")
        .update(
            {
                "current_stage": "ceo_review",
                "pipeline_status": "pending_ceo_decision",
            }
        )
        .eq("id", str(application_id))
        .eq("pipeline_status", "active_pipeline")
        .eq("final_decision", "pending")
        .select("*"),
        operation="move application to CEO review",
    )
    return ApplicationRead.model_validate(rows[0]) if rows else None


def save_final_decision(
    application_id: UUID,
    *,
    final_decision: str,
    remarks: str | None,
) -> ApplicationRead | None:
    if final_decision not in {"pass", "fail"}:
        raise ValueError("final_decision must be pass or fail")
    rows = execute_query(
        supabase_client.table("applications")
        .update(
            {
                "final_decision": final_decision,
                "pipeline_status": "closed_complete",
                "current_stage": "closed",
                "remarks": remarks,
            }
        )
        .eq("id", str(application_id))
        .eq("current_stage", "ceo_review")
        .eq("pipeline_status", "pending_ceo_decision")
        .eq("final_decision", "pending")
        .select("*"),
        operation="save final application decision",
    )
    return ApplicationRead.model_validate(rows[0]) if rows else None


def get_executive_workspace(
    job_id: UUID,
    *,
    application_id: UUID | None = None,
) -> ExecutiveWorkspace:
    rows = execute_query(
        supabase_client.rpc(
            "get_executive_workspace",
            {
                "p_job_id": str(job_id),
                "p_application_id": str(application_id) if application_id else None,
            },
        ),
        operation="get executive workspace",
    )
    if len(rows) != 1:
        raise DatabaseOperationError("get executive workspace returned an invalid row count")
    row = rows[0]
    return ExecutiveWorkspace.model_validate(
        {
            "job_exists": row.get("job_exists", False),
            "selected_application_exists": row.get("selected_application_exists", False),
            "eligible_applicants": row.get("eligible_applicants") or [],
            "dossier": row.get("dossier"),
        }
    )


def get_job_dashboard_page(
    job_id: UUID,
    *,
    decision_filter: JobDashboardFilter = JobDashboardFilter.all,
    search: str | None = None,
    offset: int = 0,
    limit: int = 20,
    selected_application_id: UUID | None = None,
) -> JobDashboardPage:
    rows = execute_query(
        supabase_client.rpc(
            "get_job_dashboard_page",
            {
                "p_job_id": str(job_id),
                "p_decision_filter": decision_filter.value,
                "p_search": search,
                "p_offset": offset,
                "p_limit": limit,
                "p_selected_application_id": (
                    str(selected_application_id) if selected_application_id else None
                ),
            },
        ),
        operation="get jobs dashboard page",
    )
    if len(rows) != 1:
        raise DatabaseOperationError("get jobs dashboard page returned an invalid row count")
    row = rows[0]
    return JobDashboardPage.model_validate(
        {
            "job_exists": row.get("job_exists", False),
            "total_count": row.get("total_count", 0),
            "applicants": row.get("applicants") or [],
            "selected_application": row.get("selected_application"),
        }
    )