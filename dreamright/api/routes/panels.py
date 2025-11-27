"""Panel routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from ...models import Panel
from ...services import PanelService
from ...services.exceptions import DependencyError, NotFoundError
from ...services.job import get_job_service
from ..deps import get_project_manager, verify_token
from ..schemas import (
    CreatePanelsRequest,
    CreateScenePanelsRequest,
    DependencyErrorResponse,
    ErrorResponse,
    JobResponse,
    PaginatedResponse,
    PaginationMeta,
    PanelGenerationResult,
)

router = APIRouter(prefix="/projects/{project_id}/chapters/{chapter_number}", tags=["Panels"])


@router.get(
    "/panels",
    response_model=PaginatedResponse[Panel],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def list_panels(
    project_id: str,
    chapter_number: int = Path(..., ge=1, description="Chapter number"),
    token: Annotated[Optional[str], Depends(verify_token)] = None,
    scene_number: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List panels for a chapter."""
    manager = get_project_manager(project_id)
    service = PanelService(manager)

    try:
        service.get_chapter(chapter_number)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")

    panels, total = service.list_panels(
        chapter_number=chapter_number,
        scene_number=scene_number,
        limit=limit,
        offset=offset,
    )

    return PaginatedResponse(
        data=panels,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + limit < total,
        ),
    )


@router.post(
    "/panels",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": DependencyErrorResponse},
    },
)
async def create_panels(
    project_id: str,
    chapter_number: int = Path(..., ge=1, description="Chapter number"),
    request: CreatePanelsRequest = CreatePanelsRequest(),
    token: Annotated[Optional[str], Depends(verify_token)] = None,
):
    """Generate panels for chapter.

    Dependencies:
    - All characters in panels must have portrait assets
    - All locations in scenes must have reference assets
    - Chapter N-1 must exist for continuity

    This is an async operation.
    """
    manager = get_project_manager(project_id)
    service = PanelService(manager)

    try:
        service.get_chapter(chapter_number)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")

    # Validate dependencies
    missing = service.validate_dependencies(chapter_number)
    if missing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "DEPENDENCY_ERROR",
                    "message": f"Cannot generate panels for chapter {chapter_number}: dependencies not met",
                },
                "missing_dependencies": missing,
            },
        )

    # Create job
    job_service = get_job_service()
    job = job_service.create_job(
        "panel_generation",
        metadata={
            "project_id": project_id,
            "chapter_number": chapter_number,
            "style": request.style,
        },
    )

    # Start async generation
    async def generate():
        return await service.generate_panels(
            chapter_number=chapter_number,
            style=request.style,
            overwrite=request.overwrite,
        )

    job_service.start_job(job, generate())

    return JobResponse(
        job_id=job.id,
        type=job.type,
        status=job.status.value,
        created_at=job.created_at,
        metadata=job.metadata,
    )


@router.post(
    "/scenes/{scene_number}/panels",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": DependencyErrorResponse},
    },
)
async def create_scene_panels(
    project_id: str,
    scene_number: int,
    chapter_number: int = Path(..., ge=1, description="Chapter number"),
    request: CreateScenePanelsRequest = CreateScenePanelsRequest(),
    token: Annotated[Optional[str], Depends(verify_token)] = None,
):
    """Generate panels for a specific scene.

    This is an async operation.
    """
    manager = get_project_manager(project_id)
    service = PanelService(manager)

    try:
        service.get_chapter(chapter_number)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")

    # Validate dependencies
    missing = service.validate_dependencies(chapter_number, scene_number)
    if missing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "DEPENDENCY_ERROR",
                    "message": f"Cannot generate panels for scene {scene_number}: dependencies not met",
                },
                "missing_dependencies": missing,
            },
        )

    # Create job
    job_service = get_job_service()
    job = job_service.create_job(
        "scene_panel_generation",
        metadata={
            "project_id": project_id,
            "chapter_number": chapter_number,
            "scene_number": scene_number,
            "style": request.style,
        },
    )

    # Start async generation
    async def generate():
        return await service.generate_panels(
            chapter_number=chapter_number,
            scene_number=scene_number,
            style=request.style,
            overwrite=request.overwrite,
        )

    job_service.start_job(job, generate())

    return JobResponse(
        job_id=job.id,
        type=job.type,
        status=job.status.value,
        created_at=job.created_at,
        metadata=job.metadata,
    )
