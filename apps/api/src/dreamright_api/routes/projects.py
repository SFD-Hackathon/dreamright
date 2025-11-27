"""Project routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from dreamright_core_schemas import ProjectFormat, ProjectStatus
from dreamright_services import ProjectService
from dreamright_services.exceptions import NotFoundError, ValidationError
from dreamright_api.deps import get_project_path, get_project_service, get_settings, verify_token
from dreamright_api.schemas import (
    CreateProjectRequest,
    ErrorResponse,
    PaginatedResponse,
    PaginationMeta,
    ProjectResponse,
    ProjectStatusResponse,
    UpdateProjectRequest,
    project_to_response,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get(
    "",
    response_model=PaginatedResponse[ProjectResponse],
    responses={401: {"model": ErrorResponse}},
)
async def list_projects(
    token: Annotated[Optional[str], Depends(verify_token)],
    status_filter: Optional[ProjectStatus] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List all projects."""
    settings = get_settings()
    projects_dir = settings.projects_dir

    if not projects_dir.exists():
        return PaginatedResponse(
            data=[],
            pagination=PaginationMeta(total=0, limit=limit, offset=offset, has_more=False),
        )

    # Load all projects
    projects = []
    for path in projects_dir.iterdir():
        if path.is_dir() and (path / "project.json").exists():
            try:
                service = ProjectService(path)
                project = service.get()
                if status_filter is None or project.status == status_filter:
                    projects.append(project_to_response(project))
            except Exception:
                continue

    # Sort by updated_at descending
    projects.sort(key=lambda p: p.updated_at, reverse=True)

    total = len(projects)
    paginated = projects[offset:offset + limit]

    return PaginatedResponse(
        data=paginated,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + limit < total,
        ),
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
async def create_project(
    request: CreateProjectRequest,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Create a new project."""
    settings = get_settings()
    projects_dir = settings.projects_dir
    projects_dir.mkdir(parents=True, exist_ok=True)

    # Generate project ID from name
    from dreamright_storage import slugify
    project_id = slugify(request.name)
    project_path = projects_dir / project_id

    try:
        service = ProjectService(project_path)
        project = service.create(request.name, request.format)
        return project_to_response(project)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_project(
    project_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Get project details."""
    path = get_project_path(project_id)

    try:
        service = ProjectService(path)
        project = service.get()
        return project_to_response(project)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Update project."""
    path = get_project_path(project_id)

    try:
        service = ProjectService(path)
        service.load()
        project = service.update(
            name=request.name,
            status=request.status,
        )
        return project_to_response(project)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_project(
    project_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Delete project."""
    path = get_project_path(project_id)

    service = ProjectService(path)
    if not service.delete(path):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get(
    "/{project_id}/status",
    response_model=ProjectStatusResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_project_status(
    project_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Get project generation status."""
    path = get_project_path(project_id)

    try:
        service = ProjectService(path)
        service.load()
        status_dict = service.get_status()
        return ProjectStatusResponse(**status_dict)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
