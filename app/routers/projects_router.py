

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.project_schema import ProjectCreate, ProjectRead, ProjectUpdate
from app.core.auth import check_headers, require_role
from app.db.db import get_db
from app.models.assignment import Assignment
from app.models.employee import Employee
from app.models.project import Project

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/{project_id}", response_model=ProjectRead)
async def fetch_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user = Depends(require_role("admin", "manager", "user")),
):
    """
    admin role can see all. manager role can only see to their clearance level
    user role cannot see via this function
    """
    if "email" not in user:
        ex_msg = "User clearance cannot be checked."
        logger.exception(ex_msg)
        raise HTTPException(403, ex_msg)
    
    userstmt = select(Employee).filter(Employee.email == user["email"])
    user_rtn = (await db.execute(userstmt)).scalar_one_or_none()

    if user["role"] == "admin":
        projstmt = select(Project).filter(Project.id == project_id)
    elif user["role"] == "manager":
        projstmt = select(Project).filter(and_(Project.id == project_id, Project.min_clearance <= user_rtn.clearance_level))
    else:
        # role is "user", only returns those he is assigned to
        projstmt = select(Project).join(
            Assignment, and_(Assignment.project_id == Project.id, Assignment.employee_id == user_rtn.id)
        ).filter(
            and_(
                Project.id == project_id,
                Project.min_clearance <= user_rtn.clearance_level,
            )
        )

    project_rtn = (await db.execute(projstmt)).scalar_one_or_none()
    
    if project_rtn is not None:
        # This ensures the employee email is unique
        logger.info(f"Project id: {project_id} found.")
        return project_rtn
    else:
        ex_msg = f"Project id: {project_id} NOT found."
        logger.exception(ex_msg)
        raise HTTPException(404, ex_msg)


@router.get("/visible/{list_limit}", response_model=List[ProjectRead])
async def fetch_visible_projects(
    list_limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user = Depends(require_role("manager", "admin", "user")),
):
    """
    GET /projects/visible — list projects visible to caller:
    Caller sends headers:
    X-Role: admin|manager|user
    X-Clearance: <int>

    Visibility rule:
    [1] Must have X-Clearance >= project.min_clearance
    [2] If X-Role == "user", only show projects the caller is assigned to (simulate caller by X-User-Email header, required for user role).
    [3] If X-Role in {"manager","admin"}, show all projects that pass the clearance filter.
    """    
    await check_headers(user)
    
    userstmt = select(Employee).filter(Employee.email == user["email"])
    user_rtn = (await db.execute(userstmt)).scalar_one_or_none()
    logger.info(f"User email: {user_rtn.email}")

    if user["role"] == "user":
        logger.info(f"Only showing projects that user email: {user['email']} is assigned to.")
        projstmt = select(Project).join(
            Assignment, Assignment.project_id == Project.id
        ).where(
            Assignment.employee_id == user_rtn.id
        ).order_by(Project.code).limit(list_limit)
    else:
        logger.info(f"Only showing projects that are equal or less than: {user['email']} meets clearance requirements for.")
        projstmt = select(Project).filter(Project.min_clearance <= user_rtn.clearance_level).order_by(Project.code).limit(list_limit)

    project_rtn = (await db.scalars(projstmt)).all()
    logger.info(f"Project rtn length: {len(project_rtn)}")

    if len(project_rtn) > 0:
        pydantic_rtn = [ProjectRead.model_validate(record) for record in project_rtn]
        logger.info(pydantic_rtn)
        logger.info(f"{len(project_rtn)} projects visible to user: {user['email']} found.")
        return pydantic_rtn
    else:
        ex_msg = f"No projects visible to user: {user['email']} found."
        logger.exception(ex_msg)
        raise HTTPException(404, ex_msg)


@router.post("/create", response_model=ProjectRead)
async def create_project(
    payload: ProjectCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user = Depends(require_role("vendor_app")),
):
    """
    Endpoints return proper status codes: 201 on create, 200 on reads/lists, 400 on bad headers.
    """
    await check_headers(user)

    new_project = Project(**payload.model_dump())
    projstmt = select(Project).filter(Project.code == payload.code)
    project_rtn = (await db.execute(projstmt)).scalar_one_or_none()
    
    if project_rtn is None:
        # This ensures the employee email is unique
        db.add(new_project)
        await db.commit()
        await db.refresh(new_project)
        logger.info(f"Project code: {payload.code} added.")
        response.status_code = 201
        return new_project
    else:
        logger.info(f"Project code: {payload.code} already exists.")
        return project_rtn


@router.post("/update", response_model=ProjectRead)
async def update_project(
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    user = Depends(require_role("vendor_app")),
):
    await check_headers(user)

    projstmt = select(Project).filter(Project.id == payload.id)
    project_rtn = (await db.execute(projstmt)).scalar_one_or_none()
    
    if project_rtn is not None:

        # Apply updates from payload onto the existing ORM object
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(project_rtn, key, value)

        db.add(project_rtn)
        await db.commit()
        await db.refresh(project_rtn)
        logger.info(f"Project ID: {payload.id} updated.")
        return project_rtn
    else:
        ex_msg = f"Project Id: {payload.id} not found."
        logger.exception(ex_msg)
        raise HTTPException(404, ex_msg)
