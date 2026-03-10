"""
V1 API Router — aggregates all v1 endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import applications, auth, jobs, oauth, recruiters, resumes

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(oauth.router, prefix="/oauth", tags=["OAuth"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["Resumes"])
api_router.include_router(applications.router, prefix="/applications", tags=["Applications"])
api_router.include_router(recruiters.router, prefix="/recruiters", tags=["Recruiters"])
