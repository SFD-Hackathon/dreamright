"""Core data models for DreamRight."""

import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)  # Remove non-word chars
    text = re.sub(r'[\s_-]+', '_', text)  # Replace spaces/dashes with underscore
    return text[:30]  # Limit length


class ProjectFormat(str, Enum):
    """Project output format."""

    WEBTOON = "webtoon"
    SHORT_DRAMA = "short_drama"


class ProjectStatus(str, Enum):
    """Project status."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Genre(str, Enum):
    """Story genre."""

    ROMANCE = "romance"
    ACTION = "action"
    FANTASY = "fantasy"
    THRILLER = "thriller"
    SLICE_OF_LIFE = "slice_of_life"
    HORROR = "horror"
    COMEDY = "comedy"
    DRAMA = "drama"
    MYSTERY = "mystery"
    SCIFI = "scifi"


class Tone(str, Enum):
    """Story tone."""

    COMEDIC = "comedic"
    DRAMATIC = "dramatic"
    DARK = "dark"
    LIGHTHEARTED = "lighthearted"
    ROMANTIC = "romantic"
    SUSPENSEFUL = "suspenseful"


class CharacterRole(str, Enum):
    """Character role in the story."""

    PROTAGONIST = "protagonist"
    ANTAGONIST = "antagonist"
    SUPPORTING = "supporting"
    MINOR = "minor"


class LocationType(str, Enum):
    """Location type."""

    INTERIOR = "interior"
    EXTERIOR = "exterior"


class TimeOfDay(str, Enum):
    """Time of day for scenes."""

    MORNING = "morning"
    DAY = "day"
    EVENING = "evening"
    NIGHT = "night"


class ShotType(str, Enum):
    """Camera shot type for panels."""

    WIDE = "wide"
    MEDIUM = "medium"
    CLOSE_UP = "close_up"
    EXTREME_CLOSE_UP = "extreme_close_up"


class CameraAngle(str, Enum):
    """Camera angle for panels."""

    EYE_LEVEL = "eye_level"
    HIGH = "high"
    LOW = "low"
    DUTCH = "dutch"


class DialogueType(str, Enum):
    """Type of dialogue."""

    SPEECH = "speech"
    THOUGHT = "thought"
    NARRATION = "narration"


# === Core Models ===


class StoryBeat(BaseModel):
    """A key story beat/plot point."""

    beat: str
    description: str


class CharacterDescription(BaseModel):
    """Detailed character description."""

    physical: str = ""
    personality: str = ""
    background: str = ""
    motivation: str = ""


class CharacterAssets(BaseModel):
    """Generated character visual assets."""

    reference_input: Optional[str] = None  # User-provided reference path
    portrait: Optional[str] = None
    three_view: dict[str, Optional[str]] = Field(
        default_factory=lambda: {"front": None, "side": None, "back": None}
    )


class Character(BaseModel):
    """A character in the story."""

    id: str = ""
    name: str
    role: CharacterRole = CharacterRole.SUPPORTING
    age: str = ""
    description: CharacterDescription = Field(default_factory=CharacterDescription)
    visual_tags: list[str] = Field(default_factory=list)
    assets: CharacterAssets = Field(default_factory=CharacterAssets)
    voice_description: str = ""  # For future TTS

    @model_validator(mode='after')
    def set_id_from_name(self) -> 'Character':
        """Generate ID from name if not provided."""
        if not self.id:
            self.id = f"char_{slugify(self.name)}"
        return self


class LocationAssets(BaseModel):
    """Generated location visual assets."""

    reference: Optional[str] = None


class Location(BaseModel):
    """A location/setting in the story."""

    id: str = ""
    name: str
    type: LocationType = LocationType.INTERIOR
    description: str = ""
    visual_tags: list[str] = Field(default_factory=list)
    assets: LocationAssets = Field(default_factory=LocationAssets)

    @model_validator(mode='after')
    def set_id_from_name(self) -> 'Location':
        """Generate ID from name if not provided."""
        if not self.id:
            self.id = f"loc_{slugify(self.name)}"
        return self


class Story(BaseModel):
    """The main story structure."""

    id: str = ""
    title: str
    logline: str = ""
    genre: Genre = Genre.DRAMA
    tone: Tone = Tone.DRAMATIC
    themes: list[str] = Field(default_factory=list)
    target_audience: str = ""
    episode_count: int = 10
    synopsis: str = ""
    story_beats: list[StoryBeat] = Field(default_factory=list)

    @model_validator(mode='after')
    def set_id_from_title(self) -> 'Story':
        """Generate ID from title if not provided."""
        if not self.id:
            self.id = f"story_{slugify(self.title)}"
        return self


class Dialogue(BaseModel):
    """A piece of dialogue in a panel."""

    character_id: Optional[str] = None
    text: str
    type: DialogueType = DialogueType.SPEECH


class PanelCharacter(BaseModel):
    """A character's appearance in a panel."""

    character_id: str
    expression: str = "neutral"
    pose: str = ""
    position: str = "center"  # left, center, right, background


