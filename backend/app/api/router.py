from fastapi import APIRouter, FastAPI

from backend.app.api.v1.jobs import router as jobs_router
from backend.app.api.v1.candidates import router as candidates_router
from backend.app.api.v1.applications import router as applications_router
from backend.app.api.v1.interviews import router as interviews_router
from backend.app.api.v1.dashboard import router as dashboard_router
from backend.app.schemas.health_schema import HealthResponse


api_router = APIRouter()
api_v1_router = APIRouter(prefix="/api/v1", tags=["v1"])


@api_router.get("/health", response_model=HealthResponse, tags=["health"])
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


api_v1_router.include_router(jobs_router)
api_v1_router.include_router(candidates_router)
api_v1_router.include_router(applications_router)
api_v1_router.include_router(interviews_router)
api_v1_router.include_router(dashboard_router)
api_router.include_router(api_v1_router)


app = FastAPI(title="DataRopes Recruitment Tool API", version="1.0.0")
app.include_router(api_router)