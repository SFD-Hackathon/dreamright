"""Character routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...models import Character
from ...services import CharacterService
from ...services.exceptions import AssetExistsError, NotFoundError
from ...services.job import get_job_service
from ..deps import get_project_manager, verify_token
from ..schemas import (
    CharacterAssetResponse,
    CreateCharacterAssetRequest,
    CreateCharacterRequest,
    ErrorResponse,
    JobResponse,
    PaginatedResponse,
    PaginationMeta,
    UpdateCharacterRequest,
)

router = APIRouter(prefix="/projects/{project_id}/characters", tags=["Characters"])


@router.get(
    "",
    response_model=PaginatedResponse[Character],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def list_characters(
    project_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List all characters."""
    manager = get_project_manager(project_id)
    service = CharacterService(manager)

    characters, total = service.list_characters(limit=limit, offset=offset)

    return PaginatedResponse(
        data=characters,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + limit < total,
        ),
    )


@router.post(
    "",
    response_model=Character,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def create_character(
    project_id: str,
    request: CreateCharacterRequest,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Create a character."""
    manager = get_project_manager(project_id)
    service = CharacterService(manager)

    return service.create_character(
        name=request.name,
        role=request.role,
        age=request.age,
        description=request.description,
        visual_tags=request.visual_tags,
    )


@router.get(
    "/{character_id}",
    response_model=Character,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_character(
    project_id: str,
    character_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Get character details."""
    manager = get_project_manager(project_id)
    service = CharacterService(manager)

    try:
        return service.get_character(character_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")


@router.patch(
    "/{character_id}",
    response_model=Character,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_character(
    project_id: str,
    character_id: str,
    request: UpdateCharacterRequest,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Update character."""
    manager = get_project_manager(project_id)
    service = CharacterService(manager)

    try:
        return service.update_character(
            character_id=character_id,
            name=request.name,
            role=request.role,
            age=request.age,
            description=request.description,
            visual_tags=request.visual_tags,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")


@router.delete(
    "/{character_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_character(
    project_id: str,
    character_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Delete character."""
    manager = get_project_manager(project_id)
    service = CharacterService(manager)

    if not service.delete_character(character_id):
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")


@router.get(
    "/{character_id}/assets",
    response_model=CharacterAssetResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_character_assets(
    project_id: str,
    character_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Get character assets metadata."""
    manager = get_project_manager(project_id)
    service = CharacterService(manager)

    try:
        assets = service.get_assets(character_id)
        return CharacterAssetResponse(**assets)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")


@router.post(
    "/{character_id}/assets",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def create_character_asset(
    project_id: str,
    character_id: str,
    request: CreateCharacterAssetRequest = CreateCharacterAssetRequest(),
    token: Annotated[Optional[str], Depends(verify_token)] = None,
):
    """Generate character assets (portrait + full-body three-view sheet).

    Two-step generation process:
    1. Generates portrait first (establishes face/features)
    2. Uses portrait as reference to generate three-view character sheet

    This is an async operation.
    """
    manager = get_project_manager(project_id)
    service = CharacterService(manager)

    # Check character exists
    try:
        char = service.get_character(character_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")

    # Check if asset exists
    if not request.overwrite:
        existing = service.check_asset_exists(character_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Portrait already exists at {existing}. Use overwrite=true to replace.",
            )

    # Create job
    job_service = get_job_service()
    job = job_service.create_job(
        "character_asset_generation",
        metadata={
            "project_id": project_id,
            "character_id": character_id,
            "character_name": char.name,
            "style": request.style,
        },
    )

    # Start async generation
    async def generate():
        return await service.generate_asset(
            character_id=character_id,
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


@router.put(
    "/{character_id}/assets",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def replace_character_asset(
    project_id: str,
    character_id: str,
    request: CreateCharacterAssetRequest = CreateCharacterAssetRequest(),
    token: Annotated[Optional[str], Depends(verify_token)] = None,
):
    """Regenerate character assets (portrait + three-view sheet, force overwrite)."""
    manager = get_project_manager(project_id)
    service = CharacterService(manager)

    # Check character exists
    try:
        char = service.get_character(character_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")

    # Create job
    job_service = get_job_service()
    job = job_service.create_job(
        "character_asset_generation",
        metadata={
            "project_id": project_id,
            "character_id": character_id,
            "character_name": char.name,
            "style": request.style,
            "overwrite": True,
        },
    )

    # Start async generation
    async def generate():
        return await service.generate_asset(
            character_id=character_id,
            style=request.style,
            overwrite=True,
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
    "/assets",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def create_all_character_assets(
    project_id: str,
    request: CreateCharacterAssetRequest = CreateCharacterAssetRequest(),
    token: Annotated[Optional[str], Depends(verify_token)] = None,
):
    """Generate all missing character assets (portrait + three-view sheet).

    Batch operation for all characters without assets.
    Each character gets a portrait first, then a three-view sheet using the portrait as reference.
    """
    manager = get_project_manager(project_id)
    service = CharacterService(manager)

    # Create job
    job_service = get_job_service()
    job = job_service.create_job(
        "batch_character_asset_generation",
        metadata={
            "project_id": project_id,
            "style": request.style,
            "overwrite": request.overwrite,
        },
    )

    # Start async generation
    async def generate():
        return await service.generate_all_assets(
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
