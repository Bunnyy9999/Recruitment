from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.api.router import app
from backend.app.api.v1 import jobs as jobs_router
from backend.app.schemas.jobs_schema import JobCreate, JobPatch, JobRead, JobStatus
from backend.app.schemas.candidates_schema import (
    ApplicationApplicantPage,
    ExecutiveWorkspace,
    FormSyncResult,
)
from backend.app.services.google_forms import GoogleFormsConfigurationError


class FakeJobsDb:
    def __init__(self):
        self.jobs: dict[str, JobRead] = {}

    def create_job(self, job: JobCreate) -> JobRead:
        row = JobRead(
            id=uuid4(),
            title=job.title,
            tech_stack=job.tech_stack,
            seniority=job.seniority,
            required_experience=job.required_experience,
            salary=job.salary,
            location=job.location,
            work_type=job.work_type,
            university=job.university,
            jd_markdown=None,
            google_form_id=None,
            google_form_url=None,
            linkedin_blurb=None,
            status=JobStatus.draft,
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        self.jobs[str(row.id)] = row
        return row

    def list_jobs(self, *, status: JobStatus | None = None) -> list[JobRead]:
        rows = list(self.jobs.values())
        if status is not None:
            rows = [row for row in rows if row.status == status]
        return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def get_job(self, job_id):
        return self.jobs.get(str(job_id))

    def update_job(self, job_id, patch: JobPatch):
        row = self.jobs[str(job_id)]
        values = patch.model_dump(exclude_unset=True)
        for key, value in values.items():
            setattr(row, key, value)
        return row


class JobsApiTests(TestCase):
    def setUp(self) -> None:
        self.store = FakeJobsDb()
        jobs_router.get_jobs_store = lambda: self.store
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    def test_create_job_returns_201_and_job_payload(self) -> None:
        response = self.client.post(
            "/api/v1/jobs",
            json={
                "title": "Data Engineer",
                "tech_stack": "Python, Postgres",
                "seniority": "Senior",
                "required_experience": "5 years",
                "salary": "$110,000-$150,000",
                "location": "Remote",
                "work_type": "Remote",
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["title"], "Data Engineer")
        self.assertEqual(payload["status"], "draft")

    def test_patch_job_updates_fields(self) -> None:
        created = self.store.create_job(
            JobCreate(
                title="Data Scientist",
                tech_stack="Python, SQL",
                seniority="Mid",
                required_experience="3 years",
            )
        )

        response = self.client.patch(
            f"/api/v1/jobs/{created.id}",
            json={"status": "posted", "jd_markdown": "# JD"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "posted")
        self.assertEqual(payload["jd_markdown"], "# JD")

    def test_paginated_applicant_route_forwards_filters(self) -> None:
        created = self.store.create_job(
            JobCreate(
                title="Data Scientist",
                tech_stack="Python, SQL",
                seniority="Mid",
                required_experience="3 years",
            )
        )
        page = ApplicationApplicantPage(items=[], total_count=0, job_exists=True)

        with patch.object(
            jobs_router.candidates_db,
            "list_job_applicants_page",
            return_value=page,
        ) as list_page:
            response = self.client.get(
                f"/api/v1/jobs/{created.id}/applicants",
                params={
                    "agent_decision": "pass",
                    "has_other_applications": "true",
                    "search": "Alex",
                    "offset": 20,
                    "limit": 20,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])
        list_page.assert_called_once()
        self.assertEqual(list_page.call_args.kwargs["search"], "Alex")
        self.assertEqual(list_page.call_args.kwargs["offset"], 20)
        self.assertEqual(list_page.call_args.kwargs["limit"], 20)

    def test_executive_workspace_route_returns_combined_payload(self) -> None:
        created = self.store.create_job(
            JobCreate(
                title="Data Scientist",
                tech_stack="Python, SQL",
                seniority="Mid",
                required_experience="3 years",
            )
        )
        application_id = uuid4()
        workspace = ExecutiveWorkspace(
            job_exists=True,
            selected_application_exists=True,
            eligible_applicants=[],
            dossier=None,
        )

        with patch.object(
            jobs_router.candidates_db,
            "get_executive_workspace",
            return_value=workspace,
        ) as get_workspace:
            response = self.client.get(
                f"/api/v1/jobs/{created.id}/executive-workspace",
                params={"application_id": str(application_id)},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["eligible_applicants"], [])
        get_workspace.assert_called_once_with(created.id, application_id=application_id)

    def test_linkedin_blurb_requires_form_and_jd(self) -> None:
        created = self.store.create_job(
            JobCreate(title="Data Scientist", tech_stack="Python", seniority="Mid", required_experience="3 years")
        )

        response = self.client.post(f"/api/v1/jobs/{created.id}/linkedin-blurb")

        self.assertEqual(response.status_code, 409)

    def test_linkedin_blurb_persists_provider_output_and_form_url(self) -> None:
        created = self.store.create_job(
            JobCreate(title="Data Scientist", tech_stack="Python", seniority="Mid", required_experience="3 years")
        )
        self.store.update_job(
            created.id,
            JobPatch(jd_markdown="# Data Scientist", google_form_url="https://forms.example/apply"),
        )

        provider = Mock()
        provider.generate_text.return_value = "Apply here: https://forms.example/apply"
        with patch.object(jobs_router, "get_ai_provider", return_value=provider):
            response = self.client.post(f"/api/v1/jobs/{created.id}/linkedin-blurb")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["linkedin_blurb"], "Apply here: https://forms.example/apply")
        provider.generate_text.assert_called_once()

    def test_sync_runs_form_batch_without_manual_applicant_payload(self) -> None:
        created = self.store.create_job(
            JobCreate(title="Data Scientist", tech_stack="Python", seniority="Mid", required_experience="3 years")
        )
        self.store.update_job(
            created.id,
            JobPatch(
                jd_markdown="# Data Scientist",
                google_form_id="form-id",
                google_form_url="https://forms.example/apply",
            ),
        )
        result = FormSyncResult(
            total_responses=2,
            synced=1,
            skipped_duplicates=1,
            errors=0,
            items=[],
        )

        with patch.object(jobs_router, "GoogleFormsService") as forms_service:
            with patch.object(jobs_router, "get_ai_provider", return_value=Mock()):
                with patch.object(jobs_router, "sync_form_responses", return_value=result) as sync:
                    response = self.client.post(f"/api/v1/jobs/{created.id}/sync")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_responses"], 2)
        forms_service.assert_called_once()
        sync.assert_called_once()

    def test_clone_form_configuration_error_returns_service_unavailable(self) -> None:
        created = self.store.create_job(
            JobCreate(title="Data Scientist", tech_stack="Python", seniority="Mid", required_experience="3 years")
        )
        with patch.object(jobs_router, "GoogleFormsService") as forms_service:
            forms_service.return_value.clone_application_form.side_effect = (
                GoogleFormsConfigurationError("Google client initialization failed")
            )
            response = self.client.post(
                f"/api/v1/jobs/{created.id}/clone-form",
                json={
                    "questions": [
                        {"title": "Describe your experience", "question_type": "paragraph"},
                        {"title": "Which tools have you used?", "question_type": "short_text"},
                    ]
                },
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Google client initialization failed")
