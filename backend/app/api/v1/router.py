"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, projects, datasets, refinery

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["Datasets"])
api_router.include_router(refinery.router, prefix="/refinery", tags=["Refinery"])
