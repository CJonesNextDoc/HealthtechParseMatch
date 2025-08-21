"""
Request/Response models for create/list operations.
Use separate schemas for inbound vs outbound (e.g., EmployeeCreate vs EmployeeRead
"""
from typing import List
from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    code: str
    title: str
    min_clearance: int

    model_config = ConfigDict(
        from_attributes=True
    )


class ProjectUpdate(ProjectCreate):
    id: int


class ProjectRead(ProjectUpdate):
    pass


class ProjectReadList(BaseModel):
    project: List[ProjectRead]
