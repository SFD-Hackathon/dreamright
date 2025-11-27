"""Chapter generation from story beats."""

from typing import Optional

from pydantic import BaseModel, Field

from dreamright_gemini_client import GeminiClient
from dreamright_core_schemas import (
    CameraAngle,
    Chapter,
    ChapterStatus,
    Character,
    Dialogue,
    DialogueType,
    Location,
    Panel,
    PanelCharacter,
    PanelComposition,
    Scene,
    ShotType,
    Story,
    StoryBeat,
    TimeOfDay,
)


class DialogueResponse(BaseModel):
    """Dialogue in a panel."""

    character_name: str = ""
    text: str
    type: str = "speech"  # speech, thought, narration


class CharacterExpressionResponse(BaseModel):
    """Character expression in a panel."""

    character_name: str
    expression: str = "neutral"


class PanelResponse(BaseModel):
    """A panel in a scene."""

    number: int
    shot_type: str = "medium"  # wide, medium, close_up, extreme_close_up
    angle: str = "eye_level"  # eye_level, high, low, dutch
    action: str
    characters: list[str] = Field(default_factory=list)  # Character names
    character_expressions: list[CharacterExpressionResponse] = Field(default_factory=list)
    dialogue: list[DialogueResponse] = Field(default_factory=list)
    sfx: list[str] = Field(default_factory=list)
    continues_from_previous: bool = False  # True if same moment/scene as previous panel
    continuity_note: str = ""  # What should stay consistent (pose, position, lighting)


class SceneResponse(BaseModel):
    """A scene in a chapter."""

    number: int
    location_name: str
    time_of_day: str = "day"  # morning, day, evening, night
    mood: str = ""
    description: str = ""
    character_names: list[str] = Field(default_factory=list)
    panels: list[PanelResponse] = Field(default_factory=list)
    # For first scene only: does it continue directly from the previous chapter's last panel?
    continues_from_previous_chapter: bool = False


class ChapterResponse(BaseModel):
    """A full chapter with scenes and panels."""

    number: int
    title: str
    summary: str
    scenes: list[SceneResponse] = Field(default_factory=list)


CHAPTER_GENERATION_PROMPT = """You are an expert webtoon storyboard artist creating addictive, visually compelling content. Convert story beats into detailed chapters optimized for vertical scrolling.

## SCENE STRUCTURE (4-8 panels per scene)
Each scene should have rhythm:
1. **Opening** (1-2 panels): Establish location and mood with wide/medium shots
2. **Development** (2-4 panels): Build tension or emotion, advance plot
3. **Payoff/Hook** (1-2 panels): End with impact - revelation, emotion, or cliffhanger

## PANEL PACING FOR ENGAGEMENT
- **Slow moments down**: Use multiple panels for emotional beats (reaction shots, silences)
- **Speed up action**: Quick cuts, motion blur descriptions, diagonal compositions
- **Create rhythm**: Alternate between dialogue-heavy and visual-only panels
- **End scenes on hooks**: Last panel should make readers NEED to scroll

## VISUAL STORYTELLING
Use panels to SHOW, not just tell:
- **POV shots**: Show what character sees (especially for horror/mystery)
- **Environmental storytelling**: Background details that hint at story/mood
- **Color/lighting shifts**: Describe palette changes for mood (warm→cold = safe→danger)
- **Visual metaphors**: Symbolic imagery that reinforces themes

## EMOTIONAL BEATS
Include variety in each chapter:
- **Tension**: Danger, conflict, stakes
- **Relief**: Humor, tender moments, breathers
- **Mystery**: Questions raised, clues planted
- **Connection**: Character bonding, vulnerability

## SHOT TYPES (use variety!)
- **wide**: Full environment, multiple characters, establishing mood
- **medium**: Waist-up, ideal for dialogue and interaction
- **close_up**: Face focus, emotional intensity, important reactions
- **extreme_close_up**: Eyes, hands, objects - for emphasis and tension

## CAMERA ANGLES (match emotion)
- **eye_level**: Neutral, normal conversation
- **high**: Vulnerability, overview, isolation
- **low**: Power, threat, dramatic impact
- **dutch**: Unease, disorientation, wrongness

## EXPRESSIONS
Use specific emotions: neutral, happy, sad, angry, surprised, scared, confused, determined, embarrassed, thoughtful, mischievous, exhausted, hopeful, devastated

## ATMOSPHERE DESCRIPTIONS
For each panel, include atmosphere cues:
- Lighting quality (harsh, soft, dappled, flickering)
- Color temperature (warm golden, cold blue, sickly green)
- Visual effects (dust motes, lens flare, motion blur, static)

## PANEL CONTINUITY
For continuous moments (same scene, same beat):
- continues_from_previous: true for direct continuation (reaction shots, zooms)
- continuity_note: what stays consistent (pose, lighting, background angle)

## CROSS-CHAPTER CONTINUITY
For first scene:
- continues_from_previous_chapter: true if immediate continuation (mid-conversation, cliffhanger resolution)
- continues_from_previous_chapter: false if time skip or new setting
"""


