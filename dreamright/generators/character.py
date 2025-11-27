"""Character asset generator."""

from pathlib import Path
from typing import Optional

from ..gemini_client import GeminiClient
from ..models import Character


class CharacterGenerator:
    """Generates character visual assets."""

    def __init__(self, client: Optional[GeminiClient] = None):
        """Initialize the character generator.

        Args:
            client: Gemini client (uses global client if not provided)
        """
        if client is None:
            from ..gemini_client import get_client

            client = get_client()
        self.client = client

    def _build_character_prompt(self, character: Character, base_prompt: str) -> str:
        """Build a detailed prompt for character generation.

        Args:
            character: Character model
            base_prompt: Base prompt to append details to

        Returns:
            Full prompt string
        """
        parts = [base_prompt]

        # Add character details
        parts.append(f"\nCharacter: {character.name}")

        if character.age:
            parts.append(f"Age: {character.age}")

        if character.description.physical:
            parts.append(f"Physical appearance: {character.description.physical}")

        if character.visual_tags:
            parts.append(f"Visual details: {', '.join(character.visual_tags)}")

        if character.description.personality:
            parts.append(f"Personality (for expression): {character.description.personality}")

        return "\n".join(parts)

    async def generate_character_sheet(
        self,
        character: Character,
        reference_image: Optional[Path] = None,
        style: str = "webtoon",
        resolution: str = "1K",
        overwrite_cache: bool = False,
    ) -> tuple[bytes, dict]:
        """Generate a full-body three-view character sheet (front, side, back in one image).

        This is the DEFAULT method for character generation as it provides the best
        reference for panel generation with consistent costume/appearance.

        Args:
            character: Character to generate sheet for
            reference_image: Optional reference image for consistency
            style: Art style (webtoon, anime, realistic, etc.)
            resolution: Image resolution (1K, 2K, 4K)

        Returns:
            Tuple of (image_data, generation_info)
        """
        base_prompt = f"""Create a CHARACTER TURNAROUND SHEET in {style} art style.

## LAYOUT
Create a SINGLE IMAGE showing the SAME character THREE times side by side:
- LEFT: Full body FRONT view (facing viewer)
- CENTER: Full body SIDE view (profile, facing right)
- RIGHT: Full body BACK view (facing away)

## REQUIREMENTS
- All three views show the EXACT SAME character with IDENTICAL outfit
- Full body from head to feet in each view
- Relaxed standing pose (arms slightly away from body to show costume)
- Clean white or light gray background
- Character sheet/model sheet style for animation reference
- All views at the same scale and aligned at feet level
- Show clothing, hair, and accessories clearly from all angles
- Professional quality suitable for production reference

## CONSISTENCY IS CRITICAL
- Same hair style/color in all views
- Same outfit in all views (every detail must match)
- Same accessories and items in all views
- Same body proportions in all views
"""

        prompt = self._build_character_prompt(character, base_prompt)

        refs = (
            [(reference_image, f"existing reference of {character.name} - match appearance exactly")]
            if reference_image
            else None
        )

        # Use 16:9 landscape for three-view layout
        image_data, response_metadata = await self.client.generate_image(
            prompt=prompt,
            reference_images=refs,
            aspect_ratio="16:9",
            resolution=resolution,
            style=style,
            overwrite_cache=overwrite_cache,
        )

        generation_info = {
            "type": "character_sheet",
            "character_id": character.id,
            "character_name": character.name,
            "prompt": prompt,
            "parameters": {
                "aspect_ratio": "16:9",
                "resolution": resolution,
                "style": style,
                "model": self.client.image_model,
                "reference_image": str(reference_image) if reference_image else None,
            },
            "response": response_metadata,
        }

        return image_data, generation_info

    async def generate_portrait(
        self,
        character: Character,
        reference_image: Optional[Path] = None,
        style: str = "webtoon",
        aspect_ratio: str = "9:16",
        resolution: str = "1K",
        overwrite_cache: bool = False,
    ) -> tuple[bytes, dict]:
        """Generate a character portrait (upper body, single view).

        NOTE: For panel generation reference, use generate_character_sheet() instead
        as it provides front/side/back views for better consistency.

        Args:
            character: Character to generate portrait for
            reference_image: Optional reference image for consistency
            style: Art style (webtoon, anime, realistic, etc.)
            aspect_ratio: Image aspect ratio (default 9:16 for vertical portrait)
            resolution: Image resolution (1K, 2K, 4K)

        Returns:
            Tuple of (image_data, generation_info)
        """
        base_prompt = f"""Create a character portrait in {style} art style.

Requirements:
- Upper body portrait (head to waist or chest)
- Neutral expression showing character's personality
- Clean background (solid color or simple gradient)
- High quality, detailed illustration
- Consistent with webtoon/manhwa aesthetic
- Front-facing, looking slightly towards viewer
- Vertical composition suitable for character card
"""

        prompt = self._build_character_prompt(character, base_prompt)

        refs = (
            [(reference_image, f"existing portrait of {character.name} for consistency")]
            if reference_image
            else None
        )
        image_data, response_metadata = await self.client.generate_image(
            prompt=prompt,
            reference_images=refs,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            style=style,
            overwrite_cache=overwrite_cache,
        )

        generation_info = {
            "type": "character_portrait",
            "character_id": character.id,
            "character_name": character.name,
            "prompt": prompt,
            "parameters": {
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "style": style,
                "model": self.client.image_model,
                "reference_image": str(reference_image) if reference_image else None,
            },
            "response": response_metadata,
        }

        return image_data, generation_info

    async def generate_three_view(
        self,
        character: Character,
        reference_image: Optional[Path] = None,
        style: str = "webtoon",
        resolution: str = "1K",
        overwrite_cache: bool = False,
    ) -> dict[str, tuple[bytes, dict]]:
        """Generate three-view character sheet (front, side, back).

        Args:
            character: Character to generate views for
            reference_image: Optional reference image for consistency
            style: Art style
            resolution: Image resolution (1K, 2K, 4K)

        Returns:
            Dict with 'front', 'side', 'back' keys containing (image_bytes, generation_info)
        """
        views = {}
        refs = (
            [(reference_image, f"reference image of {character.name} for consistency")]
            if reference_image
            else None
        )

        for view in ["front", "side", "back"]:
            base_prompt = f"""Create a full-body character reference in {style} art style.

Requirements:
- Full body {view} view
- T-pose or relaxed standing pose
- Clean white/light gray background
- Character sheet style for animation reference
- Consistent proportions and details
- Show clothing and accessories clearly
"""

            prompt = self._build_character_prompt(character, base_prompt)

            image_data, response_metadata = await self.client.generate_image(
                prompt=prompt,
                reference_images=refs,
                aspect_ratio="3:4",
                resolution=resolution,
                style=style,
                overwrite_cache=overwrite_cache,
            )

            generation_info = {
                "type": "character_three_view",
                "character_id": character.id,
                "character_name": character.name,
                "view": view,
                "prompt": prompt,
                "parameters": {
                    "aspect_ratio": "3:4",
                    "resolution": resolution,
                    "style": style,
                    "model": self.client.image_model,
                    "reference_image": str(reference_image) if reference_image else None,
                },
                "response": response_metadata,
            }

            views[view] = (image_data, generation_info)

        return views
