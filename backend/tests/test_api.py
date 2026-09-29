from unittest import TestCase

from fastapi.testclient import TestClient

from backend.app.api.router import api_router, api_v1_router
from backend.app.main import app


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
        self.assertIn("/api/v1/applications/{application_id}/hr-override", paths)