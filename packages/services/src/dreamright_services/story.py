"""Story expansion service."""

from typing import Optional

from dreamright_generators.story import StoryExpander
from dreamright_core_schemas import Character, Genre, Location, ProjectStatus, Story, Tone
from dreamright_storage import ProjectManager
from .exceptions import NotFoundError, ValidationError


class StoryService:
    """Service for story expansion operations."""

    def __init__(self, manager: ProjectManager):
        """Initialize service with a project manager."""
        self.manager = manager

    async def expand(
        self,
        prompt: str,
        genre: Optional[Genre] = None,
        tone: Optional[Tone] = None,
        episodes: int = 10,
    ) -> tuple[Story, list[Character], list[Location]]:
        """Expand a story prompt into full story structure.

        Args:
            prompt: Story idea/prompt
            genre: Genre hint (optional)
            tone: Tone hint (optional)
            episodes: Target episode count

        Returns:
            Tuple of (Story, Characters, Locations)
        """
        expander = StoryExpander()
        story, characters, locations = await expander.expand(
            prompt=prompt,
            genre_hint=genre,
            tone_hint=tone,
            episode_count=episodes,
        )

        # Update project
        self.manager.project.original_prompt = prompt
        self.manager.project.story = story
        self.manager.project.characters = characters
        self.manager.project.locations = locations
        self.manager.project.status = ProjectStatus.IN_PROGRESS
        self.manager.save()

        return story, characters, locations

    def get_story(self) -> Story:
        """Get the current story.

        Returns:
            Story instance

        Raises:
            NotFoundError: If no story exists
        """
        if not self.manager.project.story:
            raise NotFoundError("Story", "current")
        return self.manager.project.story

    def update_story(
        self,
        title: Optional[str] = None,
        logline: Optional[str] = None,
        genre: Optional[Genre] = None,
        tone: Optional[Tone] = None,
        synopsis: Optional[str] = None,
    ) -> Story:
        """Update story properties.

        Args:
            title: New title
            logline: New logline
            genre: New genre
            tone: New tone
            synopsis: New synopsis

        Returns:
            Updated story
        """
        story = self.get_story()

        if title is not None:
            story.title = title
        if logline is not None:
            story.logline = logline
        if genre is not None:
            story.genre = genre
        if tone is not None:
            story.tone = tone
        if synopsis is not None:
            story.synopsis = synopsis

        self.manager.save()
        return story

    def parse_genre(self, genre_str: str) -> Optional[Genre]:
        """Parse genre string to enum.

        Args:
            genre_str: Genre string

        Returns:
            Genre enum or None if invalid
        """
        try:
            return Genre(genre_str.lower())
        except ValueError:
            return None

    def parse_tone(self, tone_str: str) -> Optional[Tone]:
        """Parse tone string to enum.

        Args:
            tone_str: Tone string

        Returns:
            Tone enum or None if invalid
        """
        try:
            return Tone(tone_str.lower())
        except ValueError:
            return None
