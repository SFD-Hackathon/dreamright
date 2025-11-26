# DreamRight

AI-powered webtoon and short-form drama production.

## Installation

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

## Quick Start

```bash
# Set API key
export GOOGLE_API_KEY="your-api-key"

# Create project
dreamright init "My Webtoon"
cd my-webtoon

# Expand story from premise
dreamright expand "A shy high school girl discovers she can see ghosts..."

# Check project status
dreamright status
```

## Workflow

### 1. Story Expansion

```bash
dreamright expand "Your story premise here" --genre fantasy --episodes 5
```

This generates:
- Full story with title, logline, synopsis
- Story beats for each episode/chapter
- Main characters with descriptions
- Key locations

### 2. Asset Generation

```bash
# Generate character portraits
dreamright generate character --name "Mina"
dreamright generate character --all

# Generate location backgrounds
dreamright generate location --name "School" --time day
dreamright generate location --all
```

### 3. Chapter Generation

Chapters are generated **sequentially** with previous chapter context for story continuity.

```bash
# Check chapter status
dreamright generate chapter

# Generate specific chapter
dreamright generate chapter --beat 1

# Generate all remaining chapters
dreamright generate chapter --all
```

Each chapter includes:
- Multiple scenes with location and mood
- Panels with shot type, camera angle, action
- Character expressions and positions
- Dialogue and sound effects

### 4. Interactive Mode

Use `--interactive` or `-i` for hands-on control over generation:

```bash
dreamright generate chapter --beat 1 --interactive
```

Interactive mode flow:
1. **Shows prompt** before API call → You confirm or skip
2. **Calls Gemini API**
3. **Shows result** → You accept, reject, or retry
4. **Saves** only if accepted

This is useful for:
- Reviewing prompts before spending API credits
- Quality checking generated content
- Retrying unsatisfactory generations
- Debugging prompt construction

### 5. Panel Image Generation

```bash
# Generate single panel
dreamright generate panel "Mina sees a ghost" --char Mina --shot close_up

# Options
--char NAME      Character to include
--loc NAME       Location for background
--expression     Character expression (neutral, happy, sad, angry, surprised...)
--shot           Shot type (wide, medium, close_up, extreme_close_up)
--dialogue       Dialogue text (stored in metadata)
```

## Chapter Context System

When generating chapters, DreamRight maintains story continuity using a two-tier context system:

| Tier | Chapters | Content | Purpose |
|------|----------|---------|---------|
| Headlines | ALL previous | Title + summary | Big picture story arc |
| Detailed | Last 2 | Scenes + dialogue | Character voice, immediate continuity |

See [docs/chapter-generation-context.md](docs/chapter-generation-context.md) for details.

## Panel Image Generation

Panel images are generated with rich context including:
- Shot type and camera angle
- Character references (portraits)
- Location references (backgrounds)
- Previous panel reference (for continuity)

### Panel Continuity

When chapters are generated, the AI marks which panels continue from the previous panel:

```
Panel 1: Wide shot of classroom
Panel 2: [→] Close-up of Mina's face    ← continues from Panel 1
         Continuity: "same lighting angle"
Panel 3: [→] Reaction shot              ← continues from Panel 2
Panel 4: New establishing shot          ← fresh composition
```

For continuous panels (`[→]`), the previous panel's image is used as a reference to maintain visual consistency (lighting, poses, atmosphere).

See [docs/panel-image-context.md](docs/panel-image-context.md) for details.

## Caching

API responses are cached to `~/.cache/dreamright/` by default:
- Identical prompts return cached results instantly
- Use `overwrite_cache=True` in code to force fresh generation
- Cache persists across sessions

## Project Structure

```
my-webtoon/
├── project.json          # Project data (story, characters, chapters)
├── assets/
│   ├── characters/
│   │   └── mina-kim/
│   │       └── portrait.png
│   └── locations/
│       └── classroom/
│           └── day.png
└── metadata/             # Generation metadata for each asset
```
