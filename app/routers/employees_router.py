from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import check_headers, require_role
from app.db.db import get_db
from app.models.employee import Employee
from app.schemas.employee_schema import EmployeeCreate, EmployeeRead, EmployeeUpdate
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get(
    "/{employee_id}",
    summary="Fetch an employee",
    description="Returns a single employee record by id.",
    response_model=EmployeeRead,
    responses={
        404: {"description": "Employee not found"},
        403: {"description": "Forbidden: Role not authorized."},  # Raised by require_role
    },
)
async def fetch_employee(
    employee_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "manager", "user")),
):
    logger.info("Fetching employee", extra={"employee_id": employee_id, "action": "fetch"})
    await check_headers(user)

    emplstmt = select(Employee).filter(Employee.id == employee_id)
    employee_rtn = (await db.execute(emplstmt)).scalar_one_or_none()

    if employee_rtn is not None:
        response.status_code = status.HTTP_200_OK
        logger.info(
            "Employee found", extra={"employee_id": employee_id, "email": employee_rtn.email, "action": "fetch_success"}
        )
        return employee_rtn

    logger.error("Employee not found", extra={"employee_id": employee_id, "action": "fetch_failed"})
    raise HTTPException(404, f"Employee {employee_id} not found")


@router.post(
    "/create",
    summary="Create an employee",
    description="""
    Create a single employee record by unique email address.
    If email address is found, that record id is returned but no fields are updated.""",
    response_model=EmployeeRead,
    responses={
        403: {"description": "Forbidden: Role not authorized."},  # Raised by require_role
    },
)
async def create_employee(
    payload: EmployeeCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "manager")),
):
    logger.info("Creating employee", extra={"email": payload.email, "action": "create"})
    await check_headers(user)

    emplstmt = select(Employee).filter(Employee.email == payload.email)
    employee_rtn = (await db.execute(emplstmt)).scalar_one_or_none()

    if employee_rtn is None:
        new_employee = Employee(**payload.model_dump())
        db.add(new_employee)
        await db.commit()
        await db.refresh(new_employee)

        logger.info(
            "Employee created",
            extra={"employee_id": new_employee.id, "email": new_employee.email, "action": "create_success"},
        )
        response.status_code = status.HTTP_201_CREATED
        return new_employee

    logger.info(
        "Employee exists", extra={"employee_id": employee_rtn.id, "email": employee_rtn.email, "action": "create_skipped"}
    )
    return employee_rtn


@router.post(
    "/update",
    summary="Update an employee record",
    description="""Update a single employee record by employee record id.""",
    response_model=EmployeeRead,
    responses={
        403: {"description": "Forbidden: Role not authorized."},  # Raised by require_role
        404: {"description": "Employee id not found."},
    },
)
async def update_employee(
    payload: EmployeeUpdate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "manager", "user")),
):
    logger.info("Updating employee", extra={"employee_id": payload.id, "action": "update"})
    await check_headers(user)

    emplstmt = select(Employee).filter(Employee.id == payload.id)
    employee_rtn = (await db.execute(emplstmt)).scalar_one_or_none()

    if employee_rtn is not None:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(employee_rtn, key, value)
        db.add(employee_rtn)
        await db.commit()
        await db.refresh(employee_rtn)

        logger.info(
            "Employee updated", extra={"employee_id": payload.id, "email": employee_rtn.email, "action": "update_success"}
        )
        response.status_code = status.HTTP_200_OK
        return employee_rtn

    logger.error("Employee not found", extra={"employee_id": payload.id, "action": "update_failed"})
    raise HTTPException(404, f"Employee {payload.id} not found")
