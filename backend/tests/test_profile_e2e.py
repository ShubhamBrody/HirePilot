"""
Tests for Profile endpoints — Work Experience & Education CRUD.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_experiences_empty(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/profile/work-experience", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["experiences"] == []


@pytest.mark.asyncio
async def test_create_and_list_experience(client: AsyncClient, auth_headers: dict):
    payload = {
        "company": "Acme Corp",
        "role": "Software Engineer",
        "location": "Remote",
        "description": "Built things",
        "start_date": "2023-01-01",
        "is_current": True,
    }
    resp = await client.post("/api/v1/profile/work-experience", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["company"] == "Acme Corp"
    assert data["is_current"] is True
    exp_id = data["id"]

    resp2 = await client.get("/api/v1/profile/work-experience", headers=auth_headers)
    assert resp2.status_code == 200
    assert len(resp2.json()["experiences"]) == 1
    assert resp2.json()["experiences"][0]["id"] == exp_id


@pytest.mark.asyncio
async def test_update_experience(client: AsyncClient, auth_headers: dict):
    create = await client.post(
        "/api/v1/profile/work-experience",
        json={"company": "Old", "role": "Dev"},
        headers=auth_headers,
    )
    exp_id = create.json()["id"]

    resp = await client.put(
        f"/api/v1/profile/work-experience/{exp_id}",
        json={"company": "New Corp", "role": "Senior Dev"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["company"] == "New Corp"


@pytest.mark.asyncio
async def test_delete_experience(client: AsyncClient, auth_headers: dict):
    create = await client.post(
        "/api/v1/profile/work-experience",
        json={"company": "ToDelete", "role": "Temp"},
        headers=auth_headers,
    )
    exp_id = create.json()["id"]

    resp = await client.delete(f"/api/v1/profile/work-experience/{exp_id}", headers=auth_headers)
    assert resp.status_code == 204

    listing = await client.get("/api/v1/profile/work-experience", headers=auth_headers)
    assert len(listing.json()["experiences"]) == 0


@pytest.mark.asyncio
async def test_education_choices(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/profile/education/choices", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "degree_choices" in data
    assert "field_of_study_choices" in data
    assert len(data["degree_choices"]) > 0


@pytest.mark.asyncio
async def test_create_and_list_education(client: AsyncClient, auth_headers: dict):
    payload = {
        "degree": "BTech",
        "field_of_study": "Computer Science",
        "institution": "IIT Delhi",
        "start_year": 2018,
        "end_year": 2022,
        "gpa": 8.5,
        "gpa_scale": 10.0,
    }
    resp = await client.post("/api/v1/profile/education", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["degree"] == "BTech"
    assert resp.json()["institution"] == "IIT Delhi"

    listing = await client.get("/api/v1/profile/education", headers=auth_headers)
    assert len(listing.json()["educations"]) == 1


@pytest.mark.asyncio
async def test_bulk_save_experiences(client: AsyncClient, auth_headers: dict):
    exps = [
        {"company": "A", "role": "Dev", "sort_order": 0},
        {"company": "B", "role": "Lead", "sort_order": 1},
    ]
    resp = await client.put("/api/v1/profile/work-experience", json=exps, headers=auth_headers)
    assert resp.status_code == 200

    listing = await client.get("/api/v1/profile/work-experience", headers=auth_headers)
    assert len(listing.json()["experiences"]) == 2
