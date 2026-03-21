"""
LLM Service — GitHub Models / OpenAI-compatible integration.

Provides a reusable interface to call OpenAI-compatible LLM APIs
(GitHub Models, OpenAI, Azure OpenAI) for recruiter discovery,
message generation, resume analysis, etc.
"""

import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

MAX_COMPILE_RETRIES = 3


class LLMService:
    """Calls an OpenAI-compatible API (GitHub Models / OpenAI) for LLM inference."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
    ):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model
        self.api_key = api_key or settings.llm_api_key.get_secret_value()
        self.timeout = timeout
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens

    # ── Core helpers ────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        """Build request headers with auth."""
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int | None = None
    ) -> str:
        """
        Generate a text completion via chat completions endpoint.
        Returns the raw response text.
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return await self.chat(messages, max_tokens=max_tokens)

    async def generate_json(
        self, prompt: str, *, system: str | None = None
    ) -> Any:
        """
        Generate a response and parse it as JSON.
        Attempts to extract JSON from markdown code fences if present.
        """
        raw = await self.generate(prompt, system=system)
        return self._parse_json(raw)

    async def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
    ) -> str:
        """
        Multi-turn chat via OpenAI-compatible chat completions.
        Each message: {"role": "system"|"user"|"assistant", "content": "..."}
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    # ── JSON extraction ─────────────────────────────────────────

    @staticmethod
    def _parse_json(text: str) -> Any:
        """Parse JSON, handling markdown code fences."""
        text = text.strip()
        # Strip ```json ... ``` fences
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        return json.loads(text)

    # ── Health check ────────────────────────────────────────────

    async def is_available(self) -> bool:
        """Check if the LLM API is reachable and auth works."""
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    },
                )
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    # ── Compile-verify-retry helper ──────────────────────────────

    async def _ensure_compilable_latex(
        self, latex: str, *, context: str = ""
    ) -> tuple[str, bool]:
        """
        Compile the LaTeX and, if it fails, ask the LLM to fix it.
        Retries up to MAX_COMPILE_RETRIES times.

        Returns (final_latex, compiled_successfully).
        """
        from app.services.latex_compiler import LatexCompilerService

        compiler = LatexCompilerService()

        for attempt in range(MAX_COMPILE_RETRIES):
            result = await compiler.compile(latex)
            if result["success"]:
                logger.info("LaTeX compiled OK", attempt=attempt + 1)
                return latex, True

            # Gather error info for the LLM
            errors = result["errors"][:8]
            error_text = "\n".join(errors) if errors else "Unknown compilation error"
            logger.warning(
                "LaTeX compile failed, asking LLM to fix",
                attempt=attempt + 1,
                errors=error_text[:500],
            )

            fix_system = (
                "You are an expert LaTeX debugger. The LaTeX code below failed to compile. "
                "Fix ALL compilation errors and return the COMPLETE corrected LaTeX source. "
                "Start with \\documentclass and end with \\end{document}. "
                "Ensure all packages are properly loaded, all environments are balanced, "
                "all special characters are escaped, and the document structure is valid. "
                "Return ONLY the corrected LaTeX — no markdown fences, no explanations.\n\n"
                "COMMON FIXES:\n"
                "- Unbalanced braces: count { and } — they must match.\n"
                "- Missing \\end{...}: every \\begin{env} needs \\end{env}.\n"
                "- Unescaped special chars: & # % $ _ must be \\& \\# \\% \\$ \\\_\n"
                "- Missing packages: add \\usepackage{pkg} if a command needs it.\n"
                "- Unmatched \\left / \\right: always pair them.\n"
                "- Do NOT remove content to fix errors — fix the syntax instead."
            )
            fix_prompt = (
                f"This LaTeX failed to compile with these errors:\n\n"
                f"{error_text}\n\n"
                f"{'Context: ' + context + chr(10) + chr(10) if context else ''}"
                f"BROKEN LaTeX:\n{latex[:8000]}\n\n"
                f"Return the COMPLETE fixed LaTeX source."
            )
            raw = await self.generate(fix_prompt, system=fix_system)
            # Strip markdown fences
            if raw.strip().startswith("```"):
                lines = raw.strip().split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                raw = "\n".join(lines).strip()
            latex = raw

        # Final attempt — validate even if we exhausted retries
        final_result = await compiler.compile(latex)
        if final_result["success"]:
            return latex, True

        logger.error(
            "LaTeX still broken after all retries",
            errors=str(final_result["errors"][:3]),
        )
        return latex, False

    # ── Domain helpers ──────────────────────────────────────────

    async def parse_resume(self, latex_source: str) -> dict[str, Any]:
        """Parse a LaTeX resume into structured sections."""
        system = (
            "You are an expert resume parser. "
            "Given a LaTeX resume, extract structured data. "
            "Return ONLY valid JSON with these keys: "
            '"skills" (list of strings), '
            '"experience" (list of objects with keys: company, title, dates, bullets), '
            '"projects" (list of objects with keys: name, description, technologies), '
            '"achievements" (list of strings), '
            '"education" (list of objects with keys: institution, degree, dates), '
            '"name" (string), "summary" (string or null). '
            "Return ONLY valid JSON — no markdown, no commentary."
        )
        prompt = f"Parse this LaTeX resume:\n\n{latex_source[:8000]}"
        try:
            return await self.generate_json(prompt, system=system)
        except Exception as e:
            logger.error("Resume parsing failed", error=str(e))
            return {}

    async def compute_fit_score(
        self, resume_latex: str, job_description: str
    ) -> dict[str, Any]:
        """Compute how well a resume matches a job description."""
        system = (
            "You are an expert ATS system and career advisor. "
            "Compare the resume against the job description. "
            "Return ONLY valid JSON with these keys: "
            '"match_score" (float 0.0-1.0), '
            '"matched_skills" (list of skills the candidate has that match), '
            '"missing_skills" (list of required skills the candidate lacks), '
            '"strengths" (list of candidate strengths for this role), '
            '"weaknesses" (list of areas where candidate is weak for this role), '
            '"recommendations" (list of actionable suggestions). '
            "Return ONLY valid JSON — no markdown, no commentary."
        )
        prompt = (
            f"RESUME:\n{resume_latex[:6000]}\n\n"
            f"JOB DESCRIPTION:\n{job_description[:4000]}"
        )
        try:
            return await self.generate_json(prompt, system=system)
        except Exception as e:
            logger.error("Fit scoring failed", error=str(e))
            return {"match_score": 0.0, "matched_skills": [], "missing_skills": [],
                    "strengths": [], "weaknesses": [], "recommendations": []}

    async def tailor_resume(
        self, master_latex: str, job_description: str, company: str, role: str
    ) -> dict[str, Any]:
        """Tailor a resume for a specific job using AI."""
        # Build a structural inventory so the LLM knows exactly what must be preserved
        inventory = self._build_resume_inventory(master_latex)
        inventory_text = "\n".join(f"  - {item}" for item in inventory)

        system = (
            "You are an expert resume writer and ATS optimization specialist.\n\n"
            "THE MASTER RESUME IS YOUR SOP — it is the GROUND TRUTH.\n"
            "You may ONLY ADD to it or MODIFY existing bullet text. You must NEVER REMOVE anything.\n\n"
            "═══════════════════════════════════════════════════\n"
            "  RULE 1: NEVER REMOVE ANYTHING (ZERO TOLERANCE)\n"
            "═══════════════════════════════════════════════════\n"
            "  - Every \\section in the master MUST appear in the output.\n"
            "  - Every \\resumeSubheading (experience entry) MUST appear.\n"
            "  - Every \\resumeProjectHeading (project entry) MUST appear.\n"
            "  - Every \\resumeItem (bullet point) MUST appear (modified text is OK).\n"
            "  - Do NOT add new sections that duplicate existing ones.\n"
            "    (e.g., if 'Technical Skills' exists, do NOT add a separate 'Skills' section)\n\n"
            "═══════════════════════════════════════════════════\n"
            "  RULE 2: PRESERVE EXACT LaTeX STRUCTURE\n"
            "═══════════════════════════════════════════════════\n"
            "  - If a section uses raw \\begin{itemize}...\\end{itemize}, keep that exact format.\n"
            "    Do NOT convert it to \\resumeSubHeadingListStart/\\resumeItemListStart.\n"
            "  - If a section uses \\resumeSubHeadingListStart, keep that exact format.\n"
            "  - Preserve the EXACT preamble: \\documentclass, \\usepackage, \\newcommand lines.\n"
            "  - Do NOT add new \\usepackage or \\newcommand lines.\n\n"
            "═══════════════════════════════════════════════════\n"
            "  RULE 3: IMMUTABLE FACTS\n"
            "═══════════════════════════════════════════════════\n"
            "  - Company names, job titles, employment dates: COPY EXACTLY.\n"
            "  - Education: institution, degree, dates, GPA: COPY EXACTLY.\n"
            "  - Project names and the tech stacks in project headers: COPY EXACTLY.\n"
            "  - Contact info (name, email, phone, URLs): COPY EXACTLY.\n"
            "  - Numerical metrics/stats from the original (percentages, counts): PRESERVE.\n"
            "  - GitHub links: COPY EXACTLY.\n\n"
            "═══════════════════════════════════════════════════\n"
            "  RULE 4: WHAT YOU CAN MODIFY\n"
            "═══════════════════════════════════════════════════\n"
            "  a) REORDER sections by relevance to the target role.\n"
            "  b) REORDER entries within a section by relevance.\n"
            "  c) REORDER bullet points within an entry by relevance.\n"
            "  d) REWRITE bullet text under Experience to match job requirements.\n"
            "     You MAY fabricate/embellish work descriptions under existing companies.\n"
            "     If the JD needs React, Node.js, AWS — bullets should reflect that.\n"
            "  e) ENHANCE project bullet text to highlight relevant aspects.\n"
            "     But keep the original meaning — don't turn an AI Trading project into\n"
            "     something unrelated. Add relevant keywords naturally.\n"
            "  f) ADD new bullet points to any existing entry.\n"
            "  g) ADD new skills/keywords to the Technical Skills / Skills section.\n\n"
            "═══════════════════════════════════════════════════\n"
            "  RULE 5: KEYWORD STRATEGY\n"
            "═══════════════════════════════════════════════════\n"
            "  - Weave JD keywords into Experience bullets and Skills subtly.\n"
            "  - Not keyword-stuffed — integrated naturally into sentences.\n"
        )
        prompt = (
            f"Tailor this resume for **{role}** at **{company}**.\n\n"
            f"MASTER RESUME STRUCTURAL INVENTORY (every item MUST appear in output):\n"
            f"{inventory_text}\n\n"
            f"MASTER RESUME (LaTeX):\n{master_latex}\n\n"
            f"JOB DESCRIPTION:\n{job_description[:4000]}\n\n"
            "Return ONLY the complete tailored LaTeX source.\n"
            "Start directly with \\documentclass. No markdown fences.\n"
            "REMEMBER: every section, every entry, every bullet from the inventory above "
            "MUST appear in your output. You may modify text and reorder — but NEVER remove."
        )
        raw = await self.generate(prompt, system=system, max_tokens=8000)
        # Clean up any markdown fencing
        if raw.strip().startswith("```"):
            lines = raw.strip().split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw = "\n".join(lines).strip()

        # Structural validation: ensure no sections/entries were dropped (zero LLM calls)
        raw = self._validate_structure_preserved(master_latex, raw)

        # Compile-verify-retry: ensure the tailored LaTeX actually compiles
        fixed, compiled = await self._ensure_compilable_latex(
            raw, context=f"Resume tailored for {role} at {company}"
        )
        if not compiled:
            logger.warning("Tailored resume LaTeX may have compile issues")

        return {"tailored_latex": fixed, "compile_success": compiled}

    @staticmethod
    def _build_resume_inventory(latex: str) -> list[str]:
        """
        Parse the master resume LaTeX and build a human-readable inventory
        of all sections, entries, and bullet counts. This is included in the
        prompt so the LLM knows exactly what it must preserve.
        """
        import re
        items: list[str] = []

        # Sections
        sections = re.findall(r"\\section\{([^}]+)\}", latex)
        items.append(f"SECTIONS ({len(sections)}): {', '.join(sections)}")

        # Experience entries (resumeSubheading)
        exp_entries = re.findall(
            r"\\resumeSubheading\s*\{([^}]*)\}\s*\{([^}]*)\}\s*\{([^}]*)\}\s*\{([^}]*)\}",
            latex,
        )
        items.append(f"EXPERIENCE ENTRIES ({len(exp_entries)}):")
        for company_name, dates, title, location in exp_entries:
            items.append(f"  • {company_name} | {title} | {dates}")

        # Project entries (resumeProjectHeading)
        proj_entries = re.findall(
            r"\\resumeProjectHeading\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}\s*\{([^}]*)\}",
            latex,
        )
        items.append(f"PROJECT ENTRIES ({len(proj_entries)}):")
        for proj_text, date in proj_entries:
            # Extract just the project name from \textbf{Name}
            name_match = re.search(r"\\textbf\{([^}]+)\}", proj_text)
            name = name_match.group(1) if name_match else proj_text[:60]
            items.append(f"  • {name} ({date})")

        # Bullet counts per section
        # Split by \section and count \resumeItem in each
        section_splits = re.split(r"(\\section\{[^}]+\})", latex)
        current_section = ""
        for part in section_splits:
            sec_match = re.match(r"\\section\{([^}]+)\}", part)
            if sec_match:
                current_section = sec_match.group(1)
            elif current_section:
                bullet_count = len(re.findall(r"\\resumeItem\{", part))
                if bullet_count > 0:
                    items.append(f"BULLETS in '{current_section}': {bullet_count}")

        return items

    @staticmethod
    def _validate_structure_preserved(original: str, tailored: str) -> str:
        """
        Deep structural validation: ensure no sections, entries, or bullets
        were dropped from the tailored output. Also removes duplicate sections.
        This is a zero-LLM-call check — pure regex analysis.

        If entries are missing, splice them back from the original.
        """
        import re

        # ── 1. Remove duplicate sections ──────────────────────────────
        # e.g., if both "Technical Skills" and "Skills" exist, remove "Skills"
        section_pattern = re.compile(r"\\section\{([^}]+)\}")
        seen_sections: dict[str, int] = {}
        for m in section_pattern.finditer(tailored):
            name = m.group(1).strip()
            norm = name.lower().replace(" ", "")
            # "skills" is a suffix-duplicate of "technicalskills"
            seen_sections.setdefault(norm, 0)
            seen_sections[norm] += 1

        # Check for near-duplicate section names
        section_names = [m.group(1).strip() for m in section_pattern.finditer(tailored)]
        norms = [s.lower().replace(" ", "") for s in section_names]
        to_remove: list[str] = []
        for i, norm_i in enumerate(norms):
            for j, norm_j in enumerate(norms):
                if i != j and norm_i != norm_j:
                    # "skills" is a subset of "technicalskills"
                    if norm_i in norm_j and len(norm_i) < len(norm_j):
                        # norm_i is the shorter duplicate — check it wasn't in original
                        orig_norms = [
                            s.lower().replace(" ", "")
                            for s in re.findall(r"\\section\{([^}]+)\}", original)
                        ]
                        if norm_i not in orig_norms:
                            to_remove.append(section_names[i])

        for sec_name in to_remove:
            logger.warning("Removing duplicate section from tailored output", section=sec_name)
            sec_re = re.compile(
                rf"\\section\{{{re.escape(sec_name)}\}}.*?(?=\\section\{{|\\end\{{document\}})",
                re.DOTALL,
            )
            tailored = sec_re.sub("", tailored)

        # ── 2. Splice back missing sections ────────────────────────────
        orig_sections = [m.group(1).strip() for m in section_pattern.finditer(original)]
        tail_sections = [m.group(1).strip() for m in section_pattern.finditer(tailored)]
        tail_sections_lower = {s.lower() for s in tail_sections}

        missing_sections = [s for s in orig_sections if s.lower() not in tail_sections_lower]
        if missing_sections:
            logger.warning("Tailored resume dropped sections", missing=missing_sections)
            end_doc_idx = tailored.rfind("\\end{document}")
            if end_doc_idx == -1:
                end_doc_idx = len(tailored)
            for sec_name in missing_sections:
                match = re.search(
                    rf"(\\section\{{{re.escape(sec_name)}\}})",
                    original, re.IGNORECASE,
                )
                if not match:
                    continue
                start = match.start()
                next_sec = re.search(r"\\section\{", original[match.end():])
                if next_sec:
                    end = match.end() + next_sec.start()
                else:
                    ed = original.find("\\end{document}", match.end())
                    end = ed if ed != -1 else len(original)
                section_content = original[start:end].rstrip() + "\n\n"
                tailored = tailored[:end_doc_idx] + section_content + tailored[end_doc_idx:]
                end_doc_idx = tailored.rfind("\\end{document}")
                if end_doc_idx == -1:
                    end_doc_idx = len(tailored)

        # ── 3. Splice back missing experience entries ────────────────
        exp_pattern = re.compile(
            r"\\resumeSubheading\s*\{([^}]*)\}\s*\{[^}]*\}\s*\{[^}]*\}\s*\{[^}]*\}"
        )
        orig_companies = {m.group(1).strip().lower() for m in exp_pattern.finditer(original)}
        tail_companies = {m.group(1).strip().lower() for m in exp_pattern.finditer(tailored)}
        missing_exp = orig_companies - tail_companies

        if missing_exp:
            logger.warning("Tailored resume dropped experience entries", missing=list(missing_exp))
            for comp_lower in missing_exp:
                # Find the full entry block in original: \resumeSubheading{...} ... next \resumeSubheading or \resumeSubHeadingListEnd
                for m in exp_pattern.finditer(original):
                    if m.group(1).strip().lower() == comp_lower:
                        start = m.start()
                        rest = original[m.end():]
                        next_entry = re.search(
                            r"\\resumeSubheading\{|\\resumeSubHeadingListEnd",
                            rest,
                        )
                        end = m.end() + next_entry.start() if next_entry else len(original)
                        block = original[start:end]
                        # Insert before \resumeSubHeadingListEnd in the Experience section
                        insert_re = re.search(
                            r"(\\section\{.*?[Ee]xperience.*?\}.*?)(\\resumeSubHeadingListEnd)",
                            tailored,
                            re.DOTALL,
                        )
                        if insert_re:
                            idx = insert_re.start(2)
                            tailored = tailored[:idx] + block + "\n    " + tailored[idx:]
                        break

        # ── 4. Splice back missing project entries ────────────────
        proj_pattern = re.compile(
            r"\\resumeProjectHeading\s*\{.*?\\textbf\{([^}]+)\}.*?\}\s*\{[^}]*\}"
        )
        orig_projects = {m.group(1).strip().lower() for m in proj_pattern.finditer(original)}
        tail_projects = {m.group(1).strip().lower() for m in proj_pattern.finditer(tailored)}
        missing_proj = orig_projects - tail_projects

        if missing_proj:
            logger.warning("Tailored resume dropped project entries", missing=list(missing_proj))
            for proj_lower in missing_proj:
                for m in proj_pattern.finditer(original):
                    if m.group(1).strip().lower() == proj_lower:
                        start = m.start()
                        rest = original[m.end():]
                        next_entry = re.search(
                            r"\\resumeProjectHeading\{|\\resumeSubHeadingListEnd",
                            rest,
                        )
                        end = m.end() + next_entry.start() if next_entry else len(original)
                        block = original[start:end]
                        insert_re = re.search(
                            r"(\\section\{.*?[Pp]roject.*?\}.*?)(\\resumeSubHeadingListEnd)",
                            tailored,
                            re.DOTALL,
                        )
                        if insert_re:
                            idx = insert_re.start(2)
                            tailored = tailored[:idx] + block + "\n    " + tailored[idx:]
                        break

        return tailored

    async def generate_changes_summary(
        self, original: str, tailored: str
    ) -> dict[str, Any]:
        """Compare two resume versions and summarize changes."""
        system = (
            "You are an expert resume reviewer. "
            "Compare the original and tailored resume versions. "
            "Return ONLY valid JSON with these keys: "
            '"changes_summary" (brief description of all changes), '
            '"sections_modified" (list of section names), '
            '"keywords_added" (list of new keywords), '
            '"optimization_score" (float 0.0-1.0 rating the improvement). '
            "Return ONLY valid JSON — no markdown, no commentary."
        )
        prompt = (
            f"ORIGINAL:\n{original[:4000]}\n\n"
            f"TAILORED:\n{tailored[:4000]}"
        )
        try:
            return await self.generate_json(prompt, system=system)
        except Exception as e:
            logger.error("Changes summary failed", error=str(e))
            return {"changes_summary": "AI comparison unavailable",
                    "sections_modified": [], "keywords_added": [], "optimization_score": 0.0}

    async def chat_resume(
        self, resume_latex: str, user_message: str, history: list[dict[str, str]] | None = None
    ) -> dict[str, str]:
        """
        Chat about a resume — user asks for changes, AI returns updated LaTeX + explanation.
        """
        messages = [
            {"role": "system", "content": (
                "You are an expert resume editor. The user will ask you to modify their LaTeX resume. "
                "Respond with a JSON object containing exactly two keys: "
                '"updated_latex" (the full updated LaTeX source) and '
                '"explanation" (a brief explanation of what you changed). '
                "Return ONLY valid JSON — no markdown, no commentary. "
                "If the user's request doesn't require LaTeX changes, set updated_latex to null.\n\n"
                "CRITICAL CONSTRAINTS:\n"
                "- NEVER change company names, job titles, employment dates, or education details.\n"
                "- NEVER add new experience entries or companies that don't exist in the resume.\n"
                "- NEVER fabricate or invent statistics, metrics, or accomplishments.\n"
                "- You may only reword bullet points, reorder sections, and update skills/summary.\n"
                "- Every company and position in the output MUST exist in the input resume.\n\n"
                "LATEX RULES:\n"
                "- Preserve the exact \\documentclass line and \\usepackage declarations.\n"
                "- Ensure all environments are balanced (\\begin{...} / \\end{...}).\n"
                "- Escape special characters: %, $, &, #, _ → \\%, \\$, \\&, \\#, \\_.\n"
                "- Start with \\documentclass and end with \\end{document}."
            )},
            {"role": "user", "content": f"Here is my current resume:\n\n{resume_latex[:6000]}"},
            {"role": "assistant", "content": "I've reviewed your resume. What changes would you like?"},
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        raw = await self.chat(messages)
        parsed = self._parse_json(raw)

        # Compile-verify-retry: ensure chat-edited LaTeX compiles
        if parsed.get("updated_latex"):
            fixed, compiled = await self._ensure_compilable_latex(
                parsed["updated_latex"], context="Resume edited via chat"
            )
            parsed["updated_latex"] = fixed
            parsed["compile_success"] = compiled
            if not compiled:
                parsed["explanation"] = (
                    parsed.get("explanation", "") +
                    " (Warning: LaTeX may still have minor compile issues.)"
                )

        return parsed

    async def scrape_job_from_url(self, html_content: str) -> dict[str, Any]:
        """Extract structured job data from raw HTML."""
        system = (
            "You are a job listing parser. Extract structured data from the HTML of a job posting page. "
            "Return ONLY valid JSON with these keys: "
            '"title" (string), "company" (string), "location" (string or null), '
            '"description" (string — the full job description text), '
            '"requirements" (string or null), '
            '"skills" (list of strings — technologies/skills mentioned), '
            '"experience_required" (string or null — e.g. \"3-5 years\"), '
            '"salary_range" (string or null), "remote_type" (string or null). '
            "Return ONLY valid JSON — no markdown, no commentary."
        )
        # Truncate HTML to fit in context
        prompt = f"Parse this job listing HTML:\n\n{html_content[:10000]}"
        try:
            return await self.generate_json(prompt, system=system)
        except Exception as e:
            logger.error("Job URL parsing failed", error=str(e))
            return {}

    # ── Job Relevance Filtering ──────────────────────────────────

    async def filter_jobs_by_relevance(
        self,
        jobs: list[dict],
        *,
        candidate_yoe: int | None = None,
        candidate_level: str | None = None,
        resume_summary: str | None = None,
        tolerance_years: int = 2,
    ) -> list[int]:
        """
        Use LLM to filter scraped jobs for relevance.

        Returns a list of indices (0-based) of jobs that are suitable.
        Excludes jobs where the required YOE exceeds candidate_yoe + tolerance_years,
        or where the role level is clearly mismatched.
        """
        if not jobs:
            return []

        entries = []
        for i, j in enumerate(jobs):
            title = j.get("title", "Unknown")
            company = j.get("company", "Unknown")
            desc = (j.get("description") or "")[:200]
            entries.append(f"{i}. {title} @ {company} — {desc}")
        jobs_text = "\n".join(entries)

        candidate_info = []
        if candidate_yoe is not None:
            candidate_info.append(f"Years of experience: {candidate_yoe}")
        if candidate_level:
            candidate_info.append(f"Level: {candidate_level}")
        if resume_summary:
            candidate_info.append(f"Resume highlights: {resume_summary[:500]}")
        candidate_text = "\n".join(candidate_info) if candidate_info else "No candidate info provided"

        system = (
            "You are a job relevance filter. Given a candidate's profile and a list of jobs, "
            "determine which jobs are suitable for the candidate.\n\n"
            "FILTER RULES:\n"
            f"- EXCLUDE jobs that require more than {tolerance_years} years beyond the candidate's experience.\n"
            "- EXCLUDE jobs with seniority levels clearly above the candidate "
            "(e.g. a mid-level candidate should not see Principal/Staff/Director roles).\n"
            "- INCLUDE jobs at the candidate's level and one level above.\n"
            "- INCLUDE jobs where the requirements are vague or unspecified.\n"
            "- When in doubt, INCLUDE the job.\n\n"
            "Return ONLY a JSON array of the 0-based indices of suitable jobs.\n"
            "Example: [0, 2, 5, 7]\n"
            "Return ONLY the JSON array — no explanation, no markdown fences."
        )
        prompt = (
            f"CANDIDATE:\n{candidate_text}\n\n"
            f"JOBS:\n{jobs_text}\n\n"
            f"Return the JSON array of suitable job indices."
        )

        try:
            raw = await self.generate(prompt, system=system)
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                raw = "\n".join(lines).strip()
            indices = json.loads(raw)
            if not isinstance(indices, list):
                return list(range(len(jobs)))
            return [int(i) for i in indices if 0 <= int(i) < len(jobs)]
        except Exception as e:
            logger.warning("Job relevance filtering failed, returning all", error=str(e))
            return list(range(len(jobs)))

    # ── Skill Classification ─────────────────────────────────────

    async def classify_skills(self, raw_skills: list[str]) -> dict[str, list[str]]:
        """
        Classify a list of skill strings into fixed categories using LLM.

        Categories: Languages, Frameworks, Databases, Cloud & DevOps, Tools,
                    Architecture & Patterns, Soft Skills, Other.
        """
        system = (
            "You are a technical skill classifier. Classify each skill into EXACTLY ONE of these categories:\n"
            "- Languages (programming/scripting languages: Python, Java, Go, SQL, etc.)\n"
            "- Frameworks (libraries/frameworks: React, Django, Spring Boot, etc.)\n"
            "- Databases (database systems: PostgreSQL, MongoDB, Redis, etc.)\n"
            "- Cloud & DevOps (cloud providers, CI/CD, containers: AWS, Docker, Kubernetes, Terraform, etc.)\n"
            "- Tools (dev tools, IDEs, platforms: Git, Jira, Figma, Postman, etc.)\n"
            "- Architecture & Patterns (design patterns, system design: Microservices, REST API, Event-Driven, etc.)\n"
            "- Soft Skills (non-technical: Leadership, Communication, Agile, Scrum, etc.)\n"
            "- Other (anything that doesn't fit above)\n\n"
            "Return ONLY valid JSON with category names as keys and arrays of skill strings as values. "
            "Every input skill must appear in exactly one category. Do not add skills not in the input."
        )
        skills_str = ", ".join(raw_skills)
        prompt = f"Classify these skills: {skills_str}"
        try:
            result = await self.generate_json(prompt, system=system)
            categories = [
                "Languages", "Frameworks", "Databases", "Cloud & DevOps",
                "Tools", "Architecture & Patterns", "Soft Skills", "Other",
            ]
            classified: dict[str, list[str]] = {}
            for cat in categories:
                for key, val in result.items():
                    if key.lower().replace("_", " ") == cat.lower().replace("_", " "):
                        classified[cat] = val if isinstance(val, list) else [val]
                        break
                else:
                    classified[cat] = []
            return classified
        except Exception as e:
            logger.error("Skill classification failed", error=str(e))
            return {
                "Languages": [], "Frameworks": [], "Databases": [],
                "Cloud & DevOps": [], "Tools": [], "Architecture & Patterns": [],
                "Soft Skills": [], "Other": raw_skills,
            }

    # ── PDF to LaTeX ─────────────────────────────────────────────

    async def pdf_to_latex(self, extracted_text: str) -> str:
        """
        Convert extracted resume text (from PDF) into clean LaTeX source.
        """
        system = (
            "You are an expert LaTeX resume writer. Convert the provided resume text into a clean, "
            "well-structured LaTeX document using the article documentclass. "
            "Preserve ALL content — names, dates, descriptions, skills, education, projects. "
            "Use standard LaTeX resume formatting with sections for: Contact Info, Summary/Objective, "
            "Experience, Education, Skills, Projects (if present), Certifications (if present). "
            "Use \\section{}, \\textbf{}, \\textit{}, itemize/enumerate environments. "
            "Return ONLY the complete LaTeX source code starting with \\documentclass and ending with "
            "\\end{document}. Do NOT wrap in markdown code fences."
        )
        prompt = f"Convert this resume text to LaTeX:\n\n{extracted_text[:12000]}"
        raw = await self.generate(prompt, system=system)
        # Strip markdown fences
        if raw.strip().startswith("```"):
            lines = raw.strip().split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw = "\n".join(lines).strip()

        # Compile-verify-retry
        fixed, compiled = await self._ensure_compilable_latex(
            raw, context="PDF to LaTeX conversion"
        )
        if not compiled:
            logger.warning("PDF-to-LaTeX conversion may have compile issues")
        return fixed

    # ── Recruiter verification ──────────────────────────────────

    async def verify_recruiter_profiles(
        self,
        people: list[dict],
        company: str,
        role_query: str = "recruiter",
    ) -> list[dict]:
        """
        Use LLM to verify which scraped LinkedIn profiles are actually
        recruiters / hiring managers at the target company.

        Returns only the profiles that match.
        """
        if not people:
            return []

        entries = []
        for i, p in enumerate(people):
            entries.append(
                f'{i+1}. Name: {p.get("name", "?")} | '
                f'Headline: {p.get("title", "N/A")} | '
                f'Company: {p.get("company", "N/A")}'
            )
        people_text = "\n".join(entries)

        system = (
            "You are a strict recruiter-verification assistant.\n"
            "Given a list of LinkedIn profiles and a target company, decide which \n"
            "people are ACTUALLY recruiters, talent-acquisition specialists, or \n"
            "hiring managers at that company RIGHT NOW.\n\n"
            "QUALIFYING TITLES (must contain one of these or close synonyms):\n"
            "- Recruiter, Technical Recruiter, Senior Recruiter\n"
            "- Talent Acquisition, Talent Partner\n"
            "- Hiring Manager, Engineering Manager (only if hiring-related)\n"
            "- Staffing, People Operations (recruiting focus)\n"
            "- HR Business Partner (with recruiting duties)\n\n"
            "DISQUALIFYING SIGNALS:\n"
            "- Software Engineer, Product Manager, Designer, Data Scientist, etc.\n"
            "- Vague titles like 'Professional', 'Consultant', 'Advisor' without\n"
            "  explicit recruiting context\n"
            "- Title does not mention the target company or a known subsidiary\n"
            "- 'Former', 'Ex-', 'Previously at' — they must be CURRENT\n\n"
            "Rules:\n"
            "- A person qualifies ONLY if their headline/title clearly indicates a \n"
            "  recruiting, talent acquisition, hiring, staffing, or HR role.\n"
            "- If the headline does not mention the target company, they do NOT qualify.\n"
            "- Return ONLY a JSON array of the qualifying entry numbers (1-based).\n"
            "- If nobody qualifies, return an empty array: []\n"
            "- Return ONLY the JSON array — no explanation, no markdown fences."
        )
        prompt = (
            f"Target company: {company}\n"
            f"Looking for: {role_query}\n\n"
            f"Profiles:\n{people_text}\n\n"
            f"Return the JSON array of qualifying entry numbers."
        )

        try:
            raw = await self.generate(prompt, system=system)
            # Parse the array
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                raw = "\n".join(lines).strip()
            indices = json.loads(raw)
            if not isinstance(indices, list):
                logger.warning("LLM returned non-list for recruiter verification", raw=raw[:200])
                return people  # fall back to returning all

            verified = []
            for idx in indices:
                pos = int(idx) - 1  # convert 1-based to 0-based
                if 0 <= pos < len(people):
                    verified.append(people[pos])
            logger.info(
                "LLM recruiter verification",
                total=len(people),
                verified=len(verified),
                company=company,
            )
            return verified
        except Exception as e:
            logger.warning("LLM recruiter verification failed, returning all", error=str(e))
            return people

    # ── ATS Scoring (direct LLM) ─────────────────────────────────

    async def score_resume_ats(
        self, resume_latex: str, job_description: str
    ) -> dict[str, Any]:
        """
        Score a resume against a job description for ATS compatibility.
        Returns dict with overall_score (0-100), matched/missing keywords, etc.
        """
        system = (
            "You are an ATS (Applicant Tracking System) scoring engine.\n"
            "Score how well the resume matches the job description on a 0-100 scale.\n"
            "Return ONLY valid JSON with these fields:\n"
            '{"overall_score": 0-100, "matched_keywords": [...], "missing_keywords": [...], '
            '"strengths": [...], "weaknesses": [...], "suggestions": [...]}'
        )
        prompt = (
            f"RESUME (LaTeX, first 4000 chars):\n{resume_latex[:4000]}\n\n"
            f"JOB DESCRIPTION (first 3000 chars):\n{job_description[:3000]}\n\n"
            "Score this resume for ATS compatibility."
        )
        try:
            result = await self.generate_json(prompt, system=system)
            score = result.get("overall_score", 0)
            if isinstance(score, float):
                score = int(score * 100) if score <= 1.0 else int(score)
            return {
                "overall_score": min(100, max(0, int(score))),
                "matched_keywords": result.get("matched_keywords", []),
                "missing_keywords": result.get("missing_keywords", []),
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "suggestions": result.get("suggestions", []),
            }
        except Exception as e:
            logger.error("ATS scoring failed", error=str(e))
            return {"overall_score": 0, "matched_keywords": [], "missing_keywords": []}

    # ── Spelling / Grammar Check ─────────────────────────────────

    async def check_spelling_grammar(self, resume_latex: str) -> dict[str, Any]:
        """
        LLM-based spelling and grammar check for resume content.
        Ignores LaTeX commands, proper nouns, names, emails, URLs.
        """
        system = (
            "You are a professional proofreader checking a LaTeX resume for spelling and grammar errors.\n\n"
            "RULES:\n"
            "1. IGNORE LaTeX commands (\\section, \\textbf, \\href, etc.)\n"
            "2. IGNORE proper nouns: company names, product names, technology names\n"
            "3. IGNORE personal names, email addresses, URLs, phone numbers\n"
            "4. IGNORE abbreviations and acronyms (API, SDK, CI/CD, etc.)\n"
            "5. Only flag genuine spelling errors, grammar issues, or punctuation problems\n"
            "6. For each issue, provide the original text, suggested fix, surrounding context, and type\n\n"
            "Return ONLY valid JSON:\n"
            '{"issues": [{"original": "...", "suggested": "...", "context": "...surrounding text...", '
            '"issue_type": "spelling|grammar|punctuation"}], '
            '"corrected_latex": "...full corrected LaTeX if issues found, null if no issues..."}'
        )
        prompt = f"Check this resume for spelling and grammar:\n\n{resume_latex[:8000]}"
        try:
            result = await self.generate_json(prompt, system=system)
            return {
                "issues": result.get("issues", []),
                "corrected_latex": result.get("corrected_latex"),
            }
        except Exception as e:
            logger.error("Spelling check failed", error=str(e))
            return {"issues": [], "corrected_latex": None}
