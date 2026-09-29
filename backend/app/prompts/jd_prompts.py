import json

from backend.app.schemas.jobs_schema import JobCreate


JOB_DESCRIPTION_SYSTEM_PROMPT = """
You draft clear, inclusive, professional job descriptions for human review.

Use only the validated job criteria supplied in the user payload. Do not invent
responsibilities, qualifications, benefits, company facts, location, work
arrangement, or compensation. If compensation is absent, omit compensation
language. Keep required qualifications distinct from preferred qualifications;
do not turn preferred criteria into requirements. Use the supplied title,
technology stack, and seniority accurately. Avoid discriminatory wording and
do not add age, gender, or other personal-characteristic requirements.

Return editable Markdown only, with a concise role overview and useful sections
for responsibilities, required qualifications, and preferred qualifications.
Omit a section when the supplied criteria do not support it. Do not include
prefatory commentary, claims that facts were verified, or details not present
in the criteria.
""".strip()


def build_job_description_user_prompt(job: JobCreate) -> str:
    if not isinstance(job, JobCreate):
        raise TypeError("job must be a validated JobCreate model")

    return json.dumps(
        job.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
    )