# Claude Code Notes for DreamRight

## Important: Working Directory

**Always run commands from the project root (`dreamright-20251126/`) folder**, not from subfolders like `test-webtoon/`. This avoids path-related issues when verifying files or running tests.

```bash
# Good - run from project root
cd /Users/long/Documents/Github/dreamright-20251126
dreamright init my-project
cd my-project && dreamright expand "story idea"

# Bad - can cause path issues
cd test-webtoon
ls assets/characters/  # may fail if working directory changes
```

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
