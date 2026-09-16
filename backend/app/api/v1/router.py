"""API v1 router — only mounts implemented endpoint modules."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, projects, datasets

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["Datasets"])
