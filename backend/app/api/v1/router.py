"""
V1 API Router — aggregates all v1 endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    agents,
    applications,
    auth,
    insights,
    jobs,
    oauth,
    onboarding,
    orchestrator,
    profile,
    recruiters,
    resumes,
    subscription,
    target_companies,
    trash,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(oauth.router, prefix="/oauth", tags=["OAuth"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["Onboarding"])
api_router.include_router(profile.router, prefix="/profile", tags=["Profile"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["Resumes"])
api_router.include_router(applications.router, prefix="/applications", tags=["Applications"])
api_router.include_router(recruiters.router, prefix="/recruiters", tags=["Recruiters"])
api_router.include_router(insights.router, prefix="/insights", tags=["Insights"])
api_router.include_router(agents.router, prefix="/agents", tags=["Agents"])
api_router.include_router(orchestrator.router, prefix="/orchestrator", tags=["Orchestrator"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(trash.router, prefix="/trash", tags=["Trash"])
api_router.include_router(subscription.router, prefix="/subscription", tags=["Subscription"])
api_router.include_router(target_companies.router, prefix="/target-companies", tags=["Target Companies"])
