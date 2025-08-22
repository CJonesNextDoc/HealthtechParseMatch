"""
Request/Response models for create/list operations.
"""
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmployeeCreate(BaseModel):
    email: EmailStr = Field(..., description="Work email of the employee")
    full_name: str = Field(..., min_length=1, max_length=100)
    clearance_level: int = Field(..., ge=1, le=5)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "email": "jane@example.com",
                "full_name": "Jane Doe",
                "clearance_level": 3,
            }
        },
    )


class EmployeeUpdate(EmployeeCreate):
    id: int

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 6,
                "email": "jane@example.com",
                "full_name": "Jane Doe",
                "clearance_level": 3,
            }
        },
    )


class EmployeeRead(EmployeeUpdate):
    pass
