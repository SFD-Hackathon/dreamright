"""Story expansion generator."""

from typing import Optional

from pydantic import BaseModel, Field

from dreamright_gemini_client import GeminiClient
from dreamright_core_schemas import (
    Character,
    CharacterDescription,
    CharacterRole,
    Genre,
    Location,
    LocationType,
    Story,
    StoryBeat,
    Tone,
)


# Response schemas for structured output
class CharacterResponse(BaseModel):
    """Character extracted from story expansion."""

    name: str
    role: str = "supporting"
    age: str = ""
    physical_description: str = ""
    personality: str = ""
    background: str = ""
    motivation: str = ""
    visual_tags: list[str] = Field(default_factory=list)


class LocationResponse(BaseModel):
    """Location extracted from story expansion."""

    name: str
    type: str = "interior"
    description: str = ""
    visual_tags: list[str] = Field(default_factory=list)


class StoryBeatResponse(BaseModel):
    """Story beat in the narrative."""

    beat: str
    description: str


class StoryExpansionResponse(BaseModel):
    """Full story expansion response."""

    title: str
    logline: str
    genre: str
    tone: str
    themes: list[str] = Field(default_factory=list)
    target_audience: str = ""
    episode_count: int = 10
    synopsis: str = ""
    story_beats: list[StoryBeatResponse] = Field(default_factory=list)
    characters: list[CharacterResponse] = Field(default_factory=list)
    locations: list[LocationResponse] = Field(default_factory=list)


STORY_EXPANSION_SYSTEM_PROMPT = """You are an expert webtoon and short-form drama writer. Your task is to expand a simple story prompt into a complete story structure optimized for addictive, visual storytelling.

## STORY STRUCTURE
Design story beats that hook readers and keep them scrolling:
1. **Hook (Episode 1)**: Grab attention in the FIRST PANEL. Start with mystery, danger, or emotion.
2. **Inciting Incident**: The event that starts the main conflict - end this beat on a cliffhanger.
3. **Rising Action**: Build tension with mini-mysteries and reveals. Each episode should have:
   - A discovery or revelation
   - A character moment (humor, bonding, conflict)
   - A cliffhanger or hook to the next episode
4. **Climax**: The peak of conflict - seed this throughout earlier episodes with foreshadowing.
5. **Resolution**: Satisfying emotional payoff. Connect back to the opening.

## ADDICTIVE ELEMENTS
Include these for reader retention:
- **Recurring visual motifs**: A signature item, color, or symbol that appears throughout
- **Mystery breadcrumbs**: Small clues scattered across episodes that pay off later
- **Emotional anchors**: Moments of humor, tenderness, or tension that readers remember
- **Clear stakes**: What does the protagonist lose if they fail? Make it personal.
- **Time pressure**: Add urgency (countdown, deadline, transformation)

## CHARACTER DESIGN (4-5 max)
Create distinct, visually memorable characters:
- 1-2 main characters with CONTRASTING designs (e.g., one colorful, one muted)
- 2-3 supporting characters with ONE defining visual trait each
- Each character needs a SECRET or HIDDEN DEPTH revealed later

## LOCATION DESIGN (3-4 max)
Design locations that serve the story:
- Each location should have TWO MOODS (e.g., safe vs dangerous, day vs night)
- Include sensory details (sounds, smells, temperature)
- Make locations feel lived-in with specific objects

## VISUAL TAGS (CRITICAL FOR CONSISTENCY)
Each character needs ONE consistent outfit they wear throughout the ENTIRE story.
This is essential for visual consistency across all panels.

For characters, include specific details:
- Hair: exact color, length, style (e.g., "shoulder-length black hair with side-swept bangs")
- Eyes: color and distinctive look (e.g., "large brown eyes with tired dark circles")
- Face: any distinctive features (e.g., "round face, small nose, light freckles")
- **OUTFIT (ONE consistent outfit)**: Be VERY specific about clothing
  - Top: exact item and color (e.g., "cream oversized cardigan over white school shirt")
  - Bottom: exact item and color (e.g., "navy pleated school skirt")
  - Footwear: (e.g., "white sneakers with pink laces")
  - Accessories: signature items they ALWAYS have (e.g., "oversized white headphones around neck")
- Build: body type and posture (e.g., "petite build, slightly hunched posture")
- Color palette: overall character colors (e.g., "soft pastels: cream, white, navy")

For locations, include:
- Lighting style (e.g., "golden hour dust motes", "flickering fluorescent")
- Key objects that tell a story (e.g., "dusty piano with one broken key")
- Atmosphere words (e.g., "claustrophobic", "serene", "ominous")
- Color palette (e.g., "warm oranges and browns", "cold blues and grays")
- Sound/sensory elements (e.g., "echoing footsteps", "musty smell")
"""


