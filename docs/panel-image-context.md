# Panel Image Context

This document explains the context provided to the AI when generating panel images.

## Context Structure

When generating a panel image, the following context is assembled:

```
┌─────────────────────────────────────────────────────────────┐
│                    IMAGE GENERATION PROMPT                   │
├─────────────────────────────────────────────────────────────┤
│  1. Style Declaration                                        │
│     - Art style (webtoon, manga, etc.)                      │
├─────────────────────────────────────────────────────────────┤
│  2. Continuity Instructions (if continuous panel)           │
│     - Continuity note from script                           │
│     - Consistency requirements                              │
├─────────────────────────────────────────────────────────────┤
│  3. Composition                                              │
│     - Shot type (wide, medium, close_up, extreme_close_up)  │
│     - Camera angle (eye_level, high, low, dutch)            │
├─────────────────────────────────────────────────────────────┤
│  4. Background                                               │
│     - Location name and description                         │
│     - Visual tags/details                                   │
│     - Time of day                                           │
├─────────────────────────────────────────────────────────────┤
│  5. Characters                                               │
│     - Character name and visual tags                        │
│     - Expression                                            │
│     - Pose (if specified)                                   │
│     - Position in frame (left, center, right)               │
├─────────────────────────────────────────────────────────────┤
│  6. Action                                                   │
│     - What's happening in the panel                         │
├─────────────────────────────────────────────────────────────┤
│  7. Important Notes                                          │
│     - No speech bubbles or text                             │
│     - Leave space for dialogue overlay                      │
├─────────────────────────────────────────────────────────────┤
│  8. Style Requirements                                       │
│     - Clean linework                                        │
│     - Expressive poses                                      │
│     - Dynamic composition                                   │
└─────────────────────────────────────────────────────────────┘
```

## Reference Images

The image generator can use multiple reference images for consistency:

```
┌─────────────────────────────────────────────────────────────┐
│                    REFERENCE IMAGES                          │
├─────────────────────────────────────────────────────────────┤
│  Priority Order:                                             │
│                                                              │
│  1. Previous Panel Image (if continues_from_previous=true)  │
│     └── First priority for visual continuity                │
│                                                              │
│  2. Character Reference Images                               │
│     └── Portrait/reference for each character in panel      │
│                                                              │
│  3. Location Reference Image                                 │
│     └── Background reference for the location               │
└─────────────────────────────────────────────────────────────┘
```

## Panel Continuity System

### How Continuity Works

When generating chapters, the AI marks panels that continue from the previous:

```python
class Panel:
    continues_from_previous: bool = False  # Is this a continuation?
    continuity_note: str = ""              # What must stay consistent?
```

### Example Chapter Script

```
Scene 1: Classroom
  Panel 1:
    Shot: wide, Angle: eye_level
    Action: Mina sits at her desk, looking out the window
    Characters: Mina(thoughtful)

  Panel 2: [→]                              ← Continuous panel marker
    Shot: close_up, Angle: eye_level
    Continuity: same lighting, same window reflection
    Action: Close-up of Mina's face as she notices something
    Characters: Mina(surprised)

  Panel 3: [→]
    Shot: extreme_close_up, Angle: eye_level
    Continuity: same expression transition, same lighting angle
    Action: Mina's eyes widen as she sees a ghostly figure
    Characters: Mina(scared)

  Panel 4:                                  ← New composition (no marker)
    Shot: wide, Angle: low
    Action: The ghost of Kai stands by the window
    Characters: Kai(neutral)
```

### Continuity in Image Generation

When `continues_from_previous=true`:

1. **Previous panel image added as reference** (first priority)
2. **Continuity instructions added to prompt**:

```
CONTINUITY (IMPORTANT - maintain consistency with reference image):
- same lighting, same window reflection
- This panel is a direct continuation of the previous panel
- Maintain same lighting, color temperature, and atmosphere
- Keep character appearances, poses, and positions consistent
```

### Visual Flow

