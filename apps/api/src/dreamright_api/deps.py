"""API dependencies."""

from pathlib import Path
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status

from dreamright_services import (
    CharacterService,
    ChapterService,
    JobService,
    LocationService,
    PanelService,
    ProjectService,
    StoryService,
)
from dreamright_services.exceptions import NotFoundError
from dreamright_services.job import get_job_service
from dreamright_storage import ProjectManager


# Configuration
class Settings:
    """API settings."""

    projects_dir: Path = Path("./projects")
    api_keys: set[str] = set()  # Empty = no auth required
    require_auth: bool = False


settings = Settings()


def get_settings() -> Settings:
    """Get API settings."""
    return settings


# Authentication
async def verify_token(
    authorization: Annotated[Optional[str], Header()] = None,
    settings: Settings = Depends(get_settings),
) -> Optional[str]:
    """Verify bearer token if auth is required.

    Returns:
        The token if valid, None if auth not required
    """
    if not settings.require_auth:
        return None

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    if settings.api_keys and token not in settings.api_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return token


# Project loading
def get_project_path(project_id: str) -> Path:
    """Get project path from ID.

    Validates that the path stays within the projects directory
    to prevent path traversal attacks.

    Raises:
        HTTPException: If project_id would escape projects_dir
    """
    # Resolve the path and ensure it stays within projects_dir
    projects_dir = settings.projects_dir.resolve()
    project_path = (projects_dir / project_id).resolve()

    try:
        project_path.relative_to(projects_dir)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project ID",
        )

    return project_path


def get_project_manager(project_id: str) -> ProjectManager:
    """Get project manager for a project ID.

    Raises:
        HTTPException: If project not found
    """
    path = get_project_path(project_id)

    try:
        service = ProjectService(path)
        return service.load()
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )


# Service factories
def get_project_service() -> ProjectService:
    """Get project service for listing/creating projects."""
    return ProjectService(settings.projects_dir)


def get_story_service(project_id: str) -> StoryService:
    """Get story service for a project."""
    manager = get_project_manager(project_id)
    return StoryService(manager)


def get_character_service(project_id: str) -> CharacterService:
    """Get character service for a project."""
    manager = get_project_manager(project_id)
    return CharacterService(manager)


def get_location_service(project_id: str) -> LocationService:
    """Get location service for a project."""
    manager = get_project_manager(project_id)
    return LocationService(manager)


def get_chapter_service(project_id: str) -> ChapterService:
    """Get chapter service for a project."""
    manager = get_project_manager(project_id)
    return ChapterService(manager)


def get_panel_service(project_id: str) -> PanelService:
    """Get panel service for a project."""
    manager = get_project_manager(project_id)
    return PanelService(manager)


def get_jobs() -> JobService:
    """Get the job service."""
    return get_job_service()
