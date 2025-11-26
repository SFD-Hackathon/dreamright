"""Location asset generator."""

from pathlib import Path
from typing import Optional

from ..gemini_client import GeminiClient
from ..models import Location, TimeOfDay


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
        time_of_day: TimeOfDay = TimeOfDay.DAY,
        weather: str = "clear",
        style: str = "webtoon",
        aspect_ratio: str = "16:9",
        resolution: str = "1K",
        overwrite_cache: bool = False,
    ) -> tuple[bytes, dict]:
        """Generate a location reference image.

        Args:
            location: Location to generate
            time_of_day: Time of day for lighting
            weather: Weather condition
            style: Art style
            aspect_ratio: Image aspect ratio (default 16:9 for wide backgrounds)
            resolution: Image resolution (1K, 2K, 4K)

        Returns:
            Tuple of (image_data, generation_info) where generation_info contains
            the prompt and parameters used
        """
        # Map time of day to lighting description
        lighting_map = {
            TimeOfDay.MORNING: "soft morning light, warm golden hour tones, gentle shadows",
            TimeOfDay.DAY: "bright daylight, clear visibility, natural lighting",
            TimeOfDay.EVENING: "warm sunset colors, orange and pink sky, long shadows",
            TimeOfDay.NIGHT: "night time, moonlight or artificial lights, dark blue tones",
        }

        weather_map = {
            "clear": "clear sky",
            "cloudy": "overcast sky, diffused light",
            "rainy": "rain falling, wet surfaces, reflections",
            "snowy": "snow falling or on ground, cold atmosphere",
        }

        base_prompt = f"""Create a background/environment illustration in {style} art style.

Requirements:
- Establishing shot of the location
- {lighting_map.get(time_of_day, 'natural lighting')}
- Weather: {weather_map.get(weather, weather)}
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
                "time_of_day": time_of_day.value,
                "weather": weather,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "style": style,
                "model": self.client.image_model,
            },
            "response": response_metadata,
        }

        return image_data, generation_info

    async def generate_variations(
        self,
        location: Location,
        times: Optional[list[TimeOfDay]] = None,
        style: str = "webtoon",
        resolution: str = "1K",
    ) -> dict[str, bytes]:
        """Generate location variations for different times of day.

        Args:
            location: Location to generate variations for
            times: List of times to generate (defaults to all)
            style: Art style
            resolution: Image resolution (1K, 2K, 4K)

        Returns:
            Dict mapping time names to image bytes
        """
        if times is None:
            times = [TimeOfDay.MORNING, TimeOfDay.DAY, TimeOfDay.EVENING, TimeOfDay.NIGHT]

        results = {}
        for time in times:
            results[time.value] = await self.generate_reference(
                location=location,
                time_of_day=time,
                style=style,
                resolution=resolution,
            )

        return results

    async def generate_detail_shot(
        self,
        location: Location,
        focus: str,
        time_of_day: TimeOfDay = TimeOfDay.DAY,
        style: str = "webtoon",
        resolution: str = "1K",
    ) -> tuple[bytes, dict]:
        """Generate a detail shot of a specific area in the location.

        Args:
            location: Location
            focus: What to focus on (e.g., "window", "desk", "door")
            time_of_day: Time of day
            style: Art style
            resolution: Image resolution (1K, 2K, 4K)

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
        )

        generation_info = {
            "type": "location_detail",
            "location_id": location.id,
            "location_name": location.name,
            "focus": focus,
            "prompt": prompt,
            "parameters": {
                "time_of_day": time_of_day.value,
                "aspect_ratio": "4:3",
                "resolution": resolution,
                "style": style,
                "model": self.client.image_model,
            },
            "response": response_metadata,
        }

        return image_data, generation_info
