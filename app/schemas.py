"""
Request/Response models for create/list operations.
Use separate schemas for inbound vs outbound (e.g., EmployeeCreate vs EmployeeRead
"""
from typing import List
from pydantic import BaseModel


class EmployeeCreate(BaseModel):
    email: str  # TODO: don't forget function overlay
    full_name: str
    clearance_level: int

    class Config:
        from_attributes = True


class EmployeeUpdate(EmployeeCreate):
    id: int


class EmployeeRead(EmployeeUpdate):
    pass


class ProjectCreate(BaseModel):
    code: str
    title: str
    min_clearance: int

    class Config:
        from_attributes = True


class ProjectUpdate(ProjectCreate):
    id: int


class ProjectRead(ProjectUpdate):
    pass


class ProjectReadList(BaseModel):
    project: List[ProjectRead]


class AssignmentCreate(BaseModel):
    employee_email: str
    project_code: str
    role: str 

    class Config:
        from_attributes = True


class AssignmentUpdate(BaseModel):
    id: int
    employee_id: int
    project_id: int
    role: str


class AssignmentRead(AssignmentUpdate):
    pass
