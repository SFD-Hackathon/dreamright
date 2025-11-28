"""Location asset generator."""

from typing import Optional

from dreamright_gemini_client import GeminiClient
from dreamright_core_schemas import Location


class LocationGenerator:
    """Generates location/background visual assets."""

    def __init__(self, client: Optional[GeminiClient] = None):
        """Initialize the location generator.

        Args:
            client: Gemini client (uses global client if not provided)
        """
        if client is None:
            from dreamright_gemini_client import get_client

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

IMPORTANT - Background Only Rules:
- Focus on ENVIRONMENTAL elements: walls, floors, ceilings, architecture, lighting, atmosphere
- DO NOT include interactive objects that characters would use (cars, furniture, seats, steering wheels, etc.)
- If the location is a vehicle interior (car, train, etc.), show ONLY the environment (windows, walls, ambient lighting) without seats or controls
- Interactive props and character positioning will be handled separately during panel composition
- This is a STATIC BACKGROUND reference that panels will composite characters onto
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

    async def generate_reference_sheet(
        self,
        location: Location,
        style: str = "webtoon",
        resolution: str = "1K",
        overwrite_cache: bool = False,
    ) -> tuple[bytes, dict]:
        """Generate a multi-panel reference sheet showing different angles of the location.

        Creates a 2x2 grid with:
        - Top-left: Wide establishing shot (eye level)
        - Top-right: Medium shot (high angle, looking down)
        - Bottom-left: Close-up of key details
        - Bottom-right: Low angle shot (looking up)

        Args:
            location: Location to generate
            style: Art style
            resolution: Image resolution (1K, 2K, 4K)
            overwrite_cache: Bypass cache and regenerate

        Returns:
            Tuple of (image_data, generation_info)
        """
        base_prompt = f"""Create a 2x2 grid reference sheet showing the SAME location from 4 different camera angles in {style} art style.

CRITICAL: All 4 panels must show the EXACT SAME location with consistent:
- Architecture and layout
- Color palette and lighting
- Environmental elements only (walls, floors, lighting, atmosphere)
- Overall atmosphere and mood

Grid layout (4 panels, separated by thin white lines):
┌─────────────┬─────────────┐
│ WIDE SHOT   │ HIGH ANGLE  │
│ Eye level   │ Looking down│
│ Establishing│ Medium shot │
├─────────────┼─────────────┤
│ CLOSE-UP    │ LOW ANGLE   │
│ Key details │ Looking up  │
│ Textures    │ Dramatic    │
└─────────────┴─────────────┘

Requirements for all panels:
- Bright daylight, clear visibility
- No characters in the scene
- Detailed environment suitable for webtoon backgrounds
- Consistent visual style across all 4 views

IMPORTANT - Background Only Rules:
- Focus on ENVIRONMENTAL elements: walls, floors, ceilings, architecture, lighting, atmosphere
- DO NOT include interactive objects (furniture, vehicles, seats, controls, etc.)
- If vehicle interior, show ONLY environment (windows, walls, ambient lighting)
- This is a STATIC BACKGROUND reference for panel composition
"""

        prompt = self._build_location_prompt(location, base_prompt)

        image_data, response_metadata = await self.client.generate_image(
            prompt=prompt,
            aspect_ratio="1:1",  # Square for 2x2 grid
            resolution=resolution,
            style=style,
            overwrite_cache=overwrite_cache,
        )

        generation_info = {
            "type": "location_reference_sheet",
            "location_id": location.id,
            "location_name": location.name,
            "location_type": location.type.value,
            "views": ["wide_eye_level", "medium_high_angle", "closeup_details", "low_angle"],
            "prompt": prompt,
            "parameters": {
                "aspect_ratio": "1:1",
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
