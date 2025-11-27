"""Panel/segment image generator."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from dreamright_gemini_client import GeminiClient
from dreamright_core_schemas import (
    CameraAngle,
    Chapter,
    Character,
    Location,
    Panel,
    PanelCharacter,
    Scene,
    ShotType,
    TimeOfDay,
)
from dreamright_generators.templates import render
from dreamright_generators.templates.panel import PANEL_PROMPT, SPLASH_PROMPT, TRANSITION_PROMPT


@dataclass
class PanelResult:
    """Result of generating a single panel."""

    panel: Panel
    image_data: Optional[bytes]
    metadata: Optional[dict]
    error: Optional[str]
    skipped: bool = False


@dataclass
class SceneResult:
    """Result of generating all panels in a scene."""

    scene: Scene
    panels: list[PanelResult]

    @property
    def generated_count(self) -> int:
        return sum(1 for p in self.panels if p.image_data and not p.skipped)

    @property
    def skipped_count(self) -> int:
        return sum(1 for p in self.panels if p.skipped)

    @property
    def error_count(self) -> int:
        return sum(1 for p in self.panels if p.error)


@dataclass
class ChapterResult:
    """Result of generating all panels in a chapter."""

    chapter: Chapter
    scenes: list[SceneResult]

    @property
    def generated_count(self) -> int:
        return sum(s.generated_count for s in self.scenes)

    @property
    def skipped_count(self) -> int:
        return sum(s.skipped_count for s in self.scenes)

    @property
    def error_count(self) -> int:
        return sum(s.error_count for s in self.scenes)

    @property
    def total_panels(self) -> int:
        return sum(len(s.panels) for s in self.scenes)


class PanelGenerator:
    """Generates webtoon panel images."""

    def __init__(self, client: Optional[GeminiClient] = None):
        """Initialize the panel generator.

        Args:
            client: Gemini client (uses global client if not provided)
        """
        if client is None:
            from dreamright_gemini_client import get_client

            client = get_client()
        self.client = client

    def _get_shot_description(self, shot_type: ShotType) -> str:
        """Get description for shot type."""
        descriptions = {
            ShotType.WIDE: "wide establishing shot showing full environment and characters",
            ShotType.MEDIUM: "medium shot showing characters from waist up",
            ShotType.CLOSE_UP: "close-up shot focusing on face and expressions",
            ShotType.EXTREME_CLOSE_UP: "extreme close-up on specific detail (eyes, hands, object)",
        }
        return descriptions.get(shot_type, "medium shot")

    def _get_angle_description(self, angle: CameraAngle) -> str:
        """Get description for camera angle."""
        descriptions = {
            CameraAngle.EYE_LEVEL: "eye level, straight on view",
            CameraAngle.HIGH: "high angle looking down, shows vulnerability or overview",
            CameraAngle.LOW: "low angle looking up, shows power or grandeur",
            CameraAngle.DUTCH: "dutch angle (tilted), creates tension or unease",
        }
        return descriptions.get(angle, "eye level")

    def _build_character_description(
        self,
        panel_char: PanelCharacter,
        character: Optional[Character],
    ) -> str:
        """Build description for a character in the panel.

        Includes FULL appearance details to ensure costume/look consistency.
        """
        lines = []

        if character:
            lines.append(f"**{character.name}** (MUST match reference image exactly)")

            # Include physical description for appearance consistency
            if character.description.physical:
                lines.append(f"  Appearance: {character.description.physical}")

            # Include ALL visual tags for costume/appearance consistency
            if character.visual_tags:
                lines.append(f"  Visual details: {', '.join(character.visual_tags)}")
        else:
            lines.append("Character")

        # Panel-specific attributes
        lines.append(f"  Expression: {panel_char.expression}")

        if panel_char.pose:
            lines.append(f"  Pose: {panel_char.pose}")

        lines.append(f"  Position: {panel_char.position} of frame")

        return "\n".join(lines)

    async def generate_panel(
        self,
        panel: Panel,
        characters: Optional[dict[str, Character]] = None,
        location: Optional[Location] = None,
        time_of_day: TimeOfDay = TimeOfDay.DAY,
        character_references: Optional[dict[str, Path]] = None,
        location_reference: Optional[Path] = None,
        previous_panel_image: Optional[Path] = None,
        style: str = "webtoon",
        resolution: str = "1K",
        scene_number: Optional[int] = None,
        chapter_number: Optional[int] = None,
        overwrite_cache: bool = False,
    ) -> tuple[bytes, dict]:
        """Generate a single panel image.

        Args:
            panel: Panel specification
            characters: Dict of character_id -> Character for characters in panel
            location: Location for the background
            time_of_day: Time of day for lighting
            character_references: Dict of character_id -> reference image path
            location_reference: Reference image for location
            previous_panel_image: Path to previous panel image (for continuity)
            style: Art style
            resolution: Image resolution (1K, 2K, 4K)
            scene_number: Scene number for organizing output
            chapter_number: Chapter number for organizing output

        Returns:
            Tuple of (image_data, generation_info) where generation_info contains
            the prompt, parameters, references, and response metadata
        """
        characters = characters or {}

        # Build character descriptions
        char_descriptions = []
        for panel_char in panel.characters:
            char = characters.get(panel_char.character_id)
            char_descriptions.append(self._build_character_description(panel_char, char))

        # Render prompt from template
        prompt = render(
            PANEL_PROMPT,
            style=style,
            continuity=panel.continues_from_previous and previous_panel_image,
            continuity_note=panel.continuity_note,
            shot_description=self._get_shot_description(panel.composition.shot_type),
            angle_description=self._get_angle_description(panel.composition.angle),
            location=location,
            time_of_day=time_of_day.value,
            characters=char_descriptions if panel.characters else None,
            action=panel.action,
        )

        # Gather reference images with their roles
        references: list[tuple[Path, str]] = []

        # Add previous panel as first reference for continuity
        if panel.continues_from_previous and previous_panel_image and previous_panel_image.exists():
            references.append((previous_panel_image, "previous panel for visual continuity"))

        # Add character references
        if character_references:
            for panel_char in panel.characters:
                char_id = panel_char.character_id
                if char_id in character_references:
                    char = characters.get(char_id) if characters else None
                    char_name = char.name if char else char_id
                    references.append(
                        (character_references[char_id], f"character reference for {char_name}")
                    )

        # Add location reference
        if location_reference:
            references.append((location_reference, "location/background reference"))

        # Determine aspect ratio based on panel type (webtoon = vertical scroll)
        if panel.type == "splash":
            aspect_ratio = "9:16"  # Full vertical for splash pages
        else:
            aspect_ratio = "3:4"  # Vertical panel for webtoon scrolling

        # Generate image
        image_data, response_metadata = await self.client.generate_image(
            prompt=prompt,
            reference_images=references if references else None,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            style=style,
            overwrite_cache=overwrite_cache,
        )

        # Build generation info metadata
        generation_info = {
            "type": "panel",
            "panel_id": panel.id,
            "panel_number": panel.number,
            "scene_number": scene_number,
            "chapter_number": chapter_number,
            "prompt": prompt,
            "parameters": {
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "style": style,
                "panel_type": panel.type,
                "model": self.client.image_model,
            },
            "references": [
                {"path": str(path), "role": role} for path, role in references
            ] if references else [],
            "panel_data": {
                "action": panel.action,
                "composition": {
                    "shot_type": panel.composition.shot_type.value if panel.composition.shot_type else None,
                    "angle": panel.composition.angle.value if panel.composition.angle else None,
                },
                "characters": [
                    {
                        "character_id": pc.character_id,
                        "expression": pc.expression,
                        "position": pc.position,
                    }
                    for pc in panel.characters
                ] if panel.characters else [],
                "continues_from_previous": panel.continues_from_previous,
                "continuity_note": panel.continuity_note,
            },
            "location_id": location.id if location else None,
            "location_name": location.name if location else None,
            "time_of_day": time_of_day.value,
            "response": response_metadata,
        }

        return image_data, generation_info

    async def generate_transition_panel(
        self,
        from_description: str,
        to_description: str,
        transition_type: str = "fade",
        style: str = "webtoon",
        resolution: str = "1K",
    ) -> bytes:
        """Generate a transition panel between scenes.

        Args:
            from_description: Description of the previous scene
            to_description: Description of the next scene
            transition_type: Type of transition (fade, wipe, cut, etc.)
            style: Art style
            resolution: Image resolution (1K, 2K, 4K)

        Returns:
            Image data as bytes (PNG)
        """
        prompt = render(
            TRANSITION_PROMPT,
            style=style,
            transition_type=transition_type,
            from_description=from_description,
            to_description=to_description,
        )

        return await self.client.generate_image(
            prompt=prompt,
            aspect_ratio="1:1",
            resolution=resolution,
            style=style,
        )

    async def generate_splash_panel(
        self,
        description: str,
        characters: Optional[list[Character]] = None,
        location: Optional[Location] = None,
        mood: str = "dramatic",
        style: str = "webtoon",
        resolution: str = "1K",
    ) -> bytes:
        """Generate a full-page splash panel.

        Args:
            description: Description of the splash scene
            characters: Characters to include
            location: Location for the scene
            mood: Emotional mood of the scene
            style: Art style
            resolution: Image resolution (1K, 2K, 4K)

        Returns:
            Image data as bytes (PNG)
        """
        prompt = render(
            SPLASH_PROMPT,
            style=style,
            description=description,
            mood=mood,
            location=location,
            characters=characters,
        )

        return await self.client.generate_image(
            prompt=prompt,
            aspect_ratio="9:16",
            resolution=resolution,
            style=style,
        )

    async def generate_scene_panels(
        self,
        scene: Scene,
        chapter_number: int,
        characters: dict[str, Character],
        locations: dict[str, Location],
        character_references: dict[str, Path],
        location_references: dict[str, Path],
        output_dir: Path,
        style: str = "webtoon",
        overwrite: bool = False,
        on_panel_start: Optional[Callable[[Panel], None]] = None,
        on_panel_complete: Optional[Callable[[PanelResult], None]] = None,
        initial_previous_panel: Optional[Path] = None,
    ) -> SceneResult:
        """Generate all panels for a scene sequentially.

        Panels are generated sequentially (not parallel) because panel N
        may depend on panel N-1 for visual continuity.

        Args:
            scene: Scene containing panels to generate
            chapter_number: Chapter number for output organization
            characters: Dict of character_id -> Character
            locations: Dict of location_id -> Location
            character_references: Dict of character_id -> portrait image path
            location_references: Dict of location_id -> reference image path
            output_dir: Base output directory for assets
            style: Art style
            overwrite: If True, regenerate even if panel exists
            on_panel_start: Callback when starting a panel
            on_panel_complete: Callback when panel completes
            initial_previous_panel: Path to use as previous panel for first panel
                (used for cross-chapter continuity)

        Returns:
            SceneResult with all panel results
        """
        panel_results: list[PanelResult] = []

        # Get location for this scene
        location = locations.get(scene.location_id) if scene.location_id else None
        location_ref = location_references.get(scene.location_id) if scene.location_id else None

        # Track previous panel path for continuity
        # Start with initial_previous_panel if provided (cross-chapter continuity)
        previous_panel_path: Optional[Path] = initial_previous_panel

        # Generate panels SEQUENTIALLY for continuity
        for panel in scene.panels:
            if on_panel_start:
                on_panel_start(panel)

            # Determine output path
            panel_folder = output_dir / f"panels/chapter-{chapter_number}/scene-{scene.number}"
            panel_folder.mkdir(parents=True, exist_ok=True)
            panel_path = panel_folder / f"panel-{panel.number}.png"
            metadata_path = panel_folder / f"panel-{panel.number}.json"

            # Check if already exists
            if panel_path.exists() and not overwrite:
                panel.image_path = str(panel_path.relative_to(output_dir.parent))
                result = PanelResult(
                    panel=panel,
                    image_data=None,
                    metadata=None,
                    error=None,
                    skipped=True,
                )
                previous_panel_path = panel_path
                panel_results.append(result)
                if on_panel_complete:
                    on_panel_complete(result)
                continue

            # Build character references for this panel
            panel_characters = {
                pc.character_id: characters[pc.character_id]
                for pc in panel.characters
                if pc.character_id in characters
            }
            panel_char_refs = {
                pc.character_id: character_references[pc.character_id]
                for pc in panel.characters
                if pc.character_id in character_references
            }

            # Determine if we should use previous panel for continuity
            # - For panels after the first: use continues_from_previous flag
            # - For first panel with initial_previous_panel: always use it (cross-chapter continuity)
            use_previous = False
            if panel.continues_from_previous and previous_panel_path:
                use_previous = True
            elif panel.number == 1 and initial_previous_panel and previous_panel_path == initial_previous_panel:
                # First panel with cross-chapter continuity
                use_previous = True

            try:
                image_data, metadata = await self.generate_panel(
                    panel=panel,
                    characters=panel_characters,
                    location=location,
                    time_of_day=scene.time_of_day,
                    character_references=panel_char_refs,
                    location_reference=location_ref,
                    previous_panel_image=previous_panel_path if use_previous else None,
                    style=style,
                    scene_number=scene.number,
                    chapter_number=chapter_number,
                    overwrite_cache=overwrite,
                )

                # Save panel image
                with open(panel_path, "wb") as f:
                    f.write(image_data)

                # Save metadata
                import json
                from datetime import datetime
                metadata["generated_at"] = datetime.now().isoformat()
                with open(metadata_path, "w") as f:
                    json.dump(metadata, f, indent=2)

                panel.image_path = str(panel_path.relative_to(output_dir.parent))
                previous_panel_path = panel_path

                result = PanelResult(
                    panel=panel,
                    image_data=image_data,
                    metadata=metadata,
                    error=None,
                )

            except Exception as e:
                result = PanelResult(
                    panel=panel,
                    image_data=None,
                    metadata=None,
                    error=str(e),
                )

            panel_results.append(result)
            if on_panel_complete:
                on_panel_complete(result)

        return SceneResult(scene=scene, panels=panel_results)

    async def generate_chapter_panels(
        self,
        chapter: Chapter,
        characters: dict[str, Character],
        locations: dict[str, Location],
        character_references: dict[str, Path],
        location_references: dict[str, Path],
        output_dir: Path,
        style: str = "webtoon",
        overwrite: bool = False,
        previous_chapter_last_panel: Optional[Path] = None,
        on_scene_start: Optional[Callable[[Scene], None]] = None,
        on_panel_start: Optional[Callable[[Panel], None]] = None,
        on_panel_complete: Optional[Callable[[PanelResult], None]] = None,
        on_scene_complete: Optional[Callable[[SceneResult], None]] = None,
    ) -> ChapterResult:
        """Generate all panels for a chapter.

        Scenes are processed sequentially, and within each scene,
        panels are generated sequentially for visual continuity.

        Args:
            chapter: Chapter containing scenes and panels
            characters: Dict of character_id -> Character
            locations: Dict of location_id -> Location
            character_references: Dict of character_id -> portrait image path
            location_references: Dict of location_id -> reference image path
            output_dir: Base output directory for assets
            style: Art style
            overwrite: If True, regenerate even if panels exist
            previous_chapter_last_panel: Path to last panel of previous chapter
                (used if first scene has continues_from_previous_chapter=True)
            on_scene_start: Callback when starting a scene
            on_panel_start: Callback when starting a panel
            on_panel_complete: Callback when panel completes
            on_scene_complete: Callback when scene completes

        Returns:
            ChapterResult with all scene and panel results
        """
        scene_results: list[SceneResult] = []

        for i, scene in enumerate(chapter.scenes):
            if on_scene_start:
                on_scene_start(scene)

            # For first scene, check if it continues from previous chapter
            initial_previous_panel = None
            if i == 0 and scene.continues_from_previous_chapter and previous_chapter_last_panel:
                initial_previous_panel = previous_chapter_last_panel

            scene_result = await self.generate_scene_panels(
                scene=scene,
                chapter_number=chapter.number,
                characters=characters,
                locations=locations,
                character_references=character_references,
                location_references=location_references,
                output_dir=output_dir,
                style=style,
                overwrite=overwrite,
                on_panel_start=on_panel_start,
                on_panel_complete=on_panel_complete,
                initial_previous_panel=initial_previous_panel,
            )

            scene_results.append(scene_result)
            if on_scene_complete:
                on_scene_complete(scene_result)

        return ChapterResult(chapter=chapter, scenes=scene_results)
