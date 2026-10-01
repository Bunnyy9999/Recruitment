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