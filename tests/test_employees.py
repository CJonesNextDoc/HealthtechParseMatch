import random

import pytest


@pytest.mark.asyncio
async def test_employees_get(client, manager_headers):
    resp = await client.get("/employees/1", headers=manager_headers)  # Changed from /2 to /1
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 1


@pytest.mark.asyncio
async def test_employees_create(client, manager_headers):
    num = random.randint(1000, 10_000_000)
    json_payload = {"email": f"tom.smith{num}@emaildomain.com", "full_name": f"Tom Smith {num}", "clearance_level": 2}
    resp = await client.post("/employees/create", headers=manager_headers, json=json_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] >= 4  # This should be 2 since we have one initial record


@pytest.mark.asyncio
async def test_employees_get_forbidden(client, vendor_headers):
    resp = await client.get("/employees/1", headers=vendor_headers)
    assert resp.status_code == 403
    data = resp.json()
    assert "id" not in data


@pytest.mark.asyncio
async def test_employees_get_missing(client, manager_headers):
    resp = await client.get("/employees/12121212", headers=manager_headers)
    assert resp.status_code == 404
    data = resp.json()
    assert "id" not in data
