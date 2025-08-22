"""
app/routers/projects_router.py
Endpoints dealing primarily with search, create, and update for now.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
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


async def get_user_by_email(user, db):
    """Helper function to fetch user by email from the database.
    Raises HTTPException if user is not found"""
    userstmt = select(Employee).filter(Employee.email == user["email"])
    user_rtn = (await db.execute(userstmt)).scalar_one_or_none()
    if user_rtn is None:
        er_msg = f"Unable to match user with email {user['email']}."
        logger.error(er_msg)
        raise HTTPException(404, er_msg)
    return user_rtn


#This needs to be before the fetch_visible_projects function as it can be mistaken
# for /{project_id} if it is not defined first.
@router.get(
    "/visible",
    summary="Fetch list of visible project records.",
    description="""Fetch for a list of visible project records to user up to list_limit value (default 100).""",
    response_model=List[ProjectRead]
)
async def fetch_visible_projects(
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Records to skip"),
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
    user_rtn = await get_user_by_email(user, db)

    if user["role"] == "user":
        logger.info("Only showing projects the user email is assigned to.")
        projstmt = (
            select(Project)
            .join(Assignment, Assignment.project_id == Project.id)
            .where(Assignment.employee_id == user_rtn.id)
            .order_by(Project.code)
            .offset(offset)
            .limit(limit)
        )
    else:
        logger.info("Only projects with clearance are equal or less than the user (looked up by email) meets clearance requirements for.")
        projstmt = (
            select(Project)
            .filter(Project.min_clearance <= user_rtn.clearance_level)
            .order_by(Project.code)
            .offset(offset)
            .limit(limit)
        )

    project_rtn = (await db.scalars(projstmt)).all()
    logger.info(f"Project rtn length: {len(project_rtn)}")

    if len(project_rtn) > 0:
        pydantic_rtn = [ProjectRead.model_validate(record) for record in project_rtn]
        logger.info(f"{len(project_rtn)} projects visible to user (via email) found.")
        return pydantic_rtn
    else:
        er_msg = "No projects visible to user (looked up via email) found."
        logger.error(er_msg)
        raise HTTPException(404, er_msg)


# This is okay here since this is the last GET endpoint in the file.
@router.get(
    "/{project_id}",
    summary="Fetch a project record",
    description="""Fetch a single project record by project record id.""",
    response_model=ProjectRead
)
async def fetch_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user = Depends(require_role("admin", "manager", "user")),
):
    """
    admin role can see all. manager role can only see to their clearance level
    user role cannot see via this function
    """
    await check_headers(user)
    user_rtn = await get_user_by_email(user, db)

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
        er_msg = f"Project id: {project_id} NOT found."
        logger.error(er_msg)
        raise HTTPException(404, er_msg)


@router.post(
    "/create",
    summary="Create project record.",
    description="""Create a new project record.""",
    response_model=ProjectRead
)
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


@router.post(
    "/update",
    summary="Update project record.",
    description="""Update a new project record by project id.""",
    response_model=ProjectRead
)
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
        er_msg = f"Project Id: {payload.id} not found."
        logger.error(er_msg)
        raise HTTPException(404, er_msg)
