"""Chapter routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from dreamright_core_schemas import Chapter
from dreamright_services import ChapterService
from dreamright_services.exceptions import DependencyError, NotFoundError
from dreamright_services.job import get_job_service
from dreamright_api.deps import get_project_manager, verify_token
from dreamright_api.schemas import (
    CreateChapterRequest,
    DependencyErrorResponse,
    ErrorDetail,
    ErrorResponse,
    JobResponse,
    MissingDependency,
    PaginatedResponse,
    PaginationMeta,
)

router = APIRouter(prefix="/projects/{project_id}/chapters", tags=["Chapters"])


@router.get(
    "",
    response_model=PaginatedResponse[Chapter],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def list_chapters(
    project_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List all chapters."""
    manager = get_project_manager(project_id)
    service = ChapterService(manager)

    chapters, total = service.list_chapters(limit=limit, offset=offset)

    return PaginatedResponse(
        data=chapters,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + limit < total,
        ),
    )


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": DependencyErrorResponse},
    },
)
async def create_chapter(
    project_id: str,
    request: CreateChapterRequest,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Generate chapter from story beat.

    Chapter N requires Chapter N-1 to exist for story continuity.
    This is an async operation.
    """
    manager = get_project_manager(project_id)
    service = ChapterService(manager)

    # Validate dependencies
    missing = service.validate_dependencies(request.beat_number)
    if missing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "DEPENDENCY_ERROR",
                    "message": f"Cannot generate chapter {request.beat_number}: dependencies not met",
                },
                "missing_dependencies": missing,
            },
        )

    # Create job
    job_service = get_job_service()
    job = job_service.create_job(
        "chapter_generation",
        metadata={
            "project_id": project_id,
            "beat_number": request.beat_number,
            "panels_per_scene": request.panels_per_scene,
        },
    )

    # Start async generation
    async def generate():
        chapter = await service.generate_chapter(
            beat_number=request.beat_number,
            panels_per_scene=request.panels_per_scene,
        )
        return {
            "chapter_id": chapter.id,
            "chapter_number": chapter.number,
            "title": chapter.title,
            "scene_count": len(chapter.scenes),
            "panel_count": sum(len(s.panels) for s in chapter.scenes),
        }

    job_service.start_job(job, generate())

    return JobResponse(
        job_id=job.id,
        type=job.type,
        status=job.status.value,
        created_at=job.created_at,
        metadata=job.metadata,
    )


@router.get(
    "/{chapter_id}",
    response_model=Chapter,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_chapter(
    project_id: str,
    chapter_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Get chapter details."""
    manager = get_project_manager(project_id)
    service = ChapterService(manager)

    try:
        return service.get_chapter(chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Chapter '{chapter_id}' not found")


@router.delete(
    "/{chapter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_chapter(
    project_id: str,
    chapter_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Delete chapter."""
    manager = get_project_manager(project_id)
    service = ChapterService(manager)

    if not service.delete_chapter(chapter_id):
        raise HTTPException(status_code=404, detail=f"Chapter '{chapter_id}' not found")
