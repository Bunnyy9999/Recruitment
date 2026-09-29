from fastapi import APIRouter

from backend.app.schemas.health_schema import HealthResponse


api_router = APIRouter()
api_v1_router = APIRouter(prefix="/api/v1", tags=["v1"])


@api_router.get("/health", response_model=HealthResponse, tags=["health"])
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


api_router.include_router(api_v1_router)