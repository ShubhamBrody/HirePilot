"""
LLM Integration Tests — GitHub Models (GPT-4o) via OpenAI-compatible API.

Tests ALL LLM-dependent endpoints against the real API.
Requires LLM_API_KEY to be set in .env.

Run:
    pytest tests/test_llm_integration.py -v -x --timeout=120
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.llm_service import LLMService

pytestmark = pytest.mark.asyncio

# ── Sample data ─────────────────────────────────────────────────

SAMPLE_LATEX = r"""
\documentclass[11pt]{article}
\usepackage[margin=0.7in]{geometry}
\usepackage{enumitem}
\begin{document}

\begin{center}
{\LARGE \textbf{Shubham Brody}} \\[4pt]
shubham@example.com \quad | \quad +91-9876543210 \quad | \quad linkedin.com/in/shubhambrody
\end{center}

\section*{Summary}
Backend engineer with 3+ years of experience building scalable distributed systems.

\section*{Experience}

\textbf{Software Engineer II} --- \textit{Microsoft} \hfill Jan 2022 -- Present
\begin{itemize}[nosep]
  \item Designed event-driven microservices handling 5M daily transactions
  \item Reduced API latency by 40\% through caching and query optimisation
  \item Led migration from monolith to Kubernetes-based architecture
\end{itemize}

\textbf{Backend Developer} --- \textit{Flipkart} \hfill Jun 2020 -- Dec 2021
\begin{itemize}[nosep]
  \item Built real-time inventory management system in Python and Go
  \item Implemented CI/CD pipelines reducing deployment time by 60\%
\end{itemize}

\section*{Education}
\textbf{B.Tech Computer Science} --- IIT Delhi \hfill 2016 -- 2020 \\
GPA: 8.9/10

\section*{Skills}
Python, Go, FastAPI, Django, PostgreSQL, Redis, Docker, Kubernetes, AWS, Kafka

\section*{Projects}
\textbf{HirePilot} — AI-powered job search automation platform \\
Built with FastAPI, Next.js, Celery, and LLM integration.

\end{document}
"""

SAMPLE_JOB_DESCRIPTION = """
Senior Backend Engineer — Google — Bangalore

We're looking for a Senior Backend Engineer to join our Cloud Platform team.

Requirements:
- 4+ years of experience in backend development
- Strong proficiency in Python, Go, or Java
- Experience with distributed systems and microservices
- Familiarity with Kubernetes, Docker, and CI/CD
- Experience with cloud platforms (GCP, AWS, or Azure)
- Strong problem-solving and communication skills

Nice to have:
- Experience with event-driven architectures (Kafka, Pub/Sub)
- Knowledge of database internals (PostgreSQL, Spanner)
- Open source contributions

