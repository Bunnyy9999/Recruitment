from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.api.router import api_router, api_v1_router
from backend.app.main import app
from backend.app.api.v1 import dashboard as dashboard_router
from backend.app.api.v1 import interviews as interviews_router
from backend.app.schemas.jobs_schema import CommandCenterSummary
from backend.app.schemas.interviews_schema import InterviewWorkspace


class FastAPIAssemblyTests(TestCase):
    def test_health_is_available_without_external_services(self) -> None:
        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_api_router_reserves_versioned_prefix(self) -> None:
        self.assertEqual(api_v1_router.prefix, "/api/v1")
        self.assertTrue(any(route.path == "/health" for route in api_router.routes))

    def test_feature_paths_are_versioned(self) -> None:
        paths = app.openapi()["paths"]
        self.assertIn("/health", paths)
        self.assertTrue(all(path.startswith(("/health", "/api/v1/")) for path in paths))
        self.assertIn("/api/v1/jobs/{job_id}/sync", paths)
        self.assertIn("/api/v1/jobs/{job_id}/interview-workspace", paths)
        self.assertIn("/api/v1/applications/{application_id}/hr-override", paths)
        self.assertIn("/api/v1/dashboard/summary", paths)

    def test_command_center_summary_returns_aggregated_payload(self) -> None:
        summary = CommandCenterSummary(
            jobs=[],
            draft_job_count=1,
            posted_job_count=3,
            total_job_count=6,
            open_job_count=3,
            closed_job_count=2,
            application_count=12,
            active_pipeline_count=5,
            ceo_decision_count=2,
            stage1_pass_count=8,
            first_interview_scheduled_count=3,
            second_interview_count=1,
            successful_applicant_count=2,
            ceo_failed_applicant_count=1,
        )
        original = dashboard_router.dashboard_db.get_command_center_summary
        dashboard_router.dashboard_db.get_command_center_summary = lambda: summary
        try:
            with TestClient(app) as client:
                response = client.get("/api/v1/dashboard/summary")
        finally:
            dashboard_router.dashboard_db.get_command_center_summary = original

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "jobs": [],
                "draft_job_count": 1,
                "posted_job_count": 3,
                "total_job_count": 6,
                "open_job_count": 3,
                "closed_job_count": 2,
                "application_count": 12,
                "active_pipeline_count": 5,
                "ceo_decision_count": 2,
                "stage1_pass_count": 8,
                "first_interview_scheduled_count": 3,
                "second_interview_count": 1,
                "successful_applicant_count": 2,
                "ceo_failed_applicant_count": 1,
            },
        )

    def test_interview_workspace_route_returns_combined_read(self) -> None:
        job_id = uuid4()
        application_id = uuid4()
        workspace = InterviewWorkspace(
            job_exists=True,
            selected_application_exists=True,
            applicants=[],
            rounds=[],
        )

        with patch.object(
            interviews_router.interviews_db,
            "get_interview_workspace",
            return_value=workspace,
        ) as get_workspace:
            with TestClient(app) as client:
                response = client.get(
                    f"/api/v1/jobs/{job_id}/interview-workspace",
                    params={"application_id": str(application_id)},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["applicants"], [])
        self.assertEqual(response.json()["rounds"], [])
        get_workspace.assert_called_once_with(job_id, application_id=application_id)
