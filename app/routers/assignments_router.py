import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.assignment_schema import AssignmentCreate, AssignmentRead
from app.core.auth import check_headers, require_role
from app.db.db import get_db
from app.models.assignment import Assignment
from app.models.employee import Employee
from app.models.project import Project

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assignments", tags=["Assignments"])


@router.get(
    "/{assignment_id}",
    summary="Fetch an assignment record",
    description="""Fetch a single assignment record by assignment record id.""",
     response_model=AssignmentRead
)
async def fetch_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    user = Depends(require_role("manager", "admin", "user")),
):
    await check_headers(user)

    assignstmt = select(Assignment).filter(Assignment.id == assignment_id)
    assignment_rtn = (await db.execute(assignstmt)).scalar_one_or_none()
    
    if assignment_rtn is not None:
        # This ensures the employee email is unique
        logger.info(f"Assignment id: {assignment_id} found.")
        return assignment_rtn
    else:
        er_msg = f"Assignment id: {assignment_id} NOT found."
        logger.error(er_msg)
        raise HTTPException(404, er_msg)


@router.post(
    "/upsert",
    summary="Insert or update an assignment record",
    description="""Insert or update a single assignment record by searching for a matching
    project_code + employee_email assignment record. If a match is found, update with values
    in the payload. If no match found, insert the record.""",
    response_model=AssignmentRead
)
async def create_update_assignment(
    payload: AssignmentCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user = Depends(require_role("admin")),
):
    """
    Updates or Inserts payload values. If there is a match on project_code + employee_email
    in Assignments table, it will update the existing record with the role value
    """
    await check_headers(user)

    # get project_id from project code
    projstmt = select(Project).filter(Project.code == payload.project_code)
    project_rtn = (await db.execute(projstmt)).scalar_one_or_none()

    # get employee_id from employee email
    emplstmt = select(Employee).filter(Employee.email == payload.employee_email)
    employee_rtn = (await db.execute(emplstmt)).scalar_one_or_none()

    if project_rtn is None:
        er_msg = "Unable to find project by supplied code."
        logger.error(er_msg)
        raise HTTPException(404, er_msg)

    if  employee_rtn is None:
        er_msg = "Unable to find employee by supplied email."
        logger.error(er_msg)
        raise HTTPException(404, er_msg)

    assignstmt = select(Assignment).filter(and_(Assignment.project_id == project_rtn.id, Assignment.employee_id == employee_rtn.id))
    assignment_rtn = (await db.execute(assignstmt)).scalar_one_or_none()
    
    if assignment_rtn is None:
        new_assignment = Assignment(project_id = project_rtn.id, employee_id = employee_rtn.id, role = payload.role)
        # This ensures the assignment candidate is unique
        db.add(new_assignment)
        await db.commit()
        await db.refresh(new_assignment)
        logger.info(f"Assignment id: {new_assignment.id} added.")
        response.status_code = 201
        return new_assignment
    else:
        for key, value in payload.model_dump(exclude_unset=True).items():
            # payload model may have fields from related tables, ignore these
            # on the setattr below. Only want to set those attributes that
            # exist in the assignment table model.
            if key in assignment_rtn.__dict__:
                setattr(assignment_rtn, key, value)

        # db.add in this case has the record id in assignment_rtn, so an update not an insert occurs
        db.add(assignment_rtn)
        await db.commit()
        await db.refresh(assignment_rtn)
        logger.info(f"Assignment code: {assignment_rtn.id} already exists. Updated record.")

        return assignment_rtn