class PanelComposition(BaseModel):
    """Visual composition of a panel."""

    shot_type: ShotType = ShotType.MEDIUM
    angle: CameraAngle = CameraAngle.EYE_LEVEL
    focus: str = ""  # character_id, "location", or "action"


class Panel(BaseModel):
    """A single webtoon panel / video shot."""

    id: str = ""
    number: int
    type: str = "panel"  # panel, transition, splash
    composition: PanelComposition = Field(default_factory=PanelComposition)
    characters: list[PanelCharacter] = Field(default_factory=list)
    action: str = ""
    dialogue: list[Dialogue] = Field(default_factory=list)
    sfx: list[str] = Field(default_factory=list)

    # Panel continuity - for consistent image generation
    continues_from_previous: bool = False  # True if same moment/scene as previous panel
    continuity_note: str = ""  # What should stay consistent (pose, position, lighting, etc.)

    image_path: Optional[str] = None
    video_path: Optional[str] = None

    @model_validator(mode='after')
    def set_id_from_number(self) -> 'Panel':
        """Generate ID from number if not provided."""
        if not self.id:
            self.id = f"p{self.number}"
        return self


class Scene(BaseModel):
    """A scene containing multiple panels."""

    id: str = ""
    number: int
    location_id: Optional[str] = None
    time_of_day: TimeOfDay = TimeOfDay.DAY
    weather: str = "clear"
    character_ids: list[str] = Field(default_factory=list)
    description: str = ""
    mood: str = ""
    panels: list[Panel] = Field(default_factory=list)

    # Cross-chapter continuity - if True, first panel references last panel of previous chapter
    continues_from_previous_chapter: bool = False

    @model_validator(mode='after')
    def set_id_from_number(self) -> 'Scene':
        """Generate ID from number if not provided."""
        if not self.id:
            self.id = f"s{self.number}"
        return self


class ChapterStatus(str, Enum):
    """Chapter generation status."""

    OUTLINED = "outlined"
    GENERATING = "generating"
    COMPLETED = "completed"


class Chapter(BaseModel):
    """A chapter/episode containing scenes."""

    id: str = ""
    number: int
    title: str = ""
    summary: str = ""
    status: ChapterStatus = ChapterStatus.OUTLINED
    scenes: list[Scene] = Field(default_factory=list)

    @model_validator(mode='after')
    def set_id_from_number(self) -> 'Chapter':
        """Generate ID from number if not provided."""
        if not self.id:
            self.id = f"ch{self.number}"
        return self


class Project(BaseModel):
    """The top-level project container."""

    id: str = ""
    name: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    format: ProjectFormat = ProjectFormat.WEBTOON
    status: ProjectStatus = ProjectStatus.DRAFT

    # Core content
    story: Optional[Story] = None
    characters: list[Character] = Field(default_factory=list)
    locations: list[Location] = Field(default_factory=list)
    chapters: list[Chapter] = Field(default_factory=list)

    # Original user input
    original_prompt: str = ""
    reference_images: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def set_id_from_name(self) -> 'Project':
        """Generate ID from name if not provided."""
        if not self.id:
            self.id = f"proj_{slugify(self.name)}"
        return self

    def get_character_by_id(self, character_id: str) -> Optional[Character]:
        """Get character by ID."""
        for char in self.characters:
            if char.id == character_id:
                return char
        return None

    def get_character_by_name(self, name: str) -> Optional[Character]:
        """Get character by name (case-insensitive)."""
        name_lower = name.lower()
        for char in self.characters:
            if char.name.lower() == name_lower:
                return char
        return None

    def get_location_by_id(self, location_id: str) -> Optional[Location]:
        """Get location by ID."""
        for loc in self.locations:
            if loc.id == location_id:
                return loc
        return None

    def get_location_by_name(self, name: str) -> Optional[Location]:
        """Get location by name (case-insensitive)."""
        name_lower = name.lower()
        for loc in self.locations:
            if loc.name.lower() == name_lower:
                return loc
        return None
