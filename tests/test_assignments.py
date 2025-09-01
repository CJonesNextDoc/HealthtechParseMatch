import pytest


@pytest.mark.asyncio
async def test_create_assignment_two(client, admin_headers):
    json_payload = {
        "project_code": "PRJ-BLUE",
        "employee_email": "tom.smith@example.com",
        "role": "lead",
    }
    resp = await client.post("/assignments/upsert", headers=admin_headers, json=json_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] >= 1
