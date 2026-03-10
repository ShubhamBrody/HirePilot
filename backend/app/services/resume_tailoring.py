"""
AI Resume Tailoring Service

Uses GPT-4 to analyze job descriptions and generate tailored resumes
that are optimized for ATS systems while preserving factual accuracy.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


# ── System Prompts ────────────────────────────────────────────────

RESUME_ANALYSIS_SYSTEM_PROMPT = """You are an expert resume writer and ATS optimization specialist.
You analyze job descriptions to extract key requirements and optimize resumes
for maximum ATS compatibility and recruiter appeal.

Critical rules:
1. NEVER fabricate experience, skills, or achievements
2. NEVER change dates, company names, or educational credentials
3. Only reword existing experience to better match job requirements
4. Highlight relevant skills that the candidate actually has
5. Reorder sections to put the most relevant experience first
6. Use keywords from the job description naturally in bullet points
7. Quantify achievements where the original resume provides data
8. Maintain the candidate's voice and authenticity
"""

JD_ANALYSIS_PROMPT = """Analyze this job description and extract structured information.

Job Description:
{job_description}

Return a JSON object with these fields:
{{
    "required_skills": ["skill1", "skill2", ...],
    "preferred_skills": ["skill1", "skill2", ...],
    "key_responsibilities": ["resp1", "resp2", ...],
    "ats_keywords": ["keyword1", "keyword2", ...],
    "experience_level": "junior|mid|senior|lead",
    "industry_focus": "description of industry/domain",
    "culture_signals": ["signal1", "signal2", ...]
}}

Return ONLY valid JSON, no markdown or explanation."""

RESUME_TAILOR_PROMPT = """Tailor this LaTeX resume for the given job description.

MASTER RESUME (LaTeX):
{master_resume}

JOB DESCRIPTION ANALYSIS:
{jd_analysis}

TARGET COMPANY: {company}
TARGET ROLE: {role}

{additional_instructions}

Instructions:
1. Rewrite bullet points to incorporate relevant ATS keywords naturally
2. Reorder experience sections to highlight the most relevant work first
3. Emphasize matching skills in the skills section
4. Adjust the professional summary (if present) to align with the role
5. Keep all factual information (dates, companies, degrees) unchanged
6. Ensure the LaTeX compiles correctly — don't break formatting
7. Add any skills the candidate has that match the JD keywords

Return ONLY the complete tailored LaTeX source code.
Do NOT include markdown code blocks or explanations.
Start directly with \\documentclass or the first LaTeX command."""

CHANGES_SUMMARY_PROMPT = """Compare these two resume versions and summarize the changes made.

ORIGINAL:
{original}

TAILORED:
{tailored}

Return a JSON object:
{{
    "changes_summary": "Brief description of all changes",
    "sections_modified": ["section1", "section2"],
    "keywords_added": ["keyword1", "keyword2"],
    "keywords_emphasized": ["keyword1", "keyword2"],
    "optimization_score": 0.0-1.0,
    "ats_compatibility_notes": "Assessment of ATS friendliness"
}}

Return ONLY valid JSON."""


class ResumeTailoringService:
    """
    AI-powered resume tailoring service.

    Workflow:
    1. Analyze job description → extract requirements & keywords
    2. Compare with user's master resume
    3. Generate tailored version with optimized ATS keywords
    4. Provide change summary and optimization score
    """

    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
        self.model = settings.openai_model

    async def analyze_job_description(self, job_description: str) -> dict[str, Any]:
        """Extract structured requirements from a job description."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": RESUME_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": JD_ANALYSIS_PROMPT.format(
                    job_description=job_description
                )},
            ],
            max_tokens=settings.openai_max_tokens,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        text = response.choices[0].message.content or "{}"
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error("Failed to parse JD analysis response", response=text)
            return {}

    async def tailor_resume(
        self,
        master_resume_latex: str,
        job_description: str,
        company: str,
        role: str,
        additional_instructions: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a tailored resume version.

        Returns dict with:
        - tailored_latex: The new LaTeX source
        - jd_analysis: Parsed job description analysis
        - changes_summary: What was changed and why
        - optimization_score: ATS optimization score (0-1)
        """
        # Step 1: Analyze the job description
        logger.info("Analyzing job description", company=company, role=role)
        jd_analysis = await self.analyze_job_description(job_description)

        # Step 2: Generate tailored resume
        logger.info("Generating tailored resume", company=company, role=role)
        extra_instructions = ""
        if additional_instructions:
            extra_instructions = f"Additional instructions: {additional_instructions}"

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": RESUME_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": RESUME_TAILOR_PROMPT.format(
                    master_resume=master_resume_latex,
                    jd_analysis=json.dumps(jd_analysis, indent=2),
                    company=company,
                    role=role,
                    additional_instructions=extra_instructions,
                )},
            ],
            max_tokens=settings.openai_max_tokens,
            temperature=settings.openai_temperature,
        )

        tailored_latex = response.choices[0].message.content or master_resume_latex

        # Clean up any potential markdown formatting
        if tailored_latex.startswith("```"):
            lines = tailored_latex.split("\n")
            tailored_latex = "\n".join(lines[1:-1])

        # Step 3: Generate changes summary
        logger.info("Generating changes summary")
        changes = await self._generate_changes_summary(
            master_resume_latex, tailored_latex
        )

        return {
            "tailored_latex": tailored_latex,
            "jd_analysis": jd_analysis,
            "changes_summary": changes.get("changes_summary", ""),
            "matched_keywords": changes.get("keywords_added", []) + changes.get("keywords_emphasized", []),
            "optimization_score": changes.get("optimization_score", 0.0),
        }

    async def _generate_changes_summary(
        self, original: str, tailored: str
    ) -> dict[str, Any]:
        """Compare original and tailored resumes, summarize changes."""
        # Truncate to avoid token limits
        orig_truncated = original[:3000]
        tailored_truncated = tailored[:3000]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": RESUME_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": CHANGES_SUMMARY_PROMPT.format(
                    original=orig_truncated,
                    tailored=tailored_truncated,
                )},
            ],
            max_tokens=1000,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        text = response.choices[0].message.content or "{}"
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"changes_summary": "Unable to parse changes", "optimization_score": 0.0}

    async def compute_match_score(
        self,
        resume_text: str,
        job_description: str,
    ) -> dict[str, Any]:
        """
        Compute how well a resume matches a job description.
        Returns match score and detailed reasoning.
        """
        prompt = f"""Score how well this resume matches this job on a scale of 0.0 to 1.0.

RESUME (first 2000 chars):
{resume_text[:2000]}

JOB DESCRIPTION (first 2000 chars):
{job_description[:2000]}

Return JSON:
{{
    "match_score": 0.0-1.0,
    "reasoning": "Brief explanation",
    "matched_skills": ["skill1", "skill2"],
    "missing_skills": ["skill1", "skill2"],
    "recommendations": ["rec1", "rec2"]
}}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": RESUME_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        text = response.choices[0].message.content or "{}"
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"match_score": 0.0, "reasoning": "Unable to compute score"}
