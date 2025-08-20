import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import EmployeeCreate, EmployeeRead, EmployeeUpdate
from app.core.auth import check_headers, require_role
from app.db import get_db
from app.models import Employee

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get("/{employee_id}", response_model=EmployeeRead)
async def fetch_employee(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    user = Depends(require_role("vendor_app")),
):
    await check_headers(user)

    emplstmt = select(Employee).filter(Employee.id == employee_id)
    employee_rtn = (await db.execute(emplstmt)).scalar_one_or_none()
    
    if employee_rtn is not None:
        # This ensures the employee email is unique
        logger.info(f"Employee id: {employee_id} found.")
        return employee_rtn
    else:
        ex_msg = f"Employee id: {employee_id} NOT found."
        logger.exception(ex_msg)
        raise HTTPException(404, ex_msg)


@router.post("/create", response_model=EmployeeRead)
async def create_employee(
    payload: EmployeeCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user = Depends(require_role("vendor_app")),
):
    await check_headers(user)

    new_employee = Employee(**payload.model_dump())
    emplstmt = select(Employee).filter(Employee.email == payload.email)
    employee_rtn = (await db.execute(emplstmt)).scalar_one_or_none()
    
    if employee_rtn is None:
        # This ensures the employee email is unique
        db.add(new_employee)
        await db.commit()
        await db.refresh(new_employee)
        logger.info(f"Employee email: {payload.email} added.")
        response.status_code = 201
        return new_employee
    else:
        logger.info(f"Employee email: {payload.email} already exists.")
        return employee_rtn


@router.post("/update", response_model=EmployeeRead)
async def update_employee(
    payload: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    user = Depends(require_role("vendor_app")),
):
    await check_headers(user)

    emplstmt = select(Employee).filter(Employee.id == payload.id)
    employee_rtn = (await db.execute(emplstmt)).scalar_one_or_none()
    
    if employee_rtn is not None:

        # Apply updates from payload onto the existing ORM object
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(employee_rtn, key, value)

        db.add(employee_rtn)
        await db.commit()
        await db.refresh(employee_rtn)
        logger.info(f"Employee ID: {payload.id} updated.")
        return employee_rtn
    else:
        ex_msg = f"Employee Id: {payload.id} not found."
        logger.exception(ex_msg)
        raise HTTPException(404, ex_msg)
