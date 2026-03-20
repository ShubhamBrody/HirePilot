"""
Tests — LLM Job Relevance Filtering

Tests `LLMService.filter_jobs_by_relevance()` with mocked LLM responses
to verify that overqualified-job filtering works correctly.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm_service import LLMService

pytestmark = pytest.mark.asyncio


SAMPLE_JOBS = [
    {"title": "Junior Python Developer", "company": "StartupCo", "description": "0-2 years experience"},
    {"title": "Senior Staff Engineer", "company": "BigCorp", "description": "10+ years, lead teams of 50+"},
    {"title": "Backend Engineer", "company": "MidCo", "description": "3-5 years Python experience"},
    {"title": "Principal Architect", "company": "Enterprise", "description": "15+ years, CTO track"},
]


class TestFilterJobsByRelevance:
    """Unit tests for LLM-based job relevance filtering."""

    async def test_filters_out_overqualified_jobs(self):
        """LLM returns only matching indices → overqualified jobs excluded."""
        llm = LLMService()

        # Mock LLM to return indices 0 and 2 as suitable (junior + mid-level)
        mock_response = json.dumps([0, 2])
        with patch.object(llm, "generate", new_callable=AsyncMock, return_value=mock_response):
            result = await llm.filter_jobs_by_relevance(
                SAMPLE_JOBS,
                candidate_yoe=3,
                candidate_level="mid",
                resume_summary="Backend engineer with 3 years Python experience",
            )

        assert 0 in result
        assert 2 in result
        assert 1 not in result  # Senior Staff excluded
        assert 3 not in result  # Principal excluded

    async def test_returns_all_indices_when_llm_fails(self):
        """If LLM call raises, all indices are returned (fail-open)."""
        llm = LLMService()

        with patch.object(llm, "generate", new_callable=AsyncMock, side_effect=Exception("LLM down")):
            result = await llm.filter_jobs_by_relevance(
                SAMPLE_JOBS, candidate_yoe=3,
            )

        assert result == [0, 1, 2, 3]

    async def test_returns_all_indices_when_llm_returns_invalid_json(self):
        """If LLM returns garbage, all indices are returned."""
        llm = LLMService()

        with patch.object(llm, "generate", new_callable=AsyncMock, return_value="not json at all"):
            result = await llm.filter_jobs_by_relevance(
                SAMPLE_JOBS, candidate_yoe=3,
            )

        assert result == [0, 1, 2, 3]

    async def test_empty_jobs_returns_empty(self):
        """No jobs in → no indices out, no LLM call."""
        llm = LLMService()

        with patch.object(llm, "generate", new_callable=AsyncMock) as mock_gen:
            result = await llm.filter_jobs_by_relevance([], candidate_yoe=3)

        assert result == []
        mock_gen.assert_not_called()

    async def test_out_of_range_indices_ignored(self):
        """LLM returns indices outside valid range → they are ignored."""
        llm = LLMService()

        mock_response = json.dumps([0, 2, 99, -1])
        with patch.object(llm, "generate", new_callable=AsyncMock, return_value=mock_response):
            result = await llm.filter_jobs_by_relevance(
                SAMPLE_JOBS, candidate_yoe=3,
            )

        assert 0 in result
        assert 2 in result
        assert 99 not in result
        assert -1 not in result
