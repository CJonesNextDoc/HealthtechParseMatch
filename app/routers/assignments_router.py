from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.assignment_schema import AssignmentCreate, AssignmentRead
from app.core.auth import check_headers, require_role
from app.db.db import get_db
from app.models.assignment import Assignment
from app.models.employee import Employee
from app.models.project import Project
from app.utils.logger import get_logger

logger = get_logger(__name__)

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
    logger.info("Fetching assignment", extra={
        "assignment_id": assignment_id,
        "action": "fetch"
    })
    await check_headers(user)

    assignstmt = select(Assignment).filter(Assignment.id == assignment_id)
    assignment_rtn = (await db.execute(assignstmt)).scalar_one_or_none()
    
    if assignment_rtn is not None:
        logger.info("Assignment found", extra={
            "assignment_id": assignment_id,
            "project_id": assignment_rtn.project_id,
            "employee_id": assignment_rtn.employee_id,
            "action": "fetch_success"
        })
        return assignment_rtn

    logger.error("Assignment not found", extra={
        "assignment_id": assignment_id,
        "action": "fetch_failed"
    })
    raise HTTPException(404, f"Assignment id: {assignment_id} NOT found.")


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
    logger.info("Processing assignment upsert", extra={
        "project_code": payload.project_code,
        "employee_email": payload.employee_email,
        "action": "upsert"
    })
    await check_headers(user)

    # get project_id from project code
    projstmt = select(Project).filter(Project.code == payload.project_code)
    project_rtn = (await db.execute(projstmt)).scalar_one_or_none()

    if project_rtn is None:
        logger.error("Project not found", extra={
            "project_code": payload.project_code,
            "action": "upsert_failed"
        })
        raise HTTPException(404, f"Unable to find project by supplied code {payload.project_code}.")

    # get employee_id from employee email
    emplstmt = select(Employee).filter(Employee.email == payload.employee_email)
    employee_rtn = (await db.execute(emplstmt)).scalar_one_or_none()

    if employee_rtn is None:
        logger.error("Employee not found", extra={
            "employee_email": payload.employee_email,
            "action": "upsert_failed"
        })
        raise HTTPException(404, "Unable to find employee by supplied email.")

    assignstmt = select(Assignment).filter(and_(
        Assignment.project_id == project_rtn.id, 
        Assignment.employee_id == employee_rtn.id
    ))
    assignment_rtn = (await db.execute(assignstmt)).scalar_one_or_none()
    
    if assignment_rtn is None:
        logger.info("Creating new assignment", extra={
            "project_id": project_rtn.id,
            "employee_id": employee_rtn.id,
            "action": "create"
        })
        new_assignment = Assignment(
            project_id=project_rtn.id,
            employee_id=employee_rtn.id,
            role=payload.role
        )
        db.add(new_assignment)
        await db.commit()
        await db.refresh(new_assignment)
        
        logger.info("Assignment created", extra={
            "assignment_id": new_assignment.id,
            "project_id": project_rtn.id,
            "employee_id": employee_rtn.id,
            "action": "create_success"
        })
        response.status_code = 201
        return new_assignment

    logger.info("Updating existing assignment", extra={
        "assignment_id": assignment_rtn.id,
        "project_id": project_rtn.id,
        "employee_id": employee_rtn.id,
        "action": "update"
    })
    
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key in assignment_rtn.__dict__:
            setattr(assignment_rtn, key, value)

    db.add(assignment_rtn)
    await db.commit()
    await db.refresh(assignment_rtn)
    
    logger.info("Assignment updated", extra={
        "assignment_id": assignment_rtn.id,
        "project_id": project_rtn.id,
        "employee_id": employee_rtn.id,
        "action": "update_success"
    })
    return assignment_rtn

