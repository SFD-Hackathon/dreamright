"""Character management service."""

from pathlib import Path
from typing import Callable, Optional

from ..generators.character import CharacterGenerator
from ..models import Character, CharacterDescription, CharacterRole
from ..storage import ProjectManager, slugify
from .exceptions import AssetExistsError, NotFoundError

# Callback type aliases for progress reporting
OnCharacterStart = Callable[[Character], None]
OnCharacterComplete = Callable[[Character, str], None]  # character, path
OnCharacterSkip = Callable[[Character, str], None]  # character, reason


class CharacterService:
    """Service for character management operations."""

    def __init__(self, manager: ProjectManager):
        """Initialize service with a project manager."""
        self.manager = manager

    def list_characters(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Character], int]:
        """List all characters with pagination.

        Returns:
            Tuple of (characters, total_count)
        """
        characters = self.manager.project.characters
        total = len(characters)
        return characters[offset:offset + limit], total

    def get_character(self, character_id: str) -> Character:
        """Get character by ID.

        Raises:
            NotFoundError: If character not found
        """
        char = self.manager.project.get_character_by_id(character_id)
        if not char:
            raise NotFoundError("Character", character_id)
        return char

    def get_character_by_name(self, name: str) -> Character:
        """Get character by name.

        Raises:
            NotFoundError: If character not found
        """
        char = self.manager.project.get_character_by_name(name)
        if not char:
            raise NotFoundError("Character", name)
        return char

    def create_character(
        self,
        name: str,
        role: CharacterRole = CharacterRole.SUPPORTING,
        age: str = "",
        description: Optional[CharacterDescription] = None,
        visual_tags: Optional[list[str]] = None,
    ) -> Character:
        """Create a new character.

        Returns:
            Created character
        """
        char = Character(
            name=name,
            role=role,
            age=age,
            description=description or CharacterDescription(),
            visual_tags=visual_tags or [],
        )
        self.manager.project.characters.append(char)
        self.manager.save()
        return char

    def update_character(
        self,
        character_id: str,
        name: Optional[str] = None,
        role: Optional[CharacterRole] = None,
        age: Optional[str] = None,
        description: Optional[CharacterDescription] = None,
        visual_tags: Optional[list[str]] = None,
    ) -> Character:
        """Update a character.

        Returns:
            Updated character
        """
        char = self.get_character(character_id)

        if name is not None:
            char.name = name
        if role is not None:
            char.role = role
        if age is not None:
            char.age = age
        if description is not None:
            char.description = description
        if visual_tags is not None:
            char.visual_tags = visual_tags

        self.manager.save()
        return char

    def delete_character(self, character_id: str) -> bool:
        """Delete a character.

        Returns:
            True if deleted
        """
        chars = self.manager.project.characters
        for i, char in enumerate(chars):
            if char.id == character_id:
                chars.pop(i)
                self.manager.save()
                return True
        return False

    def get_assets(self, character_id: str) -> dict:
        """Get character assets metadata.

        Returns:
            Assets metadata dict
        """
        char = self.get_character(character_id)
        return {
            "character_id": char.id,
            "portrait": char.assets.portrait,
            "three_view": char.assets.three_view,
            "reference_input": char.assets.reference_input,
        }

    def check_asset_exists(self, character_id: str) -> Optional[str]:
        """Check if character portrait asset exists.

        Returns:
            Path to existing asset, or None
        """
        char = self.get_character(character_id)
        if not char.assets.portrait:
            return None

        portrait_path = self.manager.storage.get_absolute_asset_path(char.assets.portrait)
        if portrait_path.exists():
            return char.assets.portrait
        return None

    async def generate_asset(
        self,
        character_id: str,
        style: str = "webtoon",
        overwrite: bool = False,
        on_start: Optional[OnCharacterStart] = None,
        on_complete: Optional[OnCharacterComplete] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> dict:
        """Generate character reference assets (portrait + full-body three-view).

        Two-step process for best consistency:
        1. Generate portrait first (establishes face and features)
        2. Use portrait as reference to generate three-view character sheet

        Args:
            character_id: Character ID
            style: Art style
            overwrite: Whether to overwrite existing
            on_start: Callback when generation starts
            on_complete: Callback when generation completes
            on_progress: Callback for progress updates (step description)

        Returns:
            Generation result with paths

        Raises:
            AssetExistsError: If asset exists and overwrite is False
        """
        char = self.get_character(character_id)
        char_slug = slugify(char.name)
        char_folder = f"characters/{char_slug}"

        # Check existing
        if not overwrite:
            existing = self.check_asset_exists(character_id)
            if existing:
                raise AssetExistsError("character", char.name, existing)

        # Notify start
        if on_start:
            on_start(char)

        generator = CharacterGenerator()

        # Step 1: Generate portrait first (establishes the face/look)
        if on_progress:
            on_progress("Step 1/2: Generating portrait...")

        portrait_data, portrait_info = await generator.generate_portrait(
            char,
            style=style,
            overwrite_cache=overwrite,
        )

        # Save portrait
        portrait_metadata = {
            "type": "character",
            "character_id": char.id,
            "character_name": char.name,
            "role": char.role.value,
            "age": char.age,
            "style": style,
            "visual_tags": char.visual_tags,
            "description": {
                "physical": char.description.physical,
                "personality": char.description.personality,
            },
            "asset_type": "portrait",
            "gemini": portrait_info,
        }

        portrait_path = self.manager.save_asset(
            char_folder,
            "portrait.png",
            portrait_data,
            metadata=portrait_metadata,
        )
        char.assets.portrait = portrait_path

        # Step 2: Generate three-view character sheet using portrait as reference
        if on_progress:
            on_progress("Step 2/2: Generating full-body three-view using portrait as reference...")

        portrait_abs_path = self.manager.storage.get_absolute_asset_path(portrait_path)

        sheet_data, sheet_info = await generator.generate_character_sheet(
            char,
            reference_image=portrait_abs_path,  # Use portrait for consistency
            style=style,
            overwrite_cache=overwrite,
        )

        # Save character sheet
        sheet_metadata = {
            "type": "character",
            "character_id": char.id,
            "character_name": char.name,
            "role": char.role.value,
            "age": char.age,
            "style": style,
            "visual_tags": char.visual_tags,
            "description": {
                "physical": char.description.physical,
                "personality": char.description.personality,
            },
            "asset_type": "character_sheet",
            "reference_portrait": portrait_path,
            "gemini": sheet_info,
        }

        sheet_path = self.manager.save_asset(
            char_folder,
            "sheet.png",  # Three-view character sheet
            sheet_data,
            metadata=sheet_metadata,
        )
        # Store the sheet path in three_view for panel generation reference
        char.assets.three_view["sheet"] = sheet_path

        self.manager.save()

        # Notify complete
        if on_complete:
            on_complete(char, sheet_path)

        return {
            "character_id": char.id,
            "portrait_path": portrait_path,
            "sheet_path": sheet_path,
            "style": style,
        }

    async def generate_all_assets(
        self,
        style: str = "webtoon",
        overwrite: bool = False,
        on_start: Optional[OnCharacterStart] = None,
        on_complete: Optional[OnCharacterComplete] = None,
        on_skip: Optional[OnCharacterSkip] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> list[dict]:
        """Generate assets for all characters (portrait + three-view sheet).

        Args:
            style: Art style
            overwrite: Whether to overwrite existing
            on_start: Callback when generation starts for each character
            on_complete: Callback when generation completes for each character
            on_skip: Callback when character is skipped
            on_progress: Callback for progress updates

        Returns:
            List of generation results
        """
        results = []
        for char in self.manager.project.characters:
            existing = self.check_asset_exists(char.id)
            if existing and not overwrite:
                if on_skip:
                    on_skip(char, "asset_exists")
                results.append({
                    "character_id": char.id,
                    "skipped": True,
                    "reason": "asset_exists",
                    "path": existing,
                })
            else:
                result = await self.generate_asset(
                    char.id,
                    style=style,
                    overwrite=overwrite,
                    on_start=on_start,
                    on_complete=on_complete,
                    on_progress=on_progress,
                )
                results.append(result)
        return results
