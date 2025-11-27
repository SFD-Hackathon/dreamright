"""API request/response schemas."""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

from ..models import (
    CameraAngle,
    Character,
    CharacterDescription,
    CharacterRole,
    Chapter,
    DialogueType,
    Genre,
    Location,
    LocationType,
    Panel,
    Project,
    ProjectFormat,
    ProjectStatus,
    Scene,
    ShotType,
    Story,
    Tone,
)

T = TypeVar("T")


# Pagination
class PaginationMeta(BaseModel):
    """Pagination metadata."""

    total: int
    limit: int
    offset: int
    has_more: bool


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    data: list[T]
    pagination: PaginationMeta


# Error responses
class ErrorDetail(BaseModel):
    """Error detail."""

    code: str
    message: str
    field: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response."""

    error: ErrorDetail


class MissingDependency(BaseModel):
    """Missing dependency detail."""

    type: str
    message: str
    resolution: Optional[str] = None


class DependencyErrorResponse(BaseModel):
    """Dependency error response."""

    error: ErrorDetail
    missing_dependencies: list[MissingDependency]


# Job responses
class JobResponse(BaseModel):
    """Job response for async operations."""

    job_id: str
    type: str
    status: str
    created_at: datetime
    metadata: dict = Field(default_factory=dict)


class JobStatusResponse(BaseModel):
    """Job status response."""

    id: str
    type: str
    status: str
    progress: int = 0
    total: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


# Project requests/responses
class CreateProjectRequest(BaseModel):
    """Create project request."""

    name: str = Field(..., min_length=1, max_length=100)
    format: ProjectFormat = ProjectFormat.WEBTOON


class UpdateProjectRequest(BaseModel):
    """Update project request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[ProjectStatus] = None


class ProjectResponse(BaseModel):
    """Project response."""

    id: str
    name: str
    format: ProjectFormat
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    story_expanded: bool
    character_count: int
    location_count: int
    chapter_count: int


class ProjectStatusResponse(BaseModel):
    """Project status response."""

    project_id: str
    project_name: str
    status: str
    story_expanded: bool
    characters: dict
    locations: dict
    chapters: dict
    panels: dict


# Story requests/responses
class CreateStoryRequest(BaseModel):
    """Create/expand story request."""

    prompt: str = Field(..., min_length=10, max_length=5000)
    genre: Optional[Genre] = None
    tone: Optional[Tone] = None
    episodes: int = Field(10, ge=1, le=100)


class StoryResponse(BaseModel):
    """Story response."""

    id: str
    title: str
    logline: str
    genre: Genre
    tone: Tone
    themes: list[str]
    target_audience: str
    episode_count: int
    synopsis: str
    story_beats: list[dict]


# Character requests/responses
class CreateCharacterRequest(BaseModel):
    """Create character request."""

    name: str = Field(..., min_length=1, max_length=100)
    role: CharacterRole = CharacterRole.SUPPORTING
    age: str = ""
    description: Optional[CharacterDescription] = None
    visual_tags: list[str] = Field(default_factory=list)


class UpdateCharacterRequest(BaseModel):
    """Update character request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[CharacterRole] = None
    age: Optional[str] = None
    description: Optional[CharacterDescription] = None
    visual_tags: Optional[list[str]] = None


class CreateCharacterAssetRequest(BaseModel):
    """Create character asset request."""

    style: str = "webtoon"
    overwrite: bool = False


class CharacterAssetResponse(BaseModel):
    """Character asset response."""

    character_id: str
    portrait: Optional[str] = None
    three_view: dict[str, Optional[str]] = Field(default_factory=dict)


# Location requests/responses
class CreateLocationRequest(BaseModel):
    """Create location request."""

    name: str = Field(..., min_length=1, max_length=100)
    type: LocationType = LocationType.INTERIOR
    description: str = ""
    visual_tags: list[str] = Field(default_factory=list)


class UpdateLocationRequest(BaseModel):
    """Update location request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[LocationType] = None
    description: Optional[str] = None
    visual_tags: Optional[list[str]] = None


class CreateLocationAssetRequest(BaseModel):
    """Create location asset request."""

    style: str = "webtoon"
    overwrite: bool = False


class LocationAssetResponse(BaseModel):
    """Location asset response."""

    location_id: str
    reference: Optional[str] = None


# Chapter requests/responses
class CreateChapterRequest(BaseModel):
    """Create chapter request."""

    beat_number: int = Field(..., ge=1)
    panels_per_scene: int = Field(6, ge=1, le=20)


# Panel requests/responses
class CreatePanelsRequest(BaseModel):
    """Create panels request."""

    style: str = "webtoon"
    overwrite: bool = False


class CreateScenePanelsRequest(BaseModel):
    """Create scene panels request."""

    style: str = "webtoon"
    overwrite: bool = False


class PanelGenerationResult(BaseModel):
    """Panel generation result."""

    chapter_number: int
    scene_number: Optional[int] = None
    generated_count: int
    skipped_count: int
    error_count: int
    output_dir: Optional[str] = None


# Asset responses
class AssetMetadata(BaseModel):
    """Asset metadata."""

    type: str
    generated_at: Optional[datetime] = None
    style: Optional[str] = None
    prompt: Optional[str] = None
    model: Optional[str] = None


# Utility functions
def project_to_response(project: Project) -> ProjectResponse:
    """Convert Project model to response."""
    return ProjectResponse(
        id=project.id,
        name=project.name,
        format=project.format,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        story_expanded=project.story is not None,
        character_count=len(project.characters),
        location_count=len(project.locations),
        chapter_count=len(project.chapters),
    )


def story_to_response(story: Story) -> StoryResponse:
    """Convert Story model to response."""
    return StoryResponse(
        id=story.id,
        title=story.title,
        logline=story.logline,
        genre=story.genre,
        tone=story.tone,
        themes=story.themes,
        target_audience=story.target_audience,
        episode_count=story.episode_count,
        synopsis=story.synopsis,
        story_beats=[
            {"beat": b.beat, "description": b.description}
            for b in story.story_beats
        ],
    )
