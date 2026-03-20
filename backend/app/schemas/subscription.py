"""
Subscription Schemas — Plan info, billing, feature gating.
"""

from pydantic import BaseModel


class PlanInfo(BaseModel):
    name: str
    price_monthly: float
    max_resumes: int
    max_applications_per_day: int
    max_job_scrapes_per_day: int
    ai_tailoring_enabled: bool
    recruiter_outreach_enabled: bool
    autonomous_mode_enabled: bool


class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    price_monthly: float
    billing_cycle: str
    max_resumes: int
    max_applications_per_day: int
    max_job_scrapes_per_day: int
    ai_tailoring_enabled: bool
    recruiter_outreach_enabled: bool
    autonomous_mode_enabled: bool
    mock_card_last4: str | None = None
    mock_next_billing_date: str | None = None


class ChangePlanRequest(BaseModel):
    plan: str  # free, pro, enterprise


class MockPaymentRequest(BaseModel):
    card_last4: str  # mock: just store last 4 digits


class PlansListResponse(BaseModel):
    plans: list[PlanInfo]
    current_plan: str


class FeatureGateResponse(BaseModel):
    allowed: bool
    reason: str | None = None
    current_plan: str
    required_plan: str | None = None
