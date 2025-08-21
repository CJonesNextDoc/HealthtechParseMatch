"""
Request/Response models for create/list operations.
"""
from pydantic import BaseModel, ConfigDict


class EmployeeCreate(BaseModel):
    email: str  # TODO: don't forget function overlay
    full_name: str
    clearance_level: int

    model_config = ConfigDict(
        from_attributes=True
    )


class EmployeeUpdate(EmployeeCreate):
    id: int


class EmployeeRead(EmployeeUpdate):
    pass
