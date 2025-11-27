"""Chapter generation service."""

from typing import Callable, Optional

from ..generators.chapter import ChapterGenerator
from ..models import Chapter, ChapterStatus, StoryBeat
from ..storage import ProjectManager
from .exceptions import DependencyError, NotFoundError, ValidationError

# Callback type aliases for interactive mode
# on_prompt_ready: Called before API call, return True to proceed, False to skip
OnPromptReady = Callable[[str, int, StoryBeat], bool]
# on_result_ready: Called after generation, return (accept, retry)
OnResultReady = Callable[[Chapter, int], tuple[bool, bool]]
# on_chapter_start: Called when starting chapter generation
OnChapterStart = Callable[[int, StoryBeat], None]
# on_chapter_complete: Called when chapter is saved
OnChapterComplete = Callable[[Chapter], None]


class ChapterService:
    """Service for chapter generation operations."""

    def __init__(self, manager: ProjectManager):
        """Initialize service with a project manager."""
        self.manager = manager

    def list_chapters(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Chapter], int]:
        """List all chapters with pagination.

        Returns:
            Tuple of (chapters, total_count)
        """
        chapters = self.manager.project.chapters
        total = len(chapters)
        return chapters[offset:offset + limit], total

    def get_chapter(self, chapter_id: str) -> Chapter:
        """Get chapter by ID.

        Raises:
            NotFoundError: If chapter not found
        """
        for ch in self.manager.project.chapters:
            if ch.id == chapter_id:
                return ch
        raise NotFoundError("Chapter", chapter_id)

    def get_chapter_by_number(self, number: int) -> Chapter:
        """Get chapter by number.

        Raises:
            NotFoundError: If chapter not found
        """
        for ch in self.manager.project.chapters:
            if ch.number == number:
                return ch
        raise NotFoundError("Chapter", str(number))

    def delete_chapter(self, chapter_id: str) -> bool:
        """Delete a chapter.

        Returns:
            True if deleted
        """
        chapters = self.manager.project.chapters
        for i, ch in enumerate(chapters):
            if ch.id == chapter_id:
                chapters.pop(i)
                self.manager.save()
                return True
        return False

    def validate_dependencies(self, beat_number: int) -> list[dict]:
        """Validate chapter generation dependencies.

        Assumes beat_number has already been validated for range.

        Args:
            beat_number: The beat number to generate chapter for

        Returns:
            List of missing dependencies (empty if all met)
        """
        missing = []

        # Check previous chapter exists (for chapter N > 1)
        if beat_number > 1:
            existing_numbers = {c.number for c in self.manager.project.chapters}
            if beat_number - 1 not in existing_numbers:
                missing.append({
                    "type": "previous_chapter",
                    "chapter_number": beat_number - 1,
                    "message": f"Chapter {beat_number - 1} must be generated first",
                    "resolution": f"Generate chapter {beat_number - 1} first for story continuity",
                })

        return missing

    def validate_beat_number(self, beat_number: int) -> StoryBeat:
        """Validate beat number and return the beat.

        Raises:
            ValidationError: If beat number invalid or no story
        """
        if not self.manager.project.story:
            raise ValidationError("No story expanded yet")

        story = self.manager.project.story
        if not story.story_beats:
            raise ValidationError("No story beats found")

        if beat_number < 1 or beat_number > len(story.story_beats):
            raise ValidationError(
                f"Invalid beat number. Must be 1-{len(story.story_beats)}",
                field="beat_number",
            )

        return story.story_beats[beat_number - 1]

    async def generate_chapter(
        self,
        beat_number: int,
        panels_per_scene: int = 6,
        on_start: Optional[OnChapterStart] = None,
        on_prompt_ready: Optional[OnPromptReady] = None,
        on_result_ready: Optional[OnResultReady] = None,
        on_complete: Optional[OnChapterComplete] = None,
    ) -> Optional[Chapter]:
        """Generate a chapter from a story beat.

        Args:
            beat_number: Story beat number (1-indexed)
            panels_per_scene: Target panels per scene
            on_start: Callback when chapter generation starts
            on_prompt_ready: Callback before API call, return False to skip
            on_result_ready: Callback after generation, return (accept, retry)
            on_complete: Callback when chapter is saved

        Returns:
            Generated chapter, or None if skipped via callback

        Raises:
            DependencyError: If dependencies not met
            ValidationError: If beat number invalid
        """
        # Validate beat number
        beat = self.validate_beat_number(beat_number)

        # Validate dependencies
        missing = self.validate_dependencies(beat_number)
        if missing:
            raise DependencyError(
                f"Cannot generate chapter {beat_number}: dependencies not met",
                missing,
            )

        story = self.manager.project.story
        existing_chapters = sorted(self.manager.project.chapters, key=lambda c: c.number)

        # Notify start
        if on_start:
            on_start(beat_number, beat)

        # Build prompt
        generator = ChapterGenerator()
        prompt = generator.build_chapter_prompt(
            story=story,
            beat=beat,
            chapter_number=beat_number,
            characters=self.manager.project.characters,
            locations=self.manager.project.locations,
            previous_chapters=existing_chapters,
            panels_per_scene=panels_per_scene,
        )

        # Check prompt confirmation (interactive mode)
        if on_prompt_ready:
            if not on_prompt_ready(prompt, beat_number, beat):
                return None  # User skipped

        # Generate with retry loop for interactive mode
        max_retries = 3
        for attempt in range(max_retries):
            chapter = await generator.generate_chapter_from_prompt(
                prompt=prompt,
                characters=self.manager.project.characters,
                locations=self.manager.project.locations,
            )

            # Check result confirmation (interactive mode)
            if on_result_ready:
                accept, retry = on_result_ready(chapter, beat_number)
                if accept:
                    break
                elif retry and attempt < max_retries - 1:
                    continue  # Retry generation
                else:
                    return None  # User rejected
            else:
                break  # No callback, accept result

        # Mark chapter as completed
        chapter.status = ChapterStatus.COMPLETED

        # Save
        self._save_chapter(chapter)

        # Notify complete
        if on_complete:
            on_complete(chapter)

        return chapter

    async def generate_chapters(
        self,
        beat_numbers: Optional[list[int]] = None,
        panels_per_scene: int = 6,
        on_start: Optional[OnChapterStart] = None,
        on_prompt_ready: Optional[OnPromptReady] = None,
        on_result_ready: Optional[OnResultReady] = None,
        on_complete: Optional[OnChapterComplete] = None,
    ) -> list[Chapter]:
        """Generate multiple chapters from story beats.

        Args:
            beat_numbers: Specific beats to generate (None = all remaining)
            panels_per_scene: Target panels per scene
            on_start: Callback when chapter generation starts
            on_prompt_ready: Callback before API call, return False to skip
            on_result_ready: Callback after generation, return (accept, retry)
            on_complete: Callback when chapter is saved

        Returns:
            List of generated chapters
        """
        if beat_numbers is None:
            # Generate all remaining
            remaining = self.get_remaining_beats()
            beat_numbers = [num for num, _ in remaining]

        if not beat_numbers:
            return []

        generated = []
        for beat_number in beat_numbers:
            chapter = await self.generate_chapter(
                beat_number=beat_number,
                panels_per_scene=panels_per_scene,
                on_start=on_start,
                on_prompt_ready=on_prompt_ready,
                on_result_ready=on_result_ready,
                on_complete=on_complete,
            )
            if chapter:
                generated.append(chapter)

        return generated

    def _save_chapter(self, chapter: Chapter) -> None:
        """Save a chapter to the project."""
        # Replace existing or append
        existing_idx = None
        for i, c in enumerate(self.manager.project.chapters):
            if c.number == chapter.number:
                existing_idx = i
                break

        if existing_idx is not None:
            self.manager.project.chapters[existing_idx] = chapter
        else:
            self.manager.project.chapters.append(chapter)
            self.manager.project.chapters.sort(key=lambda c: c.number)

        self.manager.save()

    def get_remaining_beats(self) -> list[tuple[int, dict]]:
        """Get list of story beats that don't have chapters yet.

        Returns:
            List of (beat_number, beat) tuples
        """
        if not self.manager.project.story:
            return []

        existing_numbers = {c.number for c in self.manager.project.chapters}
        remaining = []

        for i, beat in enumerate(self.manager.project.story.story_beats, start=1):
            if i not in existing_numbers:
                remaining.append((i, {
                    "beat": beat.beat,
                    "description": beat.description,
                }))

        return remaining

    def get_generation_status(self) -> dict:
        """Get chapter generation status.

        Returns:
            Status dict with completed/remaining beats
        """
        if not self.manager.project.story:
            return {
                "story_expanded": False,
                "total_beats": 0,
                "generated_chapters": 0,
                "remaining_beats": [],
            }

        total = len(self.manager.project.story.story_beats)
        existing = {c.number for c in self.manager.project.chapters}

        return {
            "story_expanded": True,
            "total_beats": total,
            "generated_chapters": len(existing),
            "remaining_beats": [i for i in range(1, total + 1) if i not in existing],
            "chapters": [
                {
                    "number": ch.number,
                    "id": ch.id,
                    "title": ch.title,
                    "status": ch.status.value,
                    "scene_count": len(ch.scenes),
                    "panel_count": sum(len(s.panels) for s in ch.scenes),
                }
                for ch in sorted(self.manager.project.chapters, key=lambda c: c.number)
            ],
        }
