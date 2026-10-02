from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from backend.app.database.crud import jobs_db
from backend.app.database.crud import candidates_db
from backend.app.database.crud.errors import AmbiguousCandidateMatchError
from backend.app.prompts.jd_prompts import (
    JOB_DESCRIPTION_SYSTEM_PROMPT,
    LINKEDIN_BLURB_SYSTEM_PROMPT,
    build_job_description_user_prompt,
    build_linkedin_blurb_user_prompt,
)
from backend.app.schemas.jobs_schema import JobCreate, JobPatch, JobRead, JobStatus
from backend.app.schemas.google_forms_schema import (
    GoogleFormCloneRequest,
    GoogleFormCloneResult,
    GoogleFormQuestionSet,
)
from backend.app.prompts.form_prompts import FORM_QUESTION_SYSTEM_PROMPT, build_form_questions_user_prompt
from backend.app.schemas.candidates_schema import (
    ApplicationApplicantPage,
    ApplicationApplicantRead,
    ExecutiveWorkspace,
    FormSyncResult,
    PipelineStatus,
    ScreeningDecision,
)
from backend.app.services.ai.gemini_flash import GeminiFlashProvider
from backend.app.services.google_forms import (
    GoogleFormsConfigurationError,
    GoogleFormsIntegrationError,
    GoogleFormsService,
)
from backend.app.services.form_sync_service import sync_form_responses

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_prompt_payload(row: JobRead) -> JobCreate:
    fields = {
        "title",
        "tech_stack",
        "seniority",
        "required_experience",
        "salary",
        "location",
        "work_type",
        "university",
    }
    return JobCreate.model_validate(row.model_dump(include=fields))


class JobsStore:
    def create_job(self, job: JobCreate) -> JobRead:
        return jobs_db.create_job(job)

    def list_jobs(self, *, status: JobStatus | None = None) -> list[JobRead]:
        return jobs_db.list_jobs(status=status)

    def get_job(self, job_id: UUID) -> JobRead | None:
        return jobs_db.get_job(job_id)

    def update_job(self, job_id: UUID, patch: JobPatch) -> JobRead | None:
        return jobs_db.update_job(job_id, patch)


_jobs_store = JobsStore()


def get_jobs_store() -> JobsStore:
    return _jobs_store


def get_ai_provider() -> GeminiFlashProvider:
    return GeminiFlashProvider()


@router.get("", response_model=list[JobRead])
def list_jobs_route(*, status: JobStatus | None = None) -> list[JobRead]:
    return get_jobs_store().list_jobs(status=status)


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job_route(job: JobCreate) -> JobRead:
    return get_jobs_store().create_job(job)


@router.get("/{job_id}", response_model=JobRead)
def get_job_route(job_id: UUID) -> JobRead:
    row = get_jobs_store().get_job(job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return row


@router.patch("/{job_id}", response_model=JobRead)
def patch_job_route(job_id: UUID, patch: JobPatch) -> JobRead:
    row = get_jobs_store().update_job(job_id, patch)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return row


@router.post("/{job_id}/generate-jd", response_model=JobRead)
def generate_jd_route(job_id: UUID) -> JobRead:
    row = get_jobs_store().get_job(job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    payload = _job_prompt_payload(row)
    provider = get_ai_provider()
    markdown = provider.generate_text(
        system_instruction=JOB_DESCRIPTION_SYSTEM_PROMPT,
        user_content=build_job_description_user_prompt(payload),
    )

    updated = get_jobs_store().update_job(job_id, JobPatch(jd_markdown=markdown))
    if updated is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="job update failed")
    return updated


@router.post("/{job_id}/generate-form-questions", response_model=GoogleFormQuestionSet)
def generate_form_questions_route(job_id: UUID) -> GoogleFormQuestionSet:
    row = get_jobs_store().get_job(job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    payload = _job_prompt_payload(row)
    result = get_ai_provider().generate_structured(
        system_instruction=FORM_QUESTION_SYSTEM_PROMPT,
        user_content=build_form_questions_user_prompt(payload),
        response_model=GoogleFormQuestionSet,
    )
    return GoogleFormQuestionSet.model_validate(result)


@router.post("/{job_id}/clone-form", response_model=GoogleFormCloneResult)
def clone_form_route(job_id: UUID, question_set: GoogleFormQuestionSet) -> GoogleFormCloneResult:
    row = get_jobs_store().get_job(job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    payload = _job_prompt_payload(row)
    service = GoogleFormsService()
    try:
        result = service.clone_application_form(
            GoogleFormCloneRequest(
                title=f"{payload.title} Application",
                questions=question_set.questions,
            )
        )
    except GoogleFormsIntegrationError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    except GoogleFormsConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    updated = get_jobs_store().update_job(
        job_id,
        JobPatch(google_form_id=result.form_id, google_form_url=str(result.responder_url)),
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="job update failed")
    return result


@router.post("/{job_id}/linkedin-blurb", response_model=JobRead)
def linkedin_blurb_route(job_id: UUID) -> JobRead:
    row = get_jobs_store().get_job(job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    if not row.jd_markdown:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="job description must be generated or saved before creating a post",
        )
    if not row.google_form_url:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="application form must be cloned before creating a post",
        )

    payload = _job_prompt_payload(row)
    blurb = get_ai_provider().generate_text(
        system_instruction=LINKEDIN_BLURB_SYSTEM_PROMPT,
        user_content=build_linkedin_blurb_user_prompt(
            payload,
            jd_markdown=row.jd_markdown,
            form_url=row.google_form_url,
        ),
    )
    updated = get_jobs_store().update_job(job_id, JobPatch(linkedin_blurb=blurb))
    if updated is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="job update failed")
    return updated


@router.get("/{job_id}/applications", response_model=list[ApplicationApplicantRead])
def list_job_applications_route(
    job_id: UUID,
    *,
    pipeline_status: PipelineStatus | None = None,
) -> list[ApplicationApplicantRead]:
    if get_jobs_store().get_job(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return candidates_db.list_job_applications(job_id, pipeline_status=pipeline_status)


@router.get("/{job_id}/applicants", response_model=ApplicationApplicantPage)
def list_job_applicants_page_route(
    job_id: UUID,
    *,
    agent_decision: ScreeningDecision | None = None,
    has_other_applications: bool | None = None,
    search: str | None = Query(default=None, max_length=200),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> ApplicationApplicantPage:
    page = candidates_db.list_job_applicants_page(
        job_id,
        agent_decision=agent_decision,
        has_other_applications=has_other_applications,
        search=search,
        offset=offset,
        limit=limit,
    )
    if not page.job_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return page


@router.get("/{job_id}/executive-workspace", response_model=ExecutiveWorkspace)
def executive_workspace_route(
    job_id: UUID,
    *,
    application_id: UUID | None = None,
) -> ExecutiveWorkspace:
    workspace = candidates_db.get_executive_workspace(
        job_id,
        application_id=application_id,
    )
    if not workspace.job_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return workspace


@router.post("/{job_id}/sync", response_model=FormSyncResult)
def sync_applicants_route(job_id: UUID) -> FormSyncResult:
    row = get_jobs_store().get_job(job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    if not row.jd_markdown:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="job description is required before sync")
    if not row.google_form_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="application form is required before sync")
    try:
        return sync_form_responses(
            row,
            forms_service=GoogleFormsService(),
            ai_provider=get_ai_provider(),
        )
    except GoogleFormsConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except GoogleFormsIntegrationError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
