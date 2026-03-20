"""
Insights Schemas — Skills analysis, hiring trends, salary analysis.
"""

from pydantic import BaseModel


class SkillInsight(BaseModel):
    """A single skill with its frequency and status."""
    skill: str
    frequency: int  # How many job listings mention this skill
    percentage: float  # % of jobs that need this skill
    user_has: bool  # Whether the user's resume includes this


class SkillsInsightsResponse(BaseModel):
    """Full skills analysis for the user's target role."""
    total_jobs_analyzed: int
    target_role: str | None = None

    # Top skills employers are looking for
    top_skills: list[SkillInsight] = []

    # Skills the user has that are in demand
    matched_skills: list[SkillInsight] = []

    # Skills the user is missing (opportunity to learn)
    missing_skills: list[SkillInsight] = []

    # "Did You Know?" nuggets — human-readable insights
    did_you_know: list[str] = []


# ── Hiring Trends ────────────────────────────────────────────────


class CompanyHiringTrend(BaseModel):
    company: str
    active_listings: int
    roles: list[str] = []  # Sample role titles


class HiringTrendsResponse(BaseModel):
    total_companies: int
    total_active_jobs: int
    top_companies: list[CompanyHiringTrend] = []
    trending_roles: list[str] = []
    period_days: int = 30


# ── Salary Analysis ──────────────────────────────────────────────


class SalaryAnalysisResponse(BaseModel):
    user_ctc: float | None = None
    salary_currency: str | None = None
    market_median: float | None = None
    market_min: float | None = None
    market_max: float | None = None
    jobs_with_salary: int = 0
    total_jobs: int = 0
    percent_vs_market: float | None = None  # +20.0 = 20% above, -10.0 = 10% below
    recommendation: str | None = None
