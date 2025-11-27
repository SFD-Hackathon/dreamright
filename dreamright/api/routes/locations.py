"""Location routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...models import Location
from ...services import LocationService
from ...services.exceptions import NotFoundError
from ...services.job import get_job_service
from ..deps import get_project_manager, verify_token
from ..schemas import (
    CreateLocationAssetRequest,
    CreateLocationRequest,
    ErrorResponse,
    JobResponse,
    LocationAssetResponse,
    PaginatedResponse,
    PaginationMeta,
    UpdateLocationRequest,
)

router = APIRouter(prefix="/projects/{project_id}/locations", tags=["Locations"])


@router.get(
    "",
    response_model=PaginatedResponse[Location],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def list_locations(
    project_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List all locations."""
    manager = get_project_manager(project_id)
    service = LocationService(manager)

    locations, total = service.list_locations(limit=limit, offset=offset)

    return PaginatedResponse(
        data=locations,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + limit < total,
        ),
    )


@router.post(
    "",
    response_model=Location,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def create_location(
    project_id: str,
    request: CreateLocationRequest,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Create a location."""
    manager = get_project_manager(project_id)
    service = LocationService(manager)

    return service.create_location(
        name=request.name,
        type=request.type,
        description=request.description,
        visual_tags=request.visual_tags,
    )


@router.get(
    "/{location_id}",
    response_model=Location,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_location(
    project_id: str,
    location_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Get location details."""
    manager = get_project_manager(project_id)
    service = LocationService(manager)

    try:
        return service.get_location(location_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Location '{location_id}' not found")


@router.patch(
    "/{location_id}",
    response_model=Location,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_location(
    project_id: str,
    location_id: str,
    request: UpdateLocationRequest,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Update location."""
    manager = get_project_manager(project_id)
    service = LocationService(manager)

    try:
        return service.update_location(
            location_id=location_id,
            name=request.name,
            type=request.type,
            description=request.description,
            visual_tags=request.visual_tags,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Location '{location_id}' not found")


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_location(
    project_id: str,
    location_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Delete location."""
    manager = get_project_manager(project_id)
    service = LocationService(manager)

    if not service.delete_location(location_id):
        raise HTTPException(status_code=404, detail=f"Location '{location_id}' not found")


@router.get(
    "/{location_id}/assets",
    response_model=LocationAssetResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_location_assets(
    project_id: str,
    location_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Get location assets metadata."""
    manager = get_project_manager(project_id)
    service = LocationService(manager)

    try:
        assets = service.get_assets(location_id)
        return LocationAssetResponse(**assets)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Location '{location_id}' not found")


@router.post(
    "/{location_id}/assets",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def create_location_asset(
    project_id: str,
    location_id: str,
    request: CreateLocationAssetRequest = CreateLocationAssetRequest(),
    token: Annotated[Optional[str], Depends(verify_token)] = None,
):
    """Generate location reference.

    This is an async operation.
    """
    manager = get_project_manager(project_id)
    service = LocationService(manager)

    # Check location exists
    try:
        loc = service.get_location(location_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Location '{location_id}' not found")

    # Check if asset exists
    if not request.overwrite:
        existing = service.check_asset_exists(location_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Reference already exists at {existing}. Use overwrite=true to replace.",
            )

    # Create job
    job_service = get_job_service()
    job = job_service.create_job(
        "location_asset_generation",
        metadata={
            "project_id": project_id,
            "location_id": location_id,
            "location_name": loc.name,
            "style": request.style,
        },
    )

    # Start async generation
    async def generate():
        return await service.generate_asset(
            location_id=location_id,
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
    "/{location_id}/assets",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def replace_location_asset(
    project_id: str,
    location_id: str,
    request: CreateLocationAssetRequest = CreateLocationAssetRequest(),
    token: Annotated[Optional[str], Depends(verify_token)] = None,
):
    """Regenerate location reference (force overwrite)."""
    manager = get_project_manager(project_id)
    service = LocationService(manager)

    # Check location exists
    try:
        loc = service.get_location(location_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Location '{location_id}' not found")

    # Create job
    job_service = get_job_service()
    job = job_service.create_job(
        "location_asset_generation",
        metadata={
            "project_id": project_id,
            "location_id": location_id,
            "location_name": loc.name,
            "style": request.style,
            "overwrite": True,
        },
    )

    # Start async generation
    async def generate():
        return await service.generate_asset(
            location_id=location_id,
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
async def create_all_location_assets(
    project_id: str,
    request: CreateLocationAssetRequest = CreateLocationAssetRequest(),
    token: Annotated[Optional[str], Depends(verify_token)] = None,
):
    """Generate all missing location assets.

    Batch operation for all locations without references.
    """
    manager = get_project_manager(project_id)
    service = LocationService(manager)

    # Create job
    job_service = get_job_service()
    job = job_service.create_job(
        "batch_location_asset_generation",
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
