from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class JobStatus(str, Enum):
    draft = "draft"
    posted = "posted"
    closed = "closed"


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    tech_stack: str = Field(min_length=1, max_length=2000)
    seniority: str = Field(min_length=1, max_length=100)
    required_experience: str = Field(min_length=1, max_length=1000)
    salary: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=200)
    work_type: str | None = Field(default=None, max_length=100)
    university: str | None = Field(default=None, max_length=500)


class JobPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    tech_stack: str | None = Field(default=None, min_length=1, max_length=2000)
    seniority: str | None = Field(default=None, min_length=1, max_length=100)
    required_experience: str | None = Field(default=None, min_length=1, max_length=1000)
    salary: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=200)
    work_type: str | None = Field(default=None, max_length=100)
    university: str | None = Field(default=None, max_length=500)
    jd_markdown: str | None = None
    google_form_id: str | None = Field(default=None, min_length=1, max_length=255)
    google_form_url: str | None = Field(default=None, min_length=1, max_length=2048)
    linkedin_blurb: str | None = None
    status: JobStatus | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> "JobPatch":
        if not self.model_fields_set:
            raise ValueError("at least one job field must be provided")
        return self


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    title: str
    posted_at: AwareDatetime | None = None
    closed_at: AwareDatetime | None = None
    application_count: int = Field(default=0, ge=0)
    stage1_pass_count: int = Field(default=0, ge=0)
    first_interview_scheduled_count: int = Field(default=0, ge=0)
    second_interview_count: int = Field(default=0, ge=0)
    ceo_decision_count: int = Field(default=0, ge=0)
    successful_applicant_count: int = Field(default=0, ge=0)
    ceo_failed_applicant_count: int = Field(default=0, ge=0)
    tech_stack: str
    seniority: str
    required_experience: str
    salary: str | None
    location: str | None
    work_type: str | None
    university: str | None
    jd_markdown: str | None
    google_form_id: str | None
    google_form_url: str | None
    linkedin_blurb: str | None
    status: JobStatus
    created_at: AwareDatetime


class CommandCenterSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jobs: list[JobRead]
    draft_job_count: int = Field(ge=0)
    posted_job_count: int = Field(ge=0)
    total_job_count: int = Field(ge=0)
    open_job_count: int = Field(ge=0)
    closed_job_count: int = Field(ge=0)
    application_count: int = Field(ge=0)
    active_pipeline_count: int = Field(ge=0)
    ceo_decision_count: int = Field(ge=0)
    stage1_pass_count: int = Field(ge=0)
    first_interview_scheduled_count: int = Field(ge=0)
    second_interview_count: int = Field(ge=0)
    successful_applicant_count: int = Field(ge=0)
    ceo_failed_applicant_count: int = Field(ge=0)

    @model_validator(mode="before")
    @classmethod
    def derive_missing_job_counts(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        statuses = [
            job.get("status") if isinstance(job, dict) else getattr(job, "status", None)
            for job in payload.get("jobs", [])
        ]
        if "draft_job_count" not in payload:
            payload["draft_job_count"] = sum(status == JobStatus.draft for status in statuses)
        if "posted_job_count" not in payload:
            payload["posted_job_count"] = sum(status == JobStatus.posted for status in statuses)
        if "total_job_count" not in payload:
            payload["total_job_count"] = (
                payload["draft_job_count"]
                + payload["posted_job_count"]
                + payload.get("closed_job_count", 0)
            )
        return payload