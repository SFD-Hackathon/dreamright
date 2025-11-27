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
    ) -> dict:
        """Generate character portrait asset.

        Args:
            character_id: Character ID
            style: Art style
            overwrite: Whether to overwrite existing
            on_start: Callback when generation starts
            on_complete: Callback when generation completes

        Returns:
            Generation result with path

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

        # Generate
        generator = CharacterGenerator()
        image_data, gen_info = await generator.generate_portrait(
            char,
            style=style,
            overwrite_cache=overwrite,
        )

        # Save
        metadata = {
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
            "gemini": gen_info,
        }

        path = self.manager.save_asset(
            char_folder,
            "portrait.png",
            image_data,
            metadata=metadata,
        )
        char.assets.portrait = path
        self.manager.save()

        # Notify complete
        if on_complete:
            on_complete(char, path)

        return {
            "character_id": char.id,
            "path": path,
            "style": style,
        }

    async def generate_all_assets(
        self,
        style: str = "webtoon",
        overwrite: bool = False,
        on_start: Optional[OnCharacterStart] = None,
        on_complete: Optional[OnCharacterComplete] = None,
        on_skip: Optional[OnCharacterSkip] = None,
    ) -> list[dict]:
        """Generate assets for all characters without portraits.

        Args:
            style: Art style
            overwrite: Whether to overwrite existing
            on_start: Callback when generation starts for each character
            on_complete: Callback when generation completes for each character
            on_skip: Callback when character is skipped

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
                )
                results.append(result)
        return results
