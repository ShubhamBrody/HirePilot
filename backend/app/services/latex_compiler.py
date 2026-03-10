"""
LaTeX Compiler Service

Compiles LaTeX source to PDF using pdflatex.
Handles compilation errors, timeouts, and artifact cleanup.
"""

import asyncio
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class LatexCompilerService:
    """
    Compiles LaTeX source code to PDF.

    Uses pdflatex with two passes for proper reference resolution.
    Implements timeout protection and temporary file cleanup.
    """

    def __init__(self) -> None:
        self.compiler_path = settings.latex_compiler_path
        self.timeout = settings.latex_compile_timeout

    async def compile(self, latex_source: str) -> dict[str, Any]:
        """
        Compile LaTeX source to PDF.

        Returns dict with:
        - success: bool
        - pdf_data: bytes | None (the compiled PDF)
        - errors: list of error strings
        - warnings: list of warning strings
        - log: full compilation log
        """
        work_dir = Path(tempfile.mkdtemp(prefix="hirepilot_latex_"))
        tex_file = work_dir / "resume.tex"
        pdf_file = work_dir / "resume.pdf"
        log_file = work_dir / "resume.log"

        result: dict[str, Any] = {
            "success": False,
            "pdf_data": None,
            "errors": [],
            "warnings": [],
            "log": "",
        }

        try:
            # Write LaTeX source to temp file
            tex_file.write_text(latex_source, encoding="utf-8")

            # Run pdflatex twice (for references/TOC)
            for pass_num in range(2):
                try:
                    process = await asyncio.create_subprocess_exec(
                        self.compiler_path,
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        "-output-directory", str(work_dir),
                        str(tex_file),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(work_dir),
                    )
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=self.timeout
                    )

                    if process.returncode != 0 and pass_num == 1:
                        # Only fail on second pass errors
                        error_output = stderr.decode("utf-8", errors="replace")
                        result["errors"].append(f"pdflatex exited with code {process.returncode}")
                        if error_output:
                            result["errors"].append(error_output[:2000])

                except asyncio.TimeoutError:
                    result["errors"].append(
                        f"Compilation timed out after {self.timeout}s"
                    )
                    return result

            # Read the log file for warnings
            if log_file.exists():
                log_content = log_file.read_text(encoding="utf-8", errors="replace")
                result["log"] = log_content

                # Extract warnings
                for line in log_content.split("\n"):
                    if "Warning" in line:
                        result["warnings"].append(line.strip())

            # Check if PDF was generated
            if pdf_file.exists():
                result["pdf_data"] = pdf_file.read_bytes()
                result["success"] = True
                logger.info(
                    "LaTeX compilation successful",
                    pdf_size=len(result["pdf_data"]),
                )
            else:
                result["errors"].append("PDF file was not generated")
                # Try to extract error from log
                if result["log"]:
                    error_lines = [
                        line for line in result["log"].split("\n")
                        if line.startswith("!")
                    ]
                    result["errors"].extend(error_lines[:5])

        except Exception as e:
            logger.error("LaTeX compilation error", error=str(e))
            result["errors"].append(str(e))

        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(work_dir)
            except Exception:
                pass

        return result

    async def validate_latex(self, latex_source: str) -> dict[str, Any]:
        """
        Validate LaTeX syntax without full compilation.
        Quick check for common errors.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Basic syntax checks
        if "\\documentclass" not in latex_source:
            errors.append("Missing \\documentclass declaration")

        if "\\begin{document}" not in latex_source:
            errors.append("Missing \\begin{document}")

        if "\\end{document}" not in latex_source:
            errors.append("Missing \\end{document}")

        # Check balanced braces
        open_braces = latex_source.count("{")
        close_braces = latex_source.count("}")
        if open_braces != close_braces:
            warnings.append(
                f"Unbalanced braces: {open_braces} opening, {close_braces} closing"
            )

        # Check balanced begin/end environments
        begins = latex_source.count("\\begin{")
        ends = latex_source.count("\\end{")
        if begins != ends:
            warnings.append(
                f"Unbalanced environments: {begins} \\begin, {ends} \\end"
            )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }
