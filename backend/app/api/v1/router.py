"""API v1 router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, projects, datasets, profiling, quality, transformations, analytics, jobs

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["Datasets"])
api_router.include_router(profiling.router, prefix="/profiling", tags=["Profiling"])
api_router.include_router(quality.router, prefix="/quality", tags=["Quality"])
api_router.include_router(transformations.router, prefix="/transformations", tags=["Transformations"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
