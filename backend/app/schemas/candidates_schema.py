from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    model_validator,
)


class ApplicationStage(str, Enum):
    sync_evaluation = "sync_evaluation"
    technical_interview = "technical_interview"
    ceo_review = "ceo_review"
    closed = "closed"


class ScreeningDecision(str, Enum):
    passed = "pass"
    failed = "fail"


class PipelineStatus(str, Enum):
    failed_at_sync = "failed_at_sync"
    active_pipeline = "active_pipeline"
    pending_ceo_decision = "pending_ceo_decision"
    closed_complete = "closed_complete"


class FinalDecision(str, Enum):
    pending = "pending"
    passed = "pass"
    failed = "fail"


class CandidateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    linkedin_url: HttpUrl | None = None


class CandidateIdentityLookup(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    linkedin_url: HttpUrl | None = None

    @model_validator(mode="after")
    def require_identity_key(self) -> "CandidateIdentityLookup":
        if not any((self.email, self.phone, self.linkedin_url)):
            raise ValueError("at least one candidate identity key is required")
        return self


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    full_name: str
    email: EmailStr
    phone: str | None
    linkedin_url: HttpUrl | None
    created_at: AwareDatetime


class ApplicationScreeningResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    agent_decision: ScreeningDecision
    screening_summary: str = Field(min_length=1, max_length=2000)


class HROverrideRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    hr_username: str = Field(min_length=1, max_length=150)


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    candidate_id: UUID
    job_id: UUID
    current_stage: ApplicationStage
    agent_decision: ScreeningDecision | None
    screening_summary: str | None
    hr_override_status: ScreeningDecision | None
    examiner: str
    pipeline_status: PipelineStatus
    final_decision: FinalDecision
    remarks: str | None
    created_at: AwareDatetime


class CandidateHistoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: UUID
    job_id: UUID
    job_title: str
    current_stage: ApplicationStage
    pipeline_status: PipelineStatus
    final_decision: FinalDecision
    remarks: str | None
    created_at: AwareDatetime


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    job_id: UUID


class ApplicationDashboardRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    application_id: UUID
    candidate_id: UUID
    job_id: UUID
    full_name: str
    email: EmailStr
    phone: str | None
    linkedin_url: HttpUrl | None
    job_title: str
    current_stage: ApplicationStage
    agent_decision: ScreeningDecision | None
    screening_summary: str | None
    hr_override_status: ScreeningDecision | None
    examiner: str
    pipeline_status: PipelineStatus
    final_decision: FinalDecision
    remarks: str | None
    application_created_at: AwareDatetime