"""Panel generation prompt templates."""

PANEL_PROMPT = """
Create a webtoon/manga panel in {{ style }} art style.

## ATMOSPHERE & MOOD
{% if time_of_day == 'day' %}
LIGHTING: Bright natural daylight - warm golden tones, soft shadows, clear visibility
{% elif time_of_day == 'morning' %}
LIGHTING: Early morning - soft diffused light, pale yellows and pinks, gentle shadows, dew-fresh feel
{% elif time_of_day == 'evening' %}
LIGHTING: Golden hour/sunset - rich orange and amber tones, long dramatic shadows, warm nostalgic feel
{% else %}
LIGHTING: Night scene - cool blue moonlight or warm artificial lights, deep shadows, high contrast
{% endif %}

{% if continuity %}
## VISUAL CONTINUITY (CRITICAL)
Match the reference image for:
- Art style, line weight, coloring technique
- Character appearance (face, hair, clothes)
- Color palette and lighting direction
- Background style and detail level

Create NEW composition showing:
- Fresh pose and body position for this action
- New camera angle as specified
{% if continuity_note %}
MAINTAIN: {{ continuity_note }}
{% endif %}
{% endif %}

## COMPOSITION
- Shot: {{ shot_description }}
- Angle: {{ angle_description }}
- Location: {% if location %}{{ location.name }}{% if location.description %} ({{ location.description }}){% endif %}{% if location.visual_tags %} - Visual elements: {{ location.visual_tags[:4] | join(', ') }}{% endif %}{% else %}unspecified{% endif %}

{% if characters %}
## CHARACTERS (CRITICAL: Match reference images EXACTLY)
For each character, you MUST:
- Use the EXACT same costume/outfit as shown in their reference image
- Match hair color, style, and accessories exactly
- Keep facial features consistent with reference
- Only change: expression, pose, and camera angle as specified

{% for char_desc in characters %}
{{ char_desc }}
{% endfor %}
{% endif %}

## ACTION & EMOTION
{{ action }}

## VISUAL EFFECTS (if appropriate)
- Motion lines for movement
- Speed lines for action
- Sparkles/glow for magical/emotional moments
- Dramatic lighting for tension

## TECHNICAL REQUIREMENTS
- FULL BLEED composition (art to all edges, NO white borders)
- NO text, speech bubbles, or sound effects in image
- Clean professional linework
- Expressive faces with clear emotions
- Dynamic poses with weight and balance
- Rich background detail that supports the mood
""".strip()


TRANSITION_PROMPT = """
Create an atmospheric transition panel in {{ style }} art style.

## TRANSITION
Type: {{ transition_type }}
From: {{ from_description }}
To: {{ to_description }}

## VISUAL APPROACH
Create a symbolic or abstract image that bridges two moments:
- Use visual metaphors (passing time, changing mood, shifting location)
- Consider: clocks, moons, shadows, silhouettes, weather, seasons
- Atmospheric and evocative rather than literal
- Minimalist but impactful design

## TECHNICAL
- Cinematic composition
- Strong mood through color and lighting
- No characters unless essential to the transition
- Full bleed, no borders
""".strip()


SPLASH_PROMPT = """
Create a dramatic full-page splash in {{ style }} art style.

## SCENE
{{ description }}

## MOOD & IMPACT
Target emotion: {{ mood }}
This is a KEY MOMENT - make it visually unforgettable.

{% if location %}
## SETTING
{{ location.name }}{% if location.description %}: {{ location.description }}{% endif %}
{% if location.visual_tags %}Key elements: {{ location.visual_tags[:4] | join(', ') }}{% endif %}
{% endif %}

{% if characters %}
## CHARACTERS (dramatic poses)
{% for char in characters %}
- {{ char.name }}{% if char.visual_tags %}: {{ char.visual_tags[:5] | join(', ') }}{% endif %}
{% endfor %}
{% endif %}

## COMPOSITION
- Full vertical page (9:16 ratio)
- Dramatic camera angle (low for power, high for vulnerability, dutch for tension)
- Dynamic character poses with clear silhouettes
- Background that reinforces the emotional beat
- Rich detail and visual impact

## EFFECTS
- Dramatic lighting (rim light, backlight, god rays)
- Motion and energy where appropriate
- Color palette that matches the mood
- Environmental effects (wind, particles, glow)
""".strip()
