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

THE MASTER RESUME IS YOUR SOP — it is the GROUND TRUTH.
You may ONLY ADD to it or MODIFY existing bullet text. You must NEVER REMOVE anything.

RULE 1 — NEVER REMOVE ANYTHING (ZERO TOLERANCE):
  - Every \\section in the master MUST appear in the output.
  - Every \\resumeSubheading (experience entry) MUST appear.
  - Every \\resumeProjectHeading (project entry) MUST appear.
  - Every \\resumeItem (bullet point) MUST appear (modified text is OK).
  - Do NOT add new sections that duplicate existing ones
    (e.g., if "Technical Skills" exists, do NOT add a separate "Skills" section).

RULE 2 — PRESERVE EXACT LaTeX STRUCTURE:
  - If a section uses raw \\begin{itemize}...\\end{itemize}, keep that exact format.
    Do NOT convert it to \\resumeSubHeadingListStart/\\resumeItemListStart.
  - If a section uses \\resumeSubHeadingListStart, keep that exact format.
  - Preserve the EXACT preamble: \\documentclass, \\usepackage, \\newcommand lines.
  - Do NOT add new \\usepackage or \\newcommand lines.

RULE 3 — IMMUTABLE FACTS:
  - Company names, job titles, employment dates: COPY EXACTLY.
  - Education: institution, degree, dates, GPA: COPY EXACTLY.
  - Project names and tech stacks in project headers: COPY EXACTLY.
  - Contact info (name, email, phone, URLs): COPY EXACTLY.
  - Numerical metrics/stats from the original (percentages, counts): PRESERVE.
  - GitHub links: COPY EXACTLY.

RULE 4 — WHAT YOU CAN MODIFY:
  a) REORDER sections by relevance to the target role.
  b) REORDER entries within a section by relevance.
  c) REORDER bullet points within an entry by relevance.
  d) REWRITE bullet text under Experience to match job requirements.
     You MAY fabricate/embellish work descriptions under existing companies.
  e) ENHANCE project bullet text to highlight relevant aspects.
     Keep original meaning — don't turn an AI Trading project into something unrelated.
  f) ADD new bullet points to any existing entry.
  g) ADD new skills/keywords to the Technical Skills / Skills section.

RULE 5 — KEYWORD STRATEGY:
  - Weave JD keywords into Experience bullets and Skills subtly.
  - Not keyword-stuffed — integrated naturally into sentences.
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

MASTER RESUME (LaTeX — this is the SOP, do NOT remove anything from it):
{master_resume}

JOB DESCRIPTION ANALYSIS:
{jd_analysis}

TARGET COMPANY: {company}
TARGET ROLE: {role}

{additional_instructions}

RULES — follow ALL of these:
1. Do NOT remove ANY section, bullet point, project entry, or experience entry.
2. Do NOT add sections that duplicate existing ones (e.g., no "Skills" if "Technical Skills" exists).
3. PRESERVE the exact LaTeX formatting of each section — if a section uses raw
   \\begin{{itemize}}...\\end{{itemize}}, keep it that way. Do NOT convert to
   \\resumeSubHeadingListStart/\\resumeItemListStart or vice versa.
4. PRESERVE all numerical metrics/stats from the original (percentages, counts, etc.).
5. PRESERVE all GitHub links exactly as they appear.
6. REORDER sections, entries, and bullets by relevance to the target role.
7. MODIFY experience bullet points — rewrite/embellish to match the JD.
8. ENHANCE project bullet text to highlight relevant aspects (keep original meaning).
9. ADD new bullet points to existing entries if needed.
10. ADD new skills to the Skills section that match the JD.
11. ADD ATS keywords from the JD into existing content naturally and subtly.
12. Keep ALL immutable facts: dates, company names, job titles, degrees, GPAs, contact info.

LATEX RULES:
- Preserve the exact \\documentclass line and all \\usepackage/\\newcommand declarations.
- Ensure every \\begin{{...}} has a matching \\end{{...}}.
- Escape special characters: %, $, &, #, _ must be \\%, \\$, \\&, \\#, \\_
- Start with \\documentclass and end with \\end{{document}}.
- Do NOT add new packages or custom commands not present in the original.

FINAL CHECK: Count sections, experience entries, project entries and bullets.
They must ALL be >= the master. If anything is missing, ADD IT BACK.

Return ONLY the complete tailored LaTeX source code.
Do NOT include markdown code blocks or explanations.
Start directly with \\documentclass."""

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
            lines = [l for l in lines if not l.strip().startswith("```")]
            tailored_latex = "\n".join(lines).strip()

        # Structural validation: splice back anything the LLM dropped
        from app.services.llm_service import LLMService
        tailored_latex = LLMService._validate_structure_preserved(
            master_resume_latex, tailored_latex
        )

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
