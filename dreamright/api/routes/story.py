"""Story routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from ...services import StoryService
from ...services.exceptions import NotFoundError
from ...services.job import get_job_service
from ..deps import get_project_manager, verify_token
from ..schemas import (
    CreateStoryRequest,
    ErrorResponse,
    JobResponse,
    StoryResponse,
    story_to_response,
)

router = APIRouter(prefix="/projects/{project_id}/story", tags=["Story"])


@router.get(
    "",
    response_model=StoryResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_story(
    project_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Get story details."""
    manager = get_project_manager(project_id)
    service = StoryService(manager)

    try:
        story = service.get_story()
        return story_to_response(story)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Story not expanded yet")


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def create_story(
    project_id: str,
    request: CreateStoryRequest,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Create/expand story from prompt.

    This is an async operation. Returns 202 with a job ID to poll for completion.
    """
    manager = get_project_manager(project_id)

    # Check if story already exists
    if manager.project.story:
        raise HTTPException(
            status_code=409,
            detail="Story already exists. Use PUT to replace.",
        )

    # Create job
    job_service = get_job_service()
    job = job_service.create_job(
        "story_expansion",
        metadata={
            "project_id": project_id,
            "prompt": request.prompt[:100] + "..." if len(request.prompt) > 100 else request.prompt,
        },
    )

    # Start async expansion
    service = StoryService(manager)

    async def expand():
        story, characters, locations = await service.expand(
            prompt=request.prompt,
            genre=request.genre,
            tone=request.tone,
            episodes=request.episodes,
        )
        return {
            "story_id": story.id,
            "title": story.title,
            "character_count": len(characters),
            "location_count": len(locations),
        }

    job_service.start_job(job, expand())

    return JobResponse(
        job_id=job.id,
        type=job.type,
        status=job.status.value,
        created_at=job.created_at,
        metadata=job.metadata,
    )


@router.put(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def replace_story(
    project_id: str,
    request: CreateStoryRequest,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Replace/re-expand story.

    This is an async operation.
    """
    manager = get_project_manager(project_id)

    # Create job
    job_service = get_job_service()
    job = job_service.create_job(
        "story_expansion",
        metadata={
            "project_id": project_id,
            "prompt": request.prompt[:100] + "..." if len(request.prompt) > 100 else request.prompt,
            "replace": True,
        },
    )

    # Start async expansion
    service = StoryService(manager)

    async def expand():
        story, characters, locations = await service.expand(
            prompt=request.prompt,
            genre=request.genre,
            tone=request.tone,
            episodes=request.episodes,
        )
        return {
            "story_id": story.id,
            "title": story.title,
            "character_count": len(characters),
            "location_count": len(locations),
        }

    job_service.start_job(job, expand())

    return JobResponse(
        job_id=job.id,
        type=job.type,
        status=job.status.value,
        created_at=job.created_at,
        metadata=job.metadata,
    )
