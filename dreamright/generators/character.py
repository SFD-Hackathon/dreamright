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

    async def generate_portrait(
        self,
        character: Character,
        reference_image: Optional[Path] = None,
        style: str = "webtoon",
        aspect_ratio: str = "9:16",
        resolution: str = "1K",
        overwrite_cache: bool = False,
    ) -> tuple[bytes, dict]:
        """Generate a character portrait.

        Args:
            character: Character to generate portrait for
            reference_image: Optional reference image for consistency
            style: Art style (webtoon, anime, realistic, etc.)
            aspect_ratio: Image aspect ratio (default 9:16 for vertical portrait)
            resolution: Image resolution (1K, 2K, 4K)

        Returns:
            Tuple of (image_data, generation_info) where generation_info contains
            the prompt and parameters used
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
