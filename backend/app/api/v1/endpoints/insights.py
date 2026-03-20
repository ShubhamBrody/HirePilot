"""
Skills Insights Endpoints — "Did You Know?" feature.

Aggregates skills from all job descriptions the user has collected,
compares against their resume, and provides actionable insights.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import get_current_user_id
from app.repositories.job_repo import JobRepository
from app.repositories.resume_repo import ResumeRepository
from app.repositories.user_repo import UserRepository
from app.schemas.insights import (
    CompanyHiringTrend,
    HiringTrendsResponse,
    SalaryAnalysisResponse,
    SkillInsight,
    SkillsInsightsResponse,
)
from app.services.llm_service import LLMService

router = APIRouter()
logger = get_logger(__name__)


@router.get("/skills", response_model=SkillsInsightsResponse)
async def get_skills_insights(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze all job descriptions the user has collected and compare
    skill requirements against the user's resume.

    Returns:
    - Top skills in demand for their target role
    - Skills they already have
    - Skills they're missing (learning opportunities)
    - "Did You Know?" nuggets
    """
    uid = uuid.UUID(user_id)
    job_repo = JobRepository(db)
    resume_repo = ResumeRepository(db)

    # Get all user's jobs
    jobs = await job_repo.get_user_jobs(uid, skip=0, limit=500)
    if not jobs:
        return SkillsInsightsResponse(
            total_jobs_analyzed=0,
            did_you_know=["Start discovering jobs to get personalized skill insights!"],
        )

    # Get user's master resume
    master_resume = await resume_repo.get_master_resume(uid)

    # Collect all technologies/skills from job listings
    all_skills: dict[str, int] = {}
    for job in jobs:
        if job.technologies:
            for skill in job.technologies.split(","):
                skill = skill.strip().lower()
                if skill and len(skill) > 1:
                    all_skills[skill] = all_skills.get(skill, 0) + 1

    # If we don't have enough structured skills from the technologies field,
    # use LLM to extract from job descriptions
    if len(all_skills) < 5 and jobs:
        llm = LLMService()
        # Combine a sample of job descriptions
        combined_descriptions = "\n---\n".join(
            [j.description[:1000] for j in jobs[:10] if j.description]
        )
        if combined_descriptions:
            try:
                result = await llm.generate_json(
                    f"Extract all technical skills, technologies, and tools mentioned in these job descriptions. "
                    f"Return a JSON object with a single key 'skills' containing a list of skill strings.\n\n"
                    f"{combined_descriptions[:8000]}",
                    system=(
                        "You are a skill extraction expert. Extract only concrete technical skills, "
                        "programming languages, frameworks, tools, and technologies. "
                        "Return ONLY valid JSON — no markdown, no commentary."
                    ),
                )
                for skill in result.get("skills", []):
                    s = skill.strip().lower()
                    if s and len(s) > 1:
                        all_skills[s] = all_skills.get(s, 0) + 1
            except Exception as e:
                logger.error("LLM skill extraction failed", error=str(e))

    # Get user's skills from resume
    user_skills: set[str] = set()
    if master_resume and master_resume.latex_source:
        llm = LLMService()
        try:
            parsed = await llm.parse_resume(master_resume.latex_source)
            for skill in parsed.get("skills", []):
                user_skills.add(skill.strip().lower())
        except Exception as e:
            logger.error("Resume skills parsing failed", error=str(e))

    # Build insights
    total_jobs = len(jobs)
    sorted_skills = sorted(all_skills.items(), key=lambda x: x[1], reverse=True)

    top_skills: list[SkillInsight] = []
    matched_skills: list[SkillInsight] = []
    missing_skills: list[SkillInsight] = []

    for skill, count in sorted_skills[:30]:
        pct = round((count / total_jobs) * 100, 1)
        has_skill = any(skill in us or us in skill for us in user_skills)

        insight = SkillInsight(
            skill=skill.title(),
            frequency=count,
            percentage=pct,
            user_has=has_skill,
        )
        top_skills.append(insight)

        if has_skill:
            matched_skills.append(insight)
        else:
            missing_skills.append(insight)

    # Generate "Did You Know?" nuggets
    did_you_know: list[str] = []

    if sorted_skills:
        top_skill, top_count = sorted_skills[0]
        top_pct = round((top_count / total_jobs) * 100)
        did_you_know.append(
            f"**{top_skill.title()}** appears in {top_pct}% of jobs you've seen — "
            f"it's the most in-demand skill for your target roles!"
        )

    if missing_skills:
        top_missing = missing_skills[0]
        did_you_know.append(
            f"Learning **{top_missing.skill}** could open doors — "
            f"{top_missing.percentage}% of jobs require it."
        )

    if matched_skills:
        did_you_know.append(
            f"You already have **{len(matched_skills)}** of the top {len(top_skills)} "
            f"most-requested skills. That's a strong foundation!"
        )

    if len(missing_skills) > 2:
        top_3_missing = ", ".join(s.skill for s in missing_skills[:3])
        did_you_know.append(
            f"The top skills you're missing: **{top_3_missing}**. "
            f"Consider upskilling in these areas."
        )

    if total_jobs >= 5:
        avg_skills_per_job = sum(all_skills.values()) / total_jobs
        did_you_know.append(
            f"On average, each job posting mentions **{avg_skills_per_job:.1f}** "
            f"skills — make sure your resume highlights your technical breadth."
        )

    # Determine target role from most common job titles
    title_counts: dict[str, int] = {}
    for job in jobs:
        t = job.title.lower().strip()
        title_counts[t] = title_counts.get(t, 0) + 1
    target_role = max(title_counts, key=title_counts.get) if title_counts else None  # type: ignore[arg-type]

    return SkillsInsightsResponse(
        total_jobs_analyzed=total_jobs,
        target_role=target_role.title() if target_role else None,
        top_skills=top_skills,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        did_you_know=did_you_know,
    )