class StoryExpander:
    """Expands a simple prompt into a full story structure."""

    def __init__(self, client: Optional[GeminiClient] = None):
        """Initialize the story expander.

        Args:
            client: Gemini client (uses global client if not provided)
        """
        if client is None:
            from dreamright_gemini_client import get_client

            client = get_client()
        self.client = client

    async def expand(
        self,
        prompt: str,
        genre_hint: Optional[Genre] = None,
        tone_hint: Optional[Tone] = None,
        episode_count: int = 10,
    ) -> tuple[Story, list[Character], list[Location]]:
        """Expand a prompt into a full story structure.

        Args:
            prompt: User's story prompt/idea
            genre_hint: Optional genre suggestion
            tone_hint: Optional tone suggestion
            episode_count: Target number of episodes

        Returns:
            Tuple of (Story, list of Characters, list of Locations)
        """
        # Build the expansion prompt
        expansion_prompt = f"""Expand this story idea into a complete webtoon/short-form drama structure:

STORY IDEA:
{prompt}

"""
        if genre_hint:
            expansion_prompt += f"SUGGESTED GENRE: {genre_hint.value}\n"
        if tone_hint:
            expansion_prompt += f"SUGGESTED TONE: {tone_hint.value}\n"

        expansion_prompt += f"TARGET EPISODES: {episode_count}\n"

        expansion_prompt += """
Please create:
1. A compelling title and logline
2. Genre and tone that best fits the story
3. Core themes (2-4 themes)
4. A synopsis (2-3 paragraphs)
5. Key story beats (hook, inciting incident, rising action, climax, resolution)
6. Characters (4-5 max): 1-2 main characters and 2-3 supporting characters with detailed descriptions and visual tags
7. Key locations (3-4) with descriptions and visual tags

Make the story engaging for a modern audience, suitable for vertical scrolling webtoon format or short-form video drama.
"""

        # Call Gemini with structured output
        response = await self.client.generate_structured(
            prompt=expansion_prompt,
            response_schema=StoryExpansionResponse,
            system_instruction=STORY_EXPANSION_SYSTEM_PROMPT,
            temperature=0.8,
        )

        # Convert response to our models
        story = self._convert_story(response)
        characters = self._convert_characters(response.characters)
        locations = self._convert_locations(response.locations)

        return story, characters, locations

    def _convert_story(self, response: StoryExpansionResponse) -> Story:
        """Convert response to Story model."""
        # Map genre string to enum
        try:
            genre = Genre(response.genre.lower().replace(" ", "_").replace("-", "_"))
        except ValueError:
            genre = Genre.DRAMA

        # Map tone string to enum
        try:
            tone = Tone(response.tone.lower().replace(" ", "_").replace("-", "_"))
        except ValueError:
            tone = Tone.DRAMATIC

        return Story(
            title=response.title,
            logline=response.logline,
            genre=genre,
            tone=tone,
            themes=response.themes,
            target_audience=response.target_audience,
            episode_count=response.episode_count,
            synopsis=response.synopsis,
            story_beats=[
                StoryBeat(beat=b.beat, description=b.description) for b in response.story_beats
            ],
        )

    def _convert_characters(self, characters: list[CharacterResponse]) -> list[Character]:
        """Convert response characters to Character models."""
        result = []
        for char in characters:
            # Map role string to enum
            try:
                role = CharacterRole(char.role.lower())
            except ValueError:
                role = CharacterRole.SUPPORTING

            result.append(
                Character(
                    name=char.name,
                    role=role,
                    age=char.age,
                    description=CharacterDescription(
                        physical=char.physical_description,
                        personality=char.personality,
                        background=char.background,
                        motivation=char.motivation,
                    ),
                    visual_tags=char.visual_tags,
                )
            )
        return result

    def _convert_locations(self, locations: list[LocationResponse]) -> list[Location]:
        """Convert response locations to Location models."""
        result = []
        for loc in locations:
            # Map type string to enum
            try:
                loc_type = LocationType(loc.type.lower())
            except ValueError:
                loc_type = LocationType.INTERIOR

            result.append(
                Location(
                    name=loc.name,
                    type=loc_type,
                    description=loc.description,
                    visual_tags=loc.visual_tags,
                )
            )
        return result
