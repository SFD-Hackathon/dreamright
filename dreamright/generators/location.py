"""Location asset generator."""

from typing import Optional

from ..gemini_client import GeminiClient
from ..models import Location


class LocationGenerator:
    """Generates location/background visual assets."""

    def __init__(self, client: Optional[GeminiClient] = None):
        """Initialize the location generator.

        Args:
            client: Gemini client (uses global client if not provided)
        """
        if client is None:
            from ..gemini_client import get_client

            client = get_client()
        self.client = client

    def _build_location_prompt(self, location: Location, base_prompt: str) -> str:
        """Build a detailed prompt for location generation.

        Args:
            location: Location model
            base_prompt: Base prompt to append details to

        Returns:
            Full prompt string
        """
        parts = [base_prompt]

        # Add location details
        parts.append(f"\nLocation: {location.name}")
        parts.append(f"Type: {location.type.value}")

        if location.description:
            parts.append(f"Description: {location.description}")

        if location.visual_tags:
            parts.append(f"Visual details: {', '.join(location.visual_tags)}")

        return "\n".join(parts)

    async def generate_reference(
        self,
        location: Location,
        style: str = "webtoon",
        aspect_ratio: str = "16:9",
        resolution: str = "1K",
        overwrite_cache: bool = False,
    ) -> tuple[bytes, dict]:
        """Generate a location reference image.

        Args:
            location: Location to generate
            style: Art style
            aspect_ratio: Image aspect ratio (default 16:9 for wide backgrounds)
            resolution: Image resolution (1K, 2K, 4K)
            overwrite_cache: Bypass cache and regenerate

        Returns:
            Tuple of (image_data, generation_info) where generation_info contains
            the prompt and parameters used
        """
        base_prompt = f"""Create a background/environment illustration in {style} art style.

Requirements:
- Establishing shot of the location
- Bright daylight, clear visibility, natural lighting
- Clear sky
- No characters in the scene
- Detailed environment suitable for webtoon backgrounds
- Wide composition showing the space
- Atmospheric and immersive
"""

        prompt = self._build_location_prompt(location, base_prompt)

        image_data, response_metadata = await self.client.generate_image(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            style=style,
            overwrite_cache=overwrite_cache,
        )

        generation_info = {
            "type": "location_reference",
            "location_id": location.id,
            "location_name": location.name,
            "location_type": location.type.value,
            "prompt": prompt,
            "parameters": {
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "style": style,
                "model": self.client.image_model,
            },
            "response": response_metadata,
        }

        return image_data, generation_info

    async def generate_detail_shot(
        self,
        location: Location,
        focus: str,
        style: str = "webtoon",
        resolution: str = "1K",
        overwrite_cache: bool = False,
    ) -> tuple[bytes, dict]:
        """Generate a detail shot of a specific area in the location.

        Args:
            location: Location
            focus: What to focus on (e.g., "window", "desk", "door")
            style: Art style
            resolution: Image resolution (1K, 2K, 4K)
            overwrite_cache: Bypass cache and regenerate

        Returns:
            Tuple of (image_data, generation_info)
        """
        base_prompt = f"""Create a detail shot/close-up of a specific area in {style} art style.

Requirements:
- Focus on: {focus}
- Part of the larger location but zoomed in
- Detailed textures and objects
- No characters
- Suitable for webtoon panel backgrounds
"""

        prompt = self._build_location_prompt(location, base_prompt)

        image_data, response_metadata = await self.client.generate_image(
            prompt=prompt,
            aspect_ratio="4:3",
            resolution=resolution,
            style=style,
            overwrite_cache=overwrite_cache,
        )

        generation_info = {
            "type": "location_detail",
            "location_id": location.id,
            "location_name": location.name,
            "focus": focus,
            "prompt": prompt,
            "parameters": {
                "aspect_ratio": "4:3",
                "resolution": resolution,
                "style": style,
                "model": self.client.image_model,
            },
            "response": response_metadata,
        }

        return image_data, generation_info