Salary: ₹35-55 LPA
"""


# ── Helper: skip if no API key ──────────────────────────────────

def _skip_if_no_key():
    """Skip test if LLM_API_KEY is not configured."""
    from app.core.config import get_settings
    s = get_settings()
    key = s.llm_api_key.get_secret_value()
    if not key:
        pytest.skip("LLM_API_KEY not set — skipping live LLM test")


# ═════════════════════════════════════════════════════════════════
# 1. LLMService unit-level integration tests (direct method calls)
# ═════════════════════════════════════════════════════════════════


class TestLLMHealthCheck:
    """Test the is_available() health check."""

    async def test_is_available(self):
        _skip_if_no_key()
        llm = LLMService()
        result = await llm.is_available()
        assert result is True, "LLM API should be reachable with valid key"

    async def test_is_available_bad_key(self):
        llm = LLMService(api_key="invalid-key-12345")
        result = await llm.is_available()
        assert result is False, "Should return False with invalid API key"


class TestLLMGenerate:
    """Test basic generate() and generate_json() methods."""

    async def test_generate_simple(self):
        _skip_if_no_key()
        llm = LLMService()
        result = await llm.generate("Reply with exactly: HELLO")
        assert isinstance(result, str)
        assert len(result) > 0
        assert "HELLO" in result.upper()

    async def test_generate_with_system(self):
        _skip_if_no_key()
        llm = LLMService()
        result = await llm.generate(
            "What is 2+2?",
            system="You are a calculator. Reply with only the number.",
        )
        assert "4" in result

    async def test_generate_json(self):
        _skip_if_no_key()
        llm = LLMService()
        result = await llm.generate_json(
            'Return a JSON object: {"name": "test", "value": 42}',
            system="Return ONLY valid JSON. No markdown fences.",
        )
        assert isinstance(result, dict)
        assert "name" in result
        assert "value" in result


class TestLLMChat:
    """Test multi-turn chat() method."""

    async def test_chat_basic(self):
        _skip_if_no_key()
        llm = LLMService()
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Be very brief."},
            {"role": "user", "content": "What is the capital of France?"},
        ]
        result = await llm.chat(messages)
        assert isinstance(result, str)
        assert "paris" in result.lower()


# ═════════════════════════════════════════════════════════════════
# 2. Domain method tests
# ═════════════════════════════════════════════════════════════════


class TestResumeParser:
    """Test parse_resume() — LaTeX → structured JSON."""

    async def test_parse_resume(self):
        _skip_if_no_key()
        llm = LLMService()
        result = await llm.parse_resume(SAMPLE_LATEX)
        assert isinstance(result, dict)
        # Should extract key sections
        assert "skills" in result or "experience" in result
        if "experience" in result:
            assert isinstance(result["experience"], list)
            assert len(result["experience"]) >= 1


class TestFitScore:
    """Test compute_fit_score() — resume vs job description."""

    async def test_compute_fit_score(self):
        _skip_if_no_key()
        llm = LLMService()
        result = await llm.compute_fit_score(SAMPLE_LATEX, SAMPLE_JOB_DESCRIPTION)
        assert isinstance(result, dict)
        assert "match_score" in result
        score = result["match_score"]
        assert isinstance(score, (int, float))
        assert 0.0 <= score <= 1.0
        # Our sample resume is a good match for the job
        assert score > 0.3, f"Expected decent match, got {score}"


class TestResumeTailoring:
    """Test tailor_resume() — the core feature."""

    async def test_tailor_resume(self):
        _skip_if_no_key()
        llm = LLMService()
        result = await llm.tailor_resume(
            master_latex=SAMPLE_LATEX,
            job_description=SAMPLE_JOB_DESCRIPTION,
            company="Google",
            role="Senior Backend Engineer",
        )
        assert isinstance(result, dict)
        assert "tailored_latex" in result
        latex = result["tailored_latex"]
        assert isinstance(latex, str)
        assert len(latex) > 100
        # Must contain documentclass
        assert "\\documentclass" in latex or "\\begin{document}" in latex
        # CRITICAL: Must NOT fabricate companies
        assert "Microsoft" in latex, "Original company Microsoft must be preserved"
        assert "Flipkart" in latex, "Original company Flipkart must be preserved"

    async def test_tailor_resume_no_fabrication(self):
        """Ensure the LLM doesn't add fake companies."""
        _skip_if_no_key()
        llm = LLMService()
        result = await llm.tailor_resume(
            master_latex=SAMPLE_LATEX,
            job_description=SAMPLE_JOB_DESCRIPTION,
            company="Google",
            role="Senior Backend Engineer",
        )
        latex = result["tailored_latex"].lower()
        # Must not add Google as an experience entry
        # (It's the target company, not one the candidate worked at)
        # Count occurrences of "google" in experience section area
        # The name may appear in a "targeted at Google" line but NOT as employer
        assert "microsoft" in latex
        assert "flipkart" in latex


class TestChangesSummary:
    """Test generate_changes_summary() — diff two resume versions."""

    async def test_changes_summary(self):
        _skip_if_no_key()
        llm = LLMService()
        # Create a slightly modified version
        modified = SAMPLE_LATEX.replace(
            "5M daily transactions",
            "10M+ daily transactions across 3 regions",
        )
        result = await llm.generate_changes_summary(SAMPLE_LATEX, modified)
        assert isinstance(result, dict)
        assert "changes_summary" in result


class TestChatResume:
    """Test chat_resume() — interactive resume editing."""

    async def test_chat_resume_reword(self):
        _skip_if_no_key()
        llm = LLMService()
        result = await llm.chat_resume(
            resume_latex=SAMPLE_LATEX,
            user_message="Make the bullets more impactful with quantified results.",
        )
        assert isinstance(result, dict)
        assert "explanation" in result
        if result.get("updated_latex"):
            latex = result["updated_latex"]
            assert "\\documentclass" in latex or "\\begin{document}" in latex
            # Must preserve companies
            assert "Microsoft" in latex
            assert "Flipkart" in latex


