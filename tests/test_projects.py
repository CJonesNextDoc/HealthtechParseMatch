"""
on /projects/visible endpoint

user with insufficient clearance (sees none)
user with sufficient clearance but not assigned (sees none)
user with sufficient clearance and assigned (sees those)
manager with sufficient clearance (sees all permitted)
admin with high clearance (sees all)
"""

import pytest

@pytest.mark.asyncio
async def test_projects_get(client, manager_headers):
    resp = await client.get("/projects/1", headers=manager_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 1

@pytest.mark.asyncio
async def test_projects_get_low_clearance(client, manager_headers_low_clearance):
    resp = await client.get("/projects/1", headers=manager_headers_low_clearance)
    assert resp.status_code == 404
    data = resp.json()
    assert "id" not in data

@pytest.mark.asyncio
async def test_projects_get_admin(client, admin_headers):
    resp = await client.get("/projects/1", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["id"] >= 1

@pytest.mark.asyncio
async def test_projects_get_user(client, user_headers_low_clearance):
    resp = await client.get("/projects/1", headers=user_headers_low_clearance)
    assert resp.status_code == 404
    data = resp.json()
    assert "id" not in data


@pytest.mark.asyncio
async def test_projects_get_list_visible_none(client, user_headers_low_clearance):
    # Method 1: Using params argument (recommended)
    resp = await client.get(
        "/projects/visible",
        params={"limit": 10, "offset": 0},
        headers=user_headers_low_clearance
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_projects_get_list_visible(client, user_headers_mid_clearance):
    resp = await client.get("/projects/visible?limit=5&offset=0", headers=user_headers_mid_clearance)
    assert resp.status_code == 200
