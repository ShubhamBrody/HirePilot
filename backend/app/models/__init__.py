"""Database models package."""

from app.models.user import User
from app.models.job import JobListing, JobSource
from app.models.recruiter import Recruiter, OutreachMessage
from app.models.resume import ResumeVersion, ResumeTemplate
from app.models.application import Application, ApplicationStatus
from app.models.audit import AuditLog
from app.models.email_tracking import EmailTracking
from app.models.agent_execution import AgentExecution
from app.models.work_experience import WorkExperience
from app.models.education import Education
from app.models.subscription import Subscription
from app.models.target_company import TargetCompany, URLDiscoveryMethod, ScrapeStatus
from app.models.scraping_log import CompanyScrapingLog, ScrapingRunStatus, ScrapingErrorType

__all__ = [
    "User",
    "JobListing",
    "JobSource",
    "Recruiter",
    "OutreachMessage",
    "ResumeVersion",
    "ResumeTemplate",
    "Application",
    "ApplicationStatus",
    "AuditLog",
    "EmailTracking",
    "AgentExecution",
    "WorkExperience",
    "Education",
    "Subscription",
    "TargetCompany",
    "URLDiscoveryMethod",
    "ScrapeStatus",
    "CompanyScrapingLog",
    "ScrapingRunStatus",
    "ScrapingErrorType",
]
