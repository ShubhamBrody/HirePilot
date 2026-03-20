"""
Subscription Endpoints — Plan management, mock billing, feature gating.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.subscription import PLAN_CONFIGS, Subscription
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.user_repo import UserRepository
from app.schemas.subscription import (
    ChangePlanRequest,
    FeatureGateResponse,
    MockPaymentRequest,
    PlanInfo,
    PlansListResponse,
    SubscriptionResponse,
)

router = APIRouter()

ENTERPRISE_EMAIL = "recruitshubhamtiwari@gmail.com"


async def _ensure_subscription(
    user_id: str, session: AsyncSession
) -> Subscription:
    """Get or create subscription for user. Auto-assigns Enterprise for special email."""
    repo = SubscriptionRepository(session)
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    sub = await repo.get_by_user(uid)
    if sub:
        return sub

    # Check if user qualifies for auto-enterprise
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(uid)
    plan = "enterprise" if user and user.email == ENTERPRISE_EMAIL else "free"
    config = PLAN_CONFIGS[plan]

    sub = Subscription(
        user_id=uid,
        plan=plan,
        status="active",
        **config,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub


def _sub_to_response(sub: Subscription) -> SubscriptionResponse:
    return SubscriptionResponse(
        plan=sub.plan,
        status=sub.status,
        price_monthly=sub.price_monthly,
        billing_cycle=sub.billing_cycle,
        max_resumes=sub.max_resumes,
        max_applications_per_day=sub.max_applications_per_day,
        max_job_scrapes_per_day=sub.max_job_scrapes_per_day,
        ai_tailoring_enabled=sub.ai_tailoring_enabled,
        recruiter_outreach_enabled=sub.recruiter_outreach_enabled,
        autonomous_mode_enabled=sub.autonomous_mode_enabled,
        mock_card_last4=sub.mock_card_last4,
        mock_next_billing_date=sub.mock_next_billing_date.isoformat() if sub.mock_next_billing_date else None,
    )


@router.get("/plans", response_model=PlansListResponse)
async def list_plans(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """List all available plans with current user's plan."""
    sub = await _ensure_subscription(user_id, session)
    plans = [
        PlanInfo(name=name, **config)
        for name, config in PLAN_CONFIGS.items()
    ]
    return PlansListResponse(plans=plans, current_plan=sub.plan)


@router.get("/current", response_model=SubscriptionResponse)
async def get_current_subscription(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Get current user's subscription."""
    sub = await _ensure_subscription(user_id, session)
    return _sub_to_response(sub)


@router.post("/change-plan", response_model=SubscriptionResponse)
async def change_plan(
    req: ChangePlanRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Change subscription plan (mock billing)."""
    if req.plan not in PLAN_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {req.plan}")

    sub = await _ensure_subscription(user_id, session)
    config = PLAN_CONFIGS[req.plan]

    sub.plan = req.plan
    sub.price_monthly = config["price_monthly"]
    sub.max_resumes = config["max_resumes"]
    sub.max_applications_per_day = config["max_applications_per_day"]
    sub.max_job_scrapes_per_day = config["max_job_scrapes_per_day"]
    sub.ai_tailoring_enabled = config["ai_tailoring_enabled"]
    sub.recruiter_outreach_enabled = config["recruiter_outreach_enabled"]
    sub.autonomous_mode_enabled = config["autonomous_mode_enabled"]

    if req.plan != "free":
        sub.mock_next_billing_date = datetime.now(UTC) + timedelta(days=30)
    else:
        sub.mock_next_billing_date = None

    sub.status = "active"
    await session.commit()
    await session.refresh(sub)
    return _sub_to_response(sub)


@router.post("/mock-payment", response_model=SubscriptionResponse)
async def mock_payment(
    req: MockPaymentRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Mock payment — store card last4."""
    sub = await _ensure_subscription(user_id, session)
    sub.mock_card_last4 = req.card_last4[:4]
    await session.commit()
    await session.refresh(sub)
    return _sub_to_response(sub)


@router.get("/check-feature/{feature}", response_model=FeatureGateResponse)
async def check_feature(
    feature: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Check if user has access to a feature based on their plan."""
    sub = await _ensure_subscription(user_id, session)

    feature_map = {
        "ai_tailoring": ("ai_tailoring_enabled", "pro"),
        "recruiter_outreach": ("recruiter_outreach_enabled", "pro"),
        "autonomous_mode": ("autonomous_mode_enabled", "enterprise"),
    }

    if feature not in feature_map:
        raise HTTPException(status_code=400, detail=f"Unknown feature: {feature}")

    attr, required_plan = feature_map[feature]
    allowed = getattr(sub, attr, False)

    return FeatureGateResponse(
        allowed=allowed,
        reason=None if allowed else f"Upgrade to {required_plan} to access this feature",
        current_plan=sub.plan,
        required_plan=None if allowed else required_plan,
    )
