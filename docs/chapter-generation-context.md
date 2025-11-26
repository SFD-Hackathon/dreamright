# Chapter Generation Context

This document explains what context is provided to the AI when generating each chapter to maintain story continuity.

## Context Structure

When generating Chapter N, the following context is assembled:

```
┌─────────────────────────────────────────────────────────────┐
│                    GENERATION PROMPT                        │
├─────────────────────────────────────────────────────────────┤
│  1. Story Overview                                          │
│     - Title                                                 │
│     - Logline                                               │
├─────────────────────────────────────────────────────────────┤
│  2. Previous Chapters Summary (last 3 chapters)             │
│     - Chapter title & summary                               │
│     - Key scene descriptions                                │
│     - Sample dialogue snippets                              │
├─────────────────────────────────────────────────────────────┤
│  3. Current Chapter Beat                                    │
│     - Beat name (e.g., "Inciting Incident")                 │
│     - Beat description                                      │
├─────────────────────────────────────────────────────────────┤
│  4. Available Resources                                     │
│     - Characters (name, role, personality)                  │
│     - Locations (name, description)                         │
├─────────────────────────────────────────────────────────────┤
│  5. Generation Instructions                                 │
│     - Panel/scene guidelines                                │
│     - Style requirements                                    │
└─────────────────────────────────────────────────────────────┘
```

## Detailed Breakdown

### 1. Story Overview

Basic story context that remains constant across all chapters:

```
STORY: The Ghost in Seat 24
A shy high school girl discovers she can see ghosts after a near-death
experience and must help a mysterious ghost boy uncover the truth of his death.
```

### 2. Previous Chapters Context

We use a **two-tier approach**:

#### Tier 1: ALL Chapters - Headlines (Title + Summary)

Compact one-liners for every previous chapter to maintain the big picture:

```
STORY SO FAR (all previous chapters):
Chapter 1: The Awakening - Mina nearly drowns in the school pool and gains the ability to see ghosts.
Chapter 2: First Contact - Mina encounters Kai for the first time and realizes he's a ghost.
Chapter 3: The Investigation Begins - Mina and Kai start looking into his death, finding his hidden sketchbook.
Chapter 4: Memories Surface - Kai begins to remember fragments of the night he died.
```

#### Tier 2: Last 2 Chapters - Detailed Context

Rich context with scenes and dialogue for immediate continuity:

```
RECENT CHAPTER DETAILS (for voice and continuity):

Chapter 3: The Investigation Begins
Summary: Mina and Kai start looking into his death, finding his hidden sketchbook.
- Scene: Mina sneaks into the old art room after school...
  - "Why would the swim team captain hide drawings here?"
- Scene: Kai watches Mina flip through his sketches with a mixture of emotions...
  - "I... I don't remember making these. But they're definitely mine."

Chapter 4: Memories Surface
Summary: Kai begins to remember fragments of the night he died.
- Scene: On the rooftop, Kai suddenly clutches his head in pain...
  - "The pool... someone was there. Someone I trusted."
- Scene: Mina tries to comfort Kai as he processes the traumatic memory...
  - "We'll figure this out together. I promise."
```

**Why this two-tier approach?**

| Tier | Content | Purpose | Token Cost |
|------|---------|---------|------------|
| All chapters | Title + summary | Story arc, major plot points | ~20-50 tokens each |
| Last 2 | Full details | Character voice, immediate continuity | ~200-400 tokens each |

This gives:
- **Big picture** - What happened across the entire story
- **Recent detail** - How characters speak, where the story just was
- **Token efficiency** - Scales well for long series (50+ chapters)

### 3. Current Chapter Beat

The story beat defines what this chapter should accomplish:

```
CHAPTER 3: Rising Action
Mina and Kai begin investigating the circumstances of his death.
They discover he was the star of the swim team and find his old
sketchbook hidden in the art room, revealing a artistic side
no one knew about.
```

### 4. Available Resources

#### Characters
```
AVAILABLE CHARACTERS:
- Mina Kim (protagonist): Introverted, anxious, but secretly brave.
  Uses self-deprecating humor as a defense mechanism.
- Kai Park (supporting): Charismatic, playful, persistent,
  masking a deep sadness and confusion.
```

