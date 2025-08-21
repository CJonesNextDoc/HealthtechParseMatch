"""
Request/Response models for create/list operations.
"""
from pydantic import BaseModel, ConfigDict


class AssignmentCreate(BaseModel):
    employee_email: str
    project_code: str
    role: str 

    model_config = ConfigDict(
        from_attributes=True
    )


class AssignmentUpdate(BaseModel):
    id: int
    employee_id: int
    project_id: int
    role: str


class AssignmentRead(AssignmentUpdate):
    pass
