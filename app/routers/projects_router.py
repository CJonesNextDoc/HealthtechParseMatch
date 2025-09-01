"""
app/routers/projects_router.py
Endpoints dealing primarily with search, create, and update for now.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import check_headers, require_role
from app.db.db import get_db
from app.models.assignment import Assignment
from app.models.employee import Employee
from app.models.project import Project
from app.schemas.project_schema import ProjectCreate, ProjectRead, ProjectUpdate
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["Projects"])


async def get_user_by_email(user, db):
    """Helper function to fetch user by email from the database."""
    userstmt = select(Employee).filter(Employee.email == user["email"])
    user_rtn = (await db.execute(userstmt)).scalar_one_or_none()
    if user_rtn is None:
        logger.error("User not found", extra={"email": user["email"], "action": "user_lookup_failed"})
        raise HTTPException(404, f"Unable to match user with email {user['email']}.")
    return user_rtn


# This needs to be before the fetch_visible_projects function as it can be mistaken
# for /{project_id} if it is not defined first.
@router.get(
    "/visible",
    summary="Fetch list of visible project records.",
    description="""Fetch for a list of visible project records to user up to list_limit value (default 100).""",
    response_model=List[ProjectRead],
)
async def fetch_visible_projects(
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Records to skip"),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("manager", "admin", "user")),
):
    logger.info("Fetching visible projects", extra={"limit": limit, "offset": offset, "action": "fetch_list"})
    await check_headers(user)
    user_rtn = await get_user_by_email(user, db)

    if user["role"] == "user":
        logger.info("Fetching user assigned projects", extra={"user_id": user_rtn.id, "action": "fetch_list_user"})
        projstmt = (
            select(Project)
            .join(Assignment, Assignment.project_id == Project.id)
            .where(Assignment.employee_id == user_rtn.id)
            .order_by(Project.code)
            .offset(offset)
            .limit(limit)
        )
    else:
        logger.info(
            "Fetching clearance-based projects",
            extra={"clearance_level": user_rtn.clearance_level, "action": "fetch_list_clearance"},
        )
        projstmt = (
            select(Project)
            .filter(Project.min_clearance <= user_rtn.clearance_level)
            .order_by(Project.code)
            .offset(offset)
            .limit(limit)
        )

    project_rtn = (await db.scalars(projstmt)).all()

    if len(project_rtn) > 0:
        pydantic_rtn = [ProjectRead.model_validate(record) for record in project_rtn]
        logger.info("Projects found", extra={"count": len(project_rtn), "action": "fetch_list_success"})
        return pydantic_rtn

    logger.error("No visible projects", extra={"user_id": user_rtn.id, "action": "fetch_list_empty"})
    raise HTTPException(404, f"No projects visible to user {user_rtn.id} found.")


# This is okay here since this is the last GET endpoint in the file.
@router.get(
    "/{project_id}",
    summary="Fetch a project record",
    description="""Fetch a single project record by project record id.""",
    response_model=ProjectRead,
)
async def fetch_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin", "manager", "user")),
):
    logger.info("Fetching project", extra={"project_id": project_id, "action": "fetch"})
    await check_headers(user)
    user_rtn = await get_user_by_email(user, db)

    if user["role"] == "admin":
        logger.info("Processing admin request", extra={"role": "admin", "project_id": project_id, "action": "fetch_admin"})
        projstmt = select(Project).filter(Project.id == project_id)
    elif user["role"] == "manager":
        logger.info(
            "Processing manager request",
            extra={
                "role": "manager",
                "project_id": project_id,
                "clearance_level": user_rtn.clearance_level,
                "action": "fetch_manager",
            },
        )
        projstmt = select(Project).filter(and_(Project.id == project_id, Project.min_clearance <= user_rtn.clearance_level))
    else:
        logger.info(
            "Processing user request",
            extra={
                "role": "user",
                "project_id": project_id,
                "user_id": user_rtn.id,
                "clearance_level": user_rtn.clearance_level,
                "action": "fetch_user",
            },
        )
        # role is "user", only returns those he is assigned to
        projstmt = (
            select(Project)
            .join(Assignment, and_(Assignment.project_id == Project.id, Assignment.employee_id == user_rtn.id))
            .filter(
                and_(
                    Project.id == project_id,
                    Project.min_clearance <= user_rtn.clearance_level,
                )
            )
        )

    project_rtn = (await db.execute(projstmt)).scalar_one_or_none()

    if project_rtn is not None:
        logger.info("Project found", extra={"project_id": project_id, "action": "fetch_success"})
        return project_rtn

    logger.error("Project not found", extra={"project_id": project_id, "action": "fetch_failed"})
    raise HTTPException(404, f"Project id {project_id} NOT found.")


@router.post(
    "/create", summary="Create project record.", description="""Create a new project record.""", response_model=ProjectRead
)
async def create_project(
    payload: ProjectCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("vendor_app")),
):
    logger.info("Creating project", extra={"code": payload.code, "action": "create"})
    await check_headers(user)

    new_project = Project(**payload.model_dump())
    projstmt = select(Project).filter(Project.code == payload.code)
    project_rtn = (await db.execute(projstmt)).scalar_one_or_none()

    if project_rtn is None:
        logger.info("Creating new project", extra={"code": payload.code, "action": "create_new"})
        db.add(new_project)
        await db.commit()
        await db.refresh(new_project)
        logger.info("Project created", extra={"code": payload.code, "id": new_project.id, "action": "create_success"})
        response.status_code = 201
        return new_project
    else:
        logger.info("Project exists", extra={"code": payload.code, "id": project_rtn.id, "action": "create_skipped"})
        return project_rtn


@router.post(
    "/update",
    summary="Update project record.",
    description="""Update a new project record by project id.""",
    response_model=ProjectRead,
)
async def update_project(
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("vendor_app")),
):
    await check_headers(user)
    logger.info("Updating project", extra={"project_id": payload.id, "code": payload.code, "action": "update"})

    projstmt = select(Project).filter(Project.id == payload.id)
    project_rtn = (await db.execute(projstmt)).scalar_one_or_none()

    if project_rtn is not None:
        logger.info(
            "Project found for update", extra={"project_id": payload.id, "code": payload.code, "action": "update_found"}
        )

        # Apply updates from payload onto the existing ORM object
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(project_rtn, key, value)

        db.add(project_rtn)
        await db.commit()
        await db.refresh(project_rtn)

        logger.info("Project updated", extra={"project_id": payload.id, "code": payload.code, "action": "update_success"})
        return project_rtn

    logger.error("Project not found", extra={"project_id": payload.id, "code": payload.code, "action": "update_failed"})
    raise HTTPException(404, f"Project id {payload.id} not found.")