# ── Hiring Trends ────────────────────────────────────────────────


@router.get("/hiring-trends", response_model=HiringTrendsResponse)
async def get_hiring_trends(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Top companies with the most active job listings in the user's saved jobs.
    Helps identify which companies are actively hiring.
    """
    uid = uuid.UUID(user_id)
    job_repo = JobRepository(db)
    jobs = await job_repo.get_user_jobs(uid, skip=0, limit=500)

    if not jobs:
        return HiringTrendsResponse(total_companies=0, total_active_jobs=0)

    # Aggregate by company
    company_data: dict[str, dict] = {}
    for job in jobs:
        if not job.is_active:
            continue
        co = (job.company or "Unknown").strip()
        if co not in company_data:
            company_data[co] = {"count": 0, "roles": set()}
        company_data[co]["count"] += 1
        company_data[co]["roles"].add(job.title)

    sorted_companies = sorted(company_data.items(), key=lambda x: x[1]["count"], reverse=True)

    top_companies = [
        CompanyHiringTrend(
            company=name,
            active_listings=info["count"],
            roles=list(info["roles"])[:5],
        )
        for name, info in sorted_companies[:15]
    ]

    # Trending roles across all companies
    role_counts: dict[str, int] = {}
    for job in jobs:
        if job.is_active:
            role_counts[job.title] = role_counts.get(job.title, 0) + 1
    trending_roles = [r for r, _ in sorted(role_counts.items(), key=lambda x: x[1], reverse=True)[:10]]

    return HiringTrendsResponse(
        total_companies=len(company_data),
        total_active_jobs=sum(1 for j in jobs if j.is_active),
        top_companies=top_companies,
        trending_roles=trending_roles,
    )


# ── Salary Analysis ──────────────────────────────────────────────


@router.get("/salary-analysis", response_model=SalaryAnalysisResponse)
async def get_salary_analysis(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Compare user's current salary against market rates from scraped jobs.
    Uses salary_min/salary_max fields from job listings.
    """
    uid = uuid.UUID(user_id)
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    job_repo = JobRepository(db)
    jobs = await job_repo.get_user_jobs(uid, skip=0, limit=500)

    # Filter jobs that have salary data
    salaries: list[float] = []
    for job in jobs:
        if job.salary_min and job.salary_min > 0:
            salaries.append(job.salary_min)
        if job.salary_max and job.salary_max > 0:
            salaries.append(job.salary_max)

    user_ctc = user.current_salary_ctc
    currency = user.salary_currency or "USD"

    if not salaries:
        return SalaryAnalysisResponse(
            user_ctc=user_ctc,
            salary_currency=currency,
            total_jobs=len(jobs),
            recommendation="Not enough salary data in your saved jobs yet. "
                           "Keep discovering jobs to get salary insights.",
        )

    salaries.sort()
    market_median = salaries[len(salaries) // 2]
    market_min = salaries[0]
    market_max = salaries[-1]

    pct_vs_market = None
    recommendation = None
    if user_ctc and user_ctc > 0 and market_median > 0:
        pct_vs_market = round(((user_ctc - market_median) / market_median) * 100, 1)
        if pct_vs_market < -15:
            recommendation = (
                f"Your current CTC is ~{abs(pct_vs_market):.0f}% below market median. "
                "There are good opportunities to significantly increase your compensation."
            )
        elif pct_vs_market < 0:
            recommendation = (
                f"You're slightly below market ({abs(pct_vs_market):.0f}%). "
                "Target roles in the upper salary range for a meaningful jump."
            )
        elif pct_vs_market < 15:
            recommendation = (
                "You're at or slightly above market rate. "
                "Focus on roles that offer equity/bonus upside for a meaningful bump."
            )
        else:
            recommendation = (
                f"You're {pct_vs_market:.0f}% above market median — strong position! "
                "Focus negotiations on total comp, growth, and scope."
            )

    return SalaryAnalysisResponse(
        user_ctc=user_ctc,
        salary_currency=currency,
        market_median=market_median,
        market_min=market_min,
        market_max=market_max,
        jobs_with_salary=len(salaries) // 2,  # approx, since we added min+max
        total_jobs=len(jobs),
        percent_vs_market=pct_vs_market,
        recommendation=recommendation,
    )
