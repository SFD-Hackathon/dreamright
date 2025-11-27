"""Job management service for async operations."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional


class JobStatus(str, Enum):
    """Job status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Represents an async job."""

    id: str
    type: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    total: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status.value,
            "progress": self.progress,
            "total": self.total,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }


class JobService:
    """Service for managing async jobs."""

    def __init__(self):
        """Initialize the job service."""
        self._jobs: dict[str, Job] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def create_job(self, job_type: str, metadata: Optional[dict] = None) -> Job:
        """Create a new job.

        Args:
            job_type: Type of job (e.g., "story_expansion", "panel_generation")
            metadata: Additional metadata

        Returns:
            Created job
        """
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            type=job_type,
            metadata=metadata or {},
        )
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID.

        Returns:
            Job or None if not found
        """
        return self._jobs.get(job_id)

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        job_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Job], int]:
        """List jobs with optional filtering.

        Returns:
            Tuple of (jobs, total_count)
        """
        jobs = list(self._jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]
        if job_type:
            jobs = [j for j in jobs if j.type == job_type]

        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        total = len(jobs)
        return jobs[offset:offset + limit], total

    async def run_job(
        self,
        job: Job,
        coro: Coroutine,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> Job:
        """Run a job's coroutine and track its status.

        Args:
            job: The job to run
            coro: The coroutine to execute
            on_progress: Optional callback for progress updates

        Returns:
            Updated job
        """
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()

        try:
            result = await coro
            job.status = JobStatus.COMPLETED
            job.result = result
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.error = "Job was cancelled"
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
        finally:
            job.completed_at = datetime.now()

        return job

    def start_job(
        self,
        job: Job,
        coro: Coroutine,
    ) -> asyncio.Task:
        """Start a job in the background.

        Args:
            job: The job to start
            coro: The coroutine to execute

        Returns:
            The asyncio Task
        """
        async def wrapped():
            return await self.run_job(job, coro)

        task = asyncio.create_task(wrapped())
        self._tasks[job.id] = task
        return task

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job.

        Args:
            job_id: Job ID to cancel

        Returns:
            True if cancelled, False if not found or not cancellable
        """
        job = self._jobs.get(job_id)
        if not job:
            return False

        if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
            return False

        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()

        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now()
        return True

    def update_progress(self, job_id: str, progress: int, total: int) -> None:
        """Update job progress.

        Args:
            job_id: Job ID
            progress: Current progress
            total: Total items
        """
        job = self._jobs.get(job_id)
        if job:
            job.progress = progress
            job.total = total

    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """Remove old completed/failed jobs.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of jobs removed
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        to_remove = []

        for job_id, job in self._jobs.items():
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                if job.completed_at and job.completed_at < cutoff:
                    to_remove.append(job_id)

        for job_id in to_remove:
            del self._jobs[job_id]
            self._tasks.pop(job_id, None)

        return len(to_remove)


# Global job service instance
_job_service: Optional[JobService] = None


def get_job_service() -> JobService:
    """Get the global job service instance."""
    global _job_service
    if _job_service is None:
        _job_service = JobService()
    return _job_service