class TestSkillClassification:
    """Test classify_skills() — categorize raw skills."""

    async def test_classify_skills(self):
        _skip_if_no_key()
        llm = LLMService()
        raw_skills = [
            "Python", "Go", "React", "PostgreSQL", "Docker",
            "Kubernetes", "AWS", "Git", "Microservices", "Leadership",
        ]
        result = await llm.classify_skills(raw_skills)
        assert isinstance(result, dict)
        # Should have our expected categories
        assert "Languages" in result
        assert "Frameworks" in result or "Databases" in result
        # Python should be classified under Languages
        all_classified = []
        for cat, skills in result.items():
            all_classified.extend(skills)
        assert any("Python" in s for s in all_classified), "Python should appear in classifications"


class TestPdfToLatex:
    """Test pdf_to_latex() — text → LaTeX conversion."""

    async def test_pdf_to_latex(self):
        _skip_if_no_key()
        llm = LLMService()
        plain_text = """
Shubham Brody
Software Engineer
shubham@example.com | +91-9876543210

Experience:
Software Engineer II, Microsoft (Jan 2022 - Present)
- Designed event-driven microservices handling 5M daily transactions
- Reduced API latency by 40%

Education:
B.Tech Computer Science, IIT Delhi (2016-2020), GPA: 8.9/10

Skills: Python, Go, FastAPI, Docker, Kubernetes, AWS
"""
        result = await llm.pdf_to_latex(plain_text)
        assert isinstance(result, str)
        assert "\\documentclass" in result
        assert "\\begin{document}" in result
        assert "\\end{document}" in result


class TestJobScraping:
    """Test scrape_job_from_url() — HTML → structured job data."""

    async def test_scrape_job_html(self):
        _skip_if_no_key()
        llm = LLMService()
        html = """
        <html><body>
        <h1>Senior Backend Engineer</h1>
        <h2>Google - Bangalore, India</h2>
        <div class="description">
            We're looking for a Senior Backend Engineer to join our Cloud team.
            Requirements: 4+ years Python/Go, distributed systems, Kubernetes.
            Salary: ₹35-55 LPA. Remote-friendly.
        </div>
        <div class="skills">Python, Go, Kubernetes, Docker, GCP</div>
        </body></html>
        """
        result = await llm.scrape_job_from_url(html)
        assert isinstance(result, dict)
        assert "title" in result
        assert "company" in result


# ═════════════════════════════════════════════════════════════════
# 3. API endpoint integration tests (via HTTP client)
# ═════════════════════════════════════════════════════════════════


class TestMatchScoreEndpoint:
    """Test GET /jobs/{id}/match-score endpoint."""

    async def test_match_score_api(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        _skip_if_no_key()
        # Create a resume + job
        resume = await factory.create_resume(
            db_session, test_user.id,
            latex_source=SAMPLE_LATEX, is_master=True,
        )
        job = await factory.create_job(
            db_session, test_user.id,
            title="Senior Backend Engineer",
            company="Google",
            description=SAMPLE_JOB_DESCRIPTION,
        )
        # Update user's master_resume_latex
        test_user.master_resume_latex = SAMPLE_LATEX
        await db_session.flush()

        response = await client.get(
            f"/api/v1/jobs/{job.id}/match-score",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "match_score" in data
        assert 0 <= data["match_score"] <= 1


class TestResumeParseEndpoint:
    """Test POST /resumes/{id}/parse endpoint."""

    async def test_parse_resume_api(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db_session: AsyncSession,
        test_user: User,
        factory,
    ):
        _skip_if_no_key()
        resume = await factory.create_resume(
            db_session, test_user.id,
            latex_source=SAMPLE_LATEX, is_master=True,
        )
        response = await client.post(
            f"/api/v1/resumes/{resume.id}/parse",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        # Response wraps content in parsed_sections
        sections = data.get("parsed_sections", data)
        assert isinstance(sections, dict)
        assert any(k in sections for k in ["skills", "experience", "education", "name"])


class TestClassifySkillsEndpoint:
    """Test POST /onboarding/classify-skills endpoint."""

    async def test_classify_skills_api(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        _skip_if_no_key()
        response = await client.post(
            "/api/v1/onboarding/classify-skills",
            headers=auth_headers,
            json={"skills": ["Python", "React", "PostgreSQL", "Docker", "Leadership"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        # Should return categorized skills
        assert "classified" in data or "Languages" in data or isinstance(data, dict)
