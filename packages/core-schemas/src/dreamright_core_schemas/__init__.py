"""Core domain models and API schemas for DreamRight."""

from dreamright_core_schemas.models import (
    # Enums
    CameraAngle,
    ChapterStatus,
    CharacterRole,
    DialogueType,
    Genre,
    LocationType,
    ProjectFormat,
    ProjectStatus,
    ShotType,
    TimeOfDay,
    Tone,
    # Domain Models
    Chapter,
    Character,
    CharacterAssets,
    CharacterDescription,
    Dialogue,
    Location,
    LocationAssets,
    Panel,
    PanelCharacter,
    PanelComposition,
    Project,
    Scene,
    Story,
    StoryBeat,
    # Utilities
    slugify,
)
from dreamright_core_schemas.exceptions import (
    AssetExistsError,
    DependencyError,
    GenerationError,
    NotFoundError,
    ServiceError,
    ValidationError,
)

__all__ = [
    # Enums
    "CameraAngle",
    "ChapterStatus",
    "CharacterRole",
    "DialogueType",
    "Genre",
    "LocationType",
    "ProjectFormat",
    "ProjectStatus",
    "ShotType",
    "TimeOfDay",
    "Tone",
    # Domain Models
    "Chapter",
    "Character",
    "CharacterAssets",
    "CharacterDescription",
    "Dialogue",
    "Location",
    "LocationAssets",
    "Panel",
    "PanelCharacter",
    "PanelComposition",
    "Project",
    "Scene",
    "Story",
    "StoryBeat",
    # Utilities
    "slugify",
    # Exceptions
    "AssetExistsError",
    "DependencyError",
    "GenerationError",
    "NotFoundError",
    "ServiceError",
    "ValidationError",
]
