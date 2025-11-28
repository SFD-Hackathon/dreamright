# Claude Code Notes for DreamRight

## Important: Working Directory

**Run commands from the project root (`dreamright-20251126/`) folder** using the `--project` option, or from inside a project folder.

```bash
# Option 1: Use --project from root directory (recommended)
cd /Users/long/Documents/Github/dreamright-20251126
dreamright status --project the-last-hunter
dreamright generate panels --chapter 1 --project the-last-hunter

# Option 2: cd into project folder
cd projects/the-last-hunter
dreamright status
dreamright generate panels --chapter 1
```

The `--project` (or `-p`) option is available on all commands that require a project:
- `dreamright status -p <project-id>`
- `dreamright expand -p <project-id>`
- `dreamright show -p <project-id>`
- `dreamright generate character -p <project-id>`
- `dreamright generate location -p <project-id>`
- `dreamright generate chapter -p <project-id>`
- `dreamright generate panel -p <project-id>`
- `dreamright generate panels -p <project-id>`

## Panel Generation

Panels are generated **sequentially** (not in parallel) because:
- Panel N may depend on Panel N-1 for visual continuity
- The `continues_from_previous` flag uses the previous panel as a reference image

**Continuity vs Motion:**
- CONSISTENT: lighting, color palette, background elements, character appearances
- PROGRESSION: characters move/act naturally, expressions evolve
- DO NOT ADD: new props, signs, banners, or objects not in previous panel
- DO NOT REMOVE: existing scene elements from previous panel
- Goal is visual continuity while showing motion, not identical frames

## Project Structure

```
my-project/
├── project.json          # Story data, characters, locations, chapters
└── assets/
    ├── characters/       # Character portraits
    │   └── {name}/
    │       ├── portrait.png
    │       └── portrait.json
    ├── locations/        # Location backgrounds
    │   └── {name}/
    │       ├── day.png
    │       └── day.json
    └── panels/           # Generated panel images
        └── chapter-{n}/
            └── scene-{n}/
                ├── panel-{n}.png
                └── panel-{n}.json
```

## Key Commands

```bash
dreamright init <name>                              # Create project
dreamright expand "prompt" --episodes N             # Generate story
dreamright generate character [--name X]            # Generate character portraits
dreamright generate location [--name X]             # Generate location backgrounds
dreamright generate chapter --beat N                # Generate chapter script
dreamright generate panels --chapter N              # Generate all panels for chapter
dreamright generate panels --chapter N --scene S    # Generate panels for specific scene
dreamright status                                   # Show project status
```

## Cache Bypass

Use `--overwrite` flag to bypass cache and regenerate assets:
```bash
dreamright generate character --name "Mina" --overwrite
dreamright generate location --name "School" --overwrite
dreamright generate panels --chapter 1 --overwrite
dreamright generate panels --chapter 1 --scene 2 --overwrite
```
