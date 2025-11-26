"""Panel generation prompt templates."""

PANEL_PROMPT = """
Create a webtoon/manga panel in {{ style }} art style.

LIGHTING: {{ time_of_day }} time - use appropriate {{ time_of_day }} lighting ({% if time_of_day == 'day' %}bright, natural sunlight{% elif time_of_day == 'morning' %}soft warm morning light{% elif time_of_day == 'evening' %}warm orange sunset tones{% else %}dark with artificial/moonlight{% endif %})

{% if continuity %}
STYLE CONSISTENCY (use reference for style only, NOT content):
- Match the art style, color palette from reference
- Character: same appearance (hair, clothes) but NEW pose for this action
- Do NOT copy or trace the reference image
{% if continuity_note %}- {{ continuity_note }}
{% endif %}
{% endif %}

SCENE:
- Location: {% if location %}{{ location.name }}{% if location.description %} - {{ location.description }}{% endif %}{% else %}unspecified{% endif %}
- Shot: {{ shot_description }}
- Angle: {{ angle_description }}

{% if characters %}
CHARACTERS (draw with correct human anatomy and proportions):
{% for char_desc in characters %}
- {{ char_desc }}
{% endfor %}
{% endif %}

{% if action %}
ACTION: {{ action }}
{% endif %}

FORMAT:
- FULL BLEED: artwork extends to ALL edges, no white borders
- No speech bubbles or text in the image

QUALITY:
- Clean linework, correct anatomy and body proportions
- Expressive faces, dynamic poses
- Professional webtoon art quality
""".strip()


TRANSITION_PROMPT = """
Create a transition panel in {{ style }} art style.

TRANSITION TYPE: {{ transition_type }}

FROM: {{ from_description }}
TO: {{ to_description }}

Requirements:
- Abstract or symbolic representation of the transition
- Can be a simple visual element (clock, moon phases, footsteps, etc.)
- Atmospheric and mood-setting
- No characters unless specifically needed
- Clean, minimalist design
""".strip()


SPLASH_PROMPT = """
Create a dramatic splash page in {{ style }} art style.

SCENE: {{ description }}
MOOD: {{ mood }}

{% if location %}
LOCATION: {{ location.name }} - {{ location.description }}
{% endif %}

{% if characters %}
CHARACTERS:
{% for char in characters %}
- {{ char.name }}: {{ char.visual_tags[:5] | join(', ') if char.visual_tags else '' }}
{% endfor %}
{% endif %}

REQUIREMENTS:
- Full page vertical composition
- High impact visual
- Dynamic and memorable
- Suitable for key story moment
""".strip()