#### Locations
```
AVAILABLE LOCATIONS:
- Classroom 2-B: A standard high school classroom that feels safe
  during the day but eerie when empty.
- The Rooftop: A secluded spot with a view of the city, often windy.
- The Old Art Room: Dusty, abandoned room filled with old easels
  and forgotten student artwork.
```

### 5. Generation Instructions

System prompt that guides the AI's output style:

```
You are an expert webtoon storyboard artist. Your task is to convert
a story beat into a detailed chapter with scenes and panels.

Follow these guidelines:
1. Each scene should have 4-8 panels
2. Start scenes with establishing shots (wide) to set location
3. Use shot variety: wide for context, medium for dialogue, close-up for emotion
4. Include clear action descriptions for each panel
5. Dialogue should be natural and advance the story
6. Include sound effects (SFX) where appropriate
7. Consider vertical scrolling flow - end scenes on hooks or transitions
8. IMPORTANT: Maintain continuity with previous chapters

For expressions: neutral, happy, sad, angry, surprised, scared,
                 confused, determined, embarrassed, thoughtful

For shot types:
- wide: Full location/scene view, multiple characters
- medium: Character from waist up, good for dialogue
- close_up: Face focus, emotional moments
- extreme_close_up: Detail focus (eyes, hands, objects)
```

## Sequential Generation Flow

```
Chapter 1 ──────────────────────────────────────────────────────►
   │ (no previous context)
   │
   ▼ saved to project.json

Chapter 2 ──────────────────────────────────────────────────────►
   │ headlines: [Ch1]
   │ detailed:  [Ch1]
   │
   ▼ saved to project.json

Chapter 3 ──────────────────────────────────────────────────────►
   │ headlines: [Ch1, Ch2]
   │ detailed:  [Ch1, Ch2]
   │
   ▼ saved to project.json

Chapter 4 ──────────────────────────────────────────────────────►
   │ headlines: [Ch1, Ch2, Ch3]      ← ALL chapters
   │ detailed:  [Ch2, Ch3]           ← last 2 only
   │
   ▼ saved to project.json

Chapter 10 ─────────────────────────────────────────────────────►
   │ headlines: [Ch1..Ch9]           ← ALL 9 chapters (~450 tokens)
   │ detailed:  [Ch8, Ch9]           ← last 2 (~600 tokens)
   │
   ▼ saved to project.json
```

## Context Format Functions

### Headline (for all chapters)

```python
def _chapter_headline(chapter: Chapter) -> str:
    """One-liner: title + summary"""
    return f"Chapter {number}: {title} - {summary}"

# Example output:
# "Chapter 3: The Investigation Begins - Mina and Kai start looking into his death."
```

### Detailed (for last 2 chapters)

```python
def _chapter_detailed(chapter: Chapter) -> str:
    """
    Chapter {number}: {title}
    Summary: {summary}
    - Scene: {scene.description[:100]}...
      - "{dialogue from first 2 panels per scene}"
    """
```

This two-tier approach provides:
- **Story arc** (all headlines) - Major plot points, what happened
- **Recent context** (detailed) - Character voice, immediate continuity
- **Scalability** - Works for 5 or 50+ chapters

## Continuity Instructions

When previous chapters exist, this instruction is added:

```
IMPORTANT: Continue the story naturally from where the previous
chapter left off. Maintain character voice, ongoing plot threads,
and emotional arcs.
```

## Benefits of This Approach

1. **Story Coherence** - Each chapter builds on established events
2. **Character Consistency** - Dialogue samples help maintain voice
3. **Plot Continuity** - Previous summaries prevent contradictions
4. **Resumability** - Can stop/restart generation without losing context
5. **Token Efficiency** - Sliding window prevents context overflow

## Limitations

- Detailed context only for last 2 chapters (older dialogue/scenes not preserved)
- Headlines are lossy (nuance may be lost in summarization)
- No cross-chapter foreshadowing planning (each chapter generated independently)
- No character state tracking (who knows what, relationship status)

## Future Improvements

Potential enhancements:
- **Story bible** - Persistent facts/rules that span all chapters
- **Character state tracking** - Where characters are, what they know
- **Plot thread registry** - Open questions, unresolved conflicts
- **Foreshadowing planner** - Plant seeds for future reveals