```
Panel 1 ──────────────────────────────────────────────────────►
   │ (standalone, uses character + location refs)
   │
   ▼ saved to assets/chapters/1/scene_1/panel_1.png

Panel 2 [→] ──────────────────────────────────────────────────►
   │ references: [panel_1.png, character_refs, location_ref]
   │ continuity: "same lighting, same window reflection"
   │
   ▼ saved to assets/chapters/1/scene_1/panel_2.png

Panel 3 [→] ──────────────────────────────────────────────────►
   │ references: [panel_2.png, character_refs, location_ref]
   │ continuity: "same expression transition"
   │
   ▼ saved to assets/chapters/1/scene_1/panel_3.png

Panel 4 ──────────────────────────────────────────────────────►
   │ (new composition, uses character + location refs only)
   │
   ▼ saved to assets/chapters/1/scene_1/panel_4.png
```

## Prompt Examples

### Standard Panel (No Continuity)

```
Create a webtoon/manga panel in webtoon art style.

COMPOSITION:
- wide establishing shot showing full environment and characters
- Camera angle: eye level, straight on view

BACKGROUND:
- Location: Classroom 2-B
- Setting: A standard high school classroom with rows of desks
- Details: windows, chalkboard, wooden desks
- Time: day

CHARACTERS:
- Character 'Mina Kim' (long black hair, school uniform, petite)
  - Expression: thoughtful - Position: center of frame

ACTION: Mina sits at her desk, looking out the window

IMPORTANT:
- Do NOT include any speech bubbles or text in the image
- Leave clean space in composition where dialogue might be added later

STYLE REQUIREMENTS:
- Clean linework suitable for webtoon
- Expressive character poses and faces
- Dynamic composition
```

### Continuous Panel

```
Create a webtoon/manga panel in webtoon art style.

CONTINUITY (IMPORTANT - maintain consistency with reference image):
- same lighting, same window reflection
- This panel is a direct continuation of the previous panel
- Maintain same lighting, color temperature, and atmosphere
- Keep character appearances, poses, and positions consistent

COMPOSITION:
- close-up shot focusing on face and expressions
- Camera angle: eye level, straight on view

BACKGROUND:
- Location: Classroom 2-B
- Setting: A standard high school classroom with rows of desks
- Time: day

CHARACTERS:
- Character 'Mina Kim' (long black hair, school uniform, petite)
  - Expression: surprised - Position: center of frame

ACTION: Close-up of Mina's face as she notices something

IMPORTANT:
- Do NOT include any speech bubbles or text in the image
- Leave clean space in composition where dialogue might be added later

STYLE REQUIREMENTS:
- Clean linework suitable for webtoon
- Expressive character poses and faces
- Dynamic composition
```

## Shot Type Descriptions

| Shot Type | Description | Use Case |
|-----------|-------------|----------|
| `wide` | Full location/scene view, multiple characters | Establishing shots, action scenes |
| `medium` | Character from waist up | Dialogue, general interaction |
| `close_up` | Face focus | Emotional moments, reactions |
| `extreme_close_up` | Detail focus (eyes, hands, objects) | Key details, tension |

## Camera Angle Descriptions

| Angle | Description | Emotional Effect |
|-------|-------------|------------------|
| `eye_level` | Straight on view | Neutral, natural |
| `high` | Looking down | Vulnerability, overview |
| `low` | Looking up | Power, grandeur |
| `dutch` | Tilted frame | Tension, unease |

## Aspect Ratios

| Panel Type | Aspect Ratio | Use Case |
|------------|--------------|----------|
| Standard | 4:3 | Regular panels |
| Splash | 9:16 | Full-page dramatic moments |
| Transition | 1:1 | Scene transitions |

## Best Practices

### When to Use Continuity

Mark `continues_from_previous=true` when:
- Same moment, different framing (wide → close-up)
- Reaction shots in conversation
- Action sequences with consistent motion
- Emotional beats requiring visual consistency

### When NOT to Use Continuity

Keep `continues_from_previous=false` when:
- New scene or location
- Time skip
- Different characters entering
- Deliberate visual contrast needed

### Continuity Notes

Good continuity notes are specific:
- ✓ "same character pose, same lighting angle"
- ✓ "maintain window reflection, same desk position"
- ✓ "character mid-motion, same trajectory"
- ✗ "keep it consistent" (too vague)
- ✗ "same as before" (not actionable)