class ChapterGenerator:
    """Generates detailed chapters from story beats."""

    def __init__(self, client: Optional[GeminiClient] = None):
        """Initialize the chapter generator."""
        if client is None:
            from dreamright_gemini_client import get_client

            client = get_client()
        self.client = client

    def _chapter_headline(self, chapter: Chapter) -> str:
        """Create a one-line headline for a chapter (title + summary)."""
        return f"Chapter {chapter.number}: {chapter.title} - {chapter.summary}"

    def format_chapter_result(self, chapter: Chapter) -> str:
        """Format a chapter for display/review.

        Args:
            chapter: The generated chapter

        Returns:
            Human-readable formatted string
        """
        lines = [
            f"Chapter {chapter.number}: {chapter.title}",
            f"Summary: {chapter.summary}",
            "",
        ]

        for scene in chapter.scenes:
            lines.append(f"── Scene {scene.number} ──")
            if scene.description:
                lines.append(f"Description: {scene.description}")
            if scene.location_id:
                lines.append(f"Location: {scene.location_id}")
            lines.append(f"Mood: {scene.mood}")
            lines.append("")

            for panel in scene.panels:
                continuity_marker = " [→]" if panel.continues_from_previous else ""
                lines.append(f"  Panel {panel.number}:{continuity_marker}")
                lines.append(f"    Shot: {panel.composition.shot_type.value}, Angle: {panel.composition.angle.value}")
                if panel.continues_from_previous and panel.continuity_note:
                    lines.append(f"    Continuity: {panel.continuity_note}")
                lines.append(f"    Action: {panel.action}")

                if panel.characters:
                    chars = ", ".join(
                        f"{pc.character_id}({pc.expression})"
                        for pc in panel.characters
                    )
                    lines.append(f"    Characters: {chars}")

                for d in panel.dialogue:
                    dtype = f"[{d.type.value}]" if d.type.value != "speech" else ""
                    lines.append(f"    💬 {dtype}: \"{d.text}\"")

                if panel.sfx:
                    lines.append(f"    SFX: {', '.join(panel.sfx)}")

                lines.append("")

        return "\n".join(lines)

    def _chapter_detailed(self, chapter: Chapter) -> str:
        """Create detailed context for a chapter including scenes and dialogue."""
        lines = [f"Chapter {chapter.number}: {chapter.title}"]
        lines.append(f"Summary: {chapter.summary}")

        # Add key dialogue/events from scenes
        for scene in chapter.scenes:
            if scene.description:
                lines.append(f"- Scene: {scene.description[:100]}...")
            # Include some key dialogue
            for panel in scene.panels[:2]:  # First 2 panels per scene
                for d in panel.dialogue[:1]:  # First dialogue per panel
                    lines.append(f"  - \"{d.text[:60]}...\"" if len(d.text) > 60 else f"  - \"{d.text}\"")

        return "\n".join(lines)

    def build_chapter_prompt(
        self,
        story: Story,
        beat: StoryBeat,
        chapter_number: int,
        characters: list[Character],
        locations: list[Location],
        previous_chapters: Optional[list[Chapter]] = None,
        panels_per_scene: int = 6,
    ) -> str:
        """Build the prompt for chapter generation without calling API.

        Args:
            story: The full story context
            beat: The story beat for this chapter
            chapter_number: Chapter number
            characters: Available characters
            locations: Available locations
            previous_chapters: Previously generated chapters for continuity
            panels_per_scene: Target panels per scene

        Returns:
            The prompt string that would be sent to the API
        """
        # Build character and location context
        char_info = "\n".join(
            f"- {c.name} ({c.role.value}): {c.description.personality}"
            for c in characters
        )
        loc_info = "\n".join(f"- {loc.name}: {loc.description}" for loc in locations)

        # Build previous chapter context
        prev_context = ""
        if previous_chapters:
            # All chapters get headline (title + summary) for story arc overview
            all_headlines = [self._chapter_headline(ch) for ch in previous_chapters]

            # Last 2 chapters get detailed context (scenes, dialogue) for continuity
            recent_detailed = []
            for prev_ch in previous_chapters[-2:]:
                recent_detailed.append(self._chapter_detailed(prev_ch))

            prev_context = f"""
STORY SO FAR (all previous chapters):
{chr(10).join(all_headlines)}

RECENT CHAPTER DETAILS (for voice and continuity):
{chr(10).join(recent_detailed)}

IMPORTANT: Continue the story naturally from where the previous chapter left off.
Maintain character voice, ongoing plot threads, and emotional arcs.
Reference events from earlier chapters where relevant.
"""

        return f"""Create a detailed webtoon chapter for the following:

STORY: {story.title}
{story.logline}
{prev_context}
CHAPTER {chapter_number}: {beat.beat}
{beat.description}

AVAILABLE CHARACTERS:
{char_info}

AVAILABLE LOCATIONS:
{loc_info}

Generate 2-3 scenes with {panels_per_scene} panels each that bring this story beat to life.
Include specific dialogue, expressions, and visual directions.
Make sure to use the available characters and locations appropriately.
"""

    async def generate_chapter_from_prompt(
        self,
        prompt: str,
        characters: list[Character],
        locations: list[Location],
    ) -> Chapter:
        """Generate a chapter from a pre-built prompt.

        Args:
            prompt: The prompt to send to the API
            characters: Available characters (for ID resolution)
            locations: Available locations (for ID resolution)

        Returns:
            A fully detailed Chapter
        """
        response = await self.client.generate_structured(
            prompt=prompt,
            response_schema=ChapterResponse,
            system_instruction=CHAPTER_GENERATION_PROMPT,
            temperature=0.8,
        )

        return self._convert_chapter(response, characters, locations)

    async def generate_chapter(
        self,
        story: Story,
        beat: StoryBeat,
        chapter_number: int,
        characters: list[Character],
        locations: list[Location],
        previous_chapters: Optional[list[Chapter]] = None,
        panels_per_scene: int = 6,
    ) -> Chapter:
        """Generate a detailed chapter from a story beat.

        Args:
            story: The full story context
            beat: The story beat for this chapter
            chapter_number: Chapter number
            characters: Available characters
            locations: Available locations
            previous_chapters: Previously generated chapters for continuity
            panels_per_scene: Target panels per scene

        Returns:
            A fully detailed Chapter
        """
        prompt = self.build_chapter_prompt(
            story=story,
            beat=beat,
            chapter_number=chapter_number,
            characters=characters,
            locations=locations,
            previous_chapters=previous_chapters,
            panels_per_scene=panels_per_scene,
        )

        return await self.generate_chapter_from_prompt(prompt, characters, locations)

    def _convert_chapter(
        self,
        response: ChapterResponse,
        characters: list[Character],
        locations: list[Location],
    ) -> Chapter:
        """Convert response to Chapter model."""
        # Build lookup maps
        char_by_name = {c.name.lower(): c for c in characters}
        loc_by_name = {loc.name.lower(): loc for loc in locations}

        # Deduplicate scenes by number - keep the one with most panels
        scene_by_number: dict[int, SceneResponse] = {}
        for scene_resp in response.scenes:
            num = scene_resp.number
            if num not in scene_by_number or len(scene_resp.panels) > len(scene_by_number[num].panels):
                scene_by_number[num] = scene_resp

        scenes = []
        for scene_resp in scene_by_number.values():
            # Find location
            loc_id = None
            loc_key = scene_resp.location_name.lower()
            for name, loc in loc_by_name.items():
                if loc_key in name or name in loc_key:
                    loc_id = loc.id
                    break

            # Find characters
            char_ids = []
            for char_name in scene_resp.character_names:
                char_key = char_name.lower()
                for name, char in char_by_name.items():
                    if char_key in name or name in char_key:
                        char_ids.append(char.id)
                        break

            # Parse time of day
            try:
                time_of_day = TimeOfDay(scene_resp.time_of_day.lower())
            except ValueError:
                time_of_day = TimeOfDay.DAY

            # Convert panels
            panels = []
            for panel_resp in scene_resp.panels:
                # Parse shot type
                try:
                    shot_type = ShotType(panel_resp.shot_type.lower())
                except ValueError:
                    shot_type = ShotType.MEDIUM

                # Parse angle
                try:
                    angle = CameraAngle(panel_resp.angle.lower())
                except ValueError:
                    angle = CameraAngle.EYE_LEVEL

                # Build expression lookup from character_expressions
                expr_lookup = {
                    ce.character_name.lower(): ce.expression
                    for ce in panel_resp.character_expressions
                }

                # Build panel characters
                panel_chars = []
                for i, char_name in enumerate(panel_resp.characters):
                    char_key = char_name.lower()
                    for name, char in char_by_name.items():
                        if char_key in name or name in char_key:
                            # Look up expression from character_expressions
                            expr = expr_lookup.get(char_key, "neutral")
                            position = ["left", "center", "right"][i % 3]
                            panel_chars.append(
                                PanelCharacter(
                                    character_id=char.id,
                                    expression=expr,
                                    position=position,
                                )
                            )
                            break

                # Build dialogue
                dialogue = []
                for dial_resp in panel_resp.dialogue:
                    char_id = None
                    if dial_resp.character_name:
                        char_key = dial_resp.character_name.lower()
                        for name, char in char_by_name.items():
                            if char_key in name or name in char_key:
                                char_id = char.id
                                break

                    try:
                        dial_type = DialogueType(dial_resp.type.lower())
                    except ValueError:
                        dial_type = DialogueType.SPEECH

                    dialogue.append(
                        Dialogue(
                            character_id=char_id,
                            text=dial_resp.text,
                            type=dial_type,
                        )
                    )

                panels.append(
                    Panel(
                        number=panel_resp.number,
                        composition=PanelComposition(
                            shot_type=shot_type,
                            angle=angle,
                        ),
                        characters=panel_chars,
                        action=panel_resp.action,
                        dialogue=dialogue,
                        sfx=panel_resp.sfx,
                        continues_from_previous=panel_resp.continues_from_previous,
                        continuity_note=panel_resp.continuity_note,
                    )
                )

            scene = Scene(
                number=scene_resp.number,
                location_id=loc_id,
                time_of_day=time_of_day,
                mood=scene_resp.mood,
                description=scene_resp.description,
                character_ids=char_ids,
                panels=panels,
            )
            # Set cross-chapter continuity for first scene
            if scene_resp.number == 1:
                scene.continues_from_previous_chapter = scene_resp.continues_from_previous_chapter
            scenes.append(scene)

        return Chapter(
            number=response.number,
            title=response.title,
            summary=response.summary,
            status=ChapterStatus.OUTLINED,
            scenes=scenes,
        )

    async def generate_all_chapters(
        self,
        story: Story,
        characters: list[Character],
        locations: list[Location],
        existing_chapters: Optional[list[Chapter]] = None,
        panels_per_scene: int = 6,
        on_chapter_complete: Optional[callable] = None,
    ) -> list[Chapter]:
        """Generate chapters for all story beats sequentially.

        Each chapter is generated with context from all previous chapters
        to maintain story continuity.

        Args:
            story: The full story
            characters: Available characters
            locations: Available locations
            existing_chapters: Already generated chapters to continue from
            panels_per_scene: Target panels per scene
            on_chapter_complete: Optional callback(chapter) called after each chapter

        Returns:
            List of all chapters (existing + newly generated)
        """
        chapters = list(existing_chapters) if existing_chapters else []
        existing_numbers = {c.number for c in chapters}

        for i, beat in enumerate(story.story_beats, start=1):
            # Skip if already generated
            if i in existing_numbers:
                continue

            # Generate with all previous chapters as context
            chapter = await self.generate_chapter(
                story=story,
                beat=beat,
                chapter_number=i,
                characters=characters,
                locations=locations,
                previous_chapters=chapters,  # Pass all previous for continuity
                panels_per_scene=panels_per_scene,
            )
            chapters.append(chapter)

            # Callback for progress reporting / saving
            if on_chapter_complete:
                on_chapter_complete(chapter)

        return chapters
