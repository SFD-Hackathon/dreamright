"""Job routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from dreamright_services.job import JobStatus, get_job_service
from dreamright_api.deps import verify_token
from dreamright_api.schemas import (
    ErrorResponse,
    JobStatusResponse,
    PaginatedResponse,
    PaginationMeta,
)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "",
    response_model=PaginatedResponse[JobStatusResponse],
    responses={401: {"model": ErrorResponse}},
)
async def list_jobs(
    token: Annotated[Optional[str], Depends(verify_token)],
    status_filter: Optional[JobStatus] = Query(None, alias="status"),
    job_type: Optional[str] = Query(None, alias="type"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List all jobs."""
    job_service = get_job_service()
    jobs, total = job_service.list_jobs(
        status=status_filter,
        job_type=job_type,
        limit=limit,
        offset=offset,
    )

    return PaginatedResponse(
        data=[
            JobStatusResponse(
                id=j.id,
                type=j.type,
                status=j.status.value,
                progress=j.progress,
                total=j.total,
                result=j.result,
                error=j.error,
                created_at=j.created_at,
                started_at=j.started_at,
                completed_at=j.completed_at,
                metadata=j.metadata,
            )
            for j in jobs
        ],
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + limit < total,
        ),
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_job(
    job_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Get job status."""
    job_service = get_job_service()
    job = job_service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return JobStatusResponse(
        id=job.id,
        type=job.type,
        status=job.status.value,
        progress=job.progress,
        total=job.total,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        metadata=job.metadata,
    )


@router.delete(
    "/{job_id}",
    response_model=JobStatusResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def cancel_job(
    job_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Cancel a running job."""
    job_service = get_job_service()
    job = job_service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
        raise HTTPException(
            status_code=409,
            detail=f"Job cannot be cancelled (status: {job.status.value})",
        )

    job_service.cancel_job(job_id)

    # Refresh job state
    job = job_service.get_job(job_id)

    return JobStatusResponse(
        id=job.id,
        type=job.type,
        status=job.status.value,
        progress=job.progress,
        total=job.total,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        metadata=job.metadata,
    )
