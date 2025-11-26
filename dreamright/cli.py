"""DreamRight CLI - AI-powered webtoon and short-form drama production."""

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .gemini_client import GeminiClient, set_client
from .generators.chapter import ChapterGenerator
from .generators.character import CharacterGenerator
from .generators.location import LocationGenerator
from .generators.panel import PanelGenerator
from .generators.story import StoryExpander
from .models import (
    CameraAngle,
    Dialogue,
    DialogueType,
    Genre,
    Panel as PanelModel,
    PanelCharacter,
    PanelComposition,
    ProjectStatus,
    ShotType,
    TimeOfDay,
    Tone,
)
from .storage import ProjectManager, slugify

app = typer.Typer(
    name="dreamright",
    help="AI-powered webtoon and short-form drama production",
    no_args_is_help=True,
)
console = Console()

# Subcommands
generate_app = typer.Typer(help="Generate assets")
app.add_typer(generate_app, name="generate")


def get_project_path() -> Path:
    """Get the current project path (current directory)."""
    return Path.cwd()


def load_project() -> ProjectManager:
    """Load the project from current directory."""
    path = get_project_path()
    if not ProjectManager.exists(path):
        console.print("[red]No project found in current directory.[/red]")
        console.print("Run [cyan]dreamright init <name>[/cyan] to create a project.")
        raise typer.Exit(1)
    return ProjectManager.load(path)


def run_async(coro):
    """Run an async coroutine."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            return asyncio.run(coro)
        else:
            return loop.run_until_complete(coro)
    except ValueError as e:
        error_msg = str(e)
        if "GOOGLE_API_KEY" in error_msg:
            console.print("[red]Error: Missing API key[/red]")
            console.print(f"\n{error_msg}")
            console.print("\n[dim]Set your API key with:[/dim]")
            console.print('  export GOOGLE_API_KEY="your-api-key"')
            raise typer.Exit(1)
        raise


@app.command()
def init(
    name: str = typer.Argument(..., help="Project name"),
    format: str = typer.Option("webtoon", help="Project format (webtoon or short_drama)"),
    path: Optional[Path] = typer.Option(None, help="Project directory (defaults to current dir if empty, else ./<name>)"),
):
    """Initialize a new DreamRight project."""
    if path is None:
        cwd = Path.cwd()
        # Use current directory if it's empty or only has hidden files
        if not any(f for f in cwd.iterdir() if not f.name.startswith('.')):
            path = cwd
        else:
            path = cwd / name.lower().replace(" ", "-")

    if path.exists() and any(f for f in path.iterdir() if not f.name.startswith('.')):
        console.print(f"[red]Directory {path} already exists and is not empty.[/red]")
        raise typer.Exit(1)

    with console.status(f"Creating project '{name}'..."):
        manager = ProjectManager.create(path, name, format)

    console.print(f"[green]Project '{name}' created at {path}[/green]")
    console.print("\nNext steps:")
    console.print(f"  1. cd {path}")
    console.print('  2. dreamright expand "Your story idea..."')


@app.command()
def expand(
    prompt: str = typer.Argument(..., help="Story prompt/idea to expand"),
    genre: Optional[str] = typer.Option(None, help="Genre hint (romance, action, fantasy, etc.)"),
    tone: Optional[str] = typer.Option(None, help="Tone hint (comedic, dramatic, dark, etc.)"),
    episodes: int = typer.Option(10, help="Target number of episodes"),
):
    """Expand a story prompt into full story structure."""
    manager = load_project()

    # Parse hints
    genre_hint = None
    if genre:
        try:
            genre_hint = Genre(genre.lower())
        except ValueError:
            console.print(f"[yellow]Unknown genre '{genre}', will let AI decide.[/yellow]")

    tone_hint = None
    if tone:
        try:
            tone_hint = Tone(tone.lower())
        except ValueError:
            console.print(f"[yellow]Unknown tone '{tone}', will let AI decide.[/yellow]")

    console.print(Panel(prompt, title="Story Prompt", border_style="blue"))

    async def do_expand():
        expander = StoryExpander()
        return await expander.expand(
            prompt=prompt,
            genre_hint=genre_hint,
            tone_hint=tone_hint,
            episode_count=episodes,
        )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Expanding story with AI...", total=None)
        story, characters, locations = run_async(do_expand())

    # Update project
    manager.project.original_prompt = prompt
    manager.project.story = story
    manager.project.characters = characters
    manager.project.locations = locations
    manager.project.status = ProjectStatus.IN_PROGRESS
    manager.save()

    # Display results
    console.print("\n[green]Story expanded successfully![/green]\n")

    console.print(Panel(
        f"[bold]{story.title}[/bold]\n\n{story.logline}",
        title="Story",
        border_style="green",
    ))

    console.print(f"\n[cyan]Genre:[/cyan] {story.genre.value}")
    console.print(f"[cyan]Tone:[/cyan] {story.tone.value}")
    console.print(f"[cyan]Themes:[/cyan] {', '.join(story.themes)}")
    console.print(f"[cyan]Episodes:[/cyan] {story.episode_count}")

    # Characters table
    if characters:
        console.print("\n[bold]Characters:[/bold]")
        char_table = Table(show_header=True)
        char_table.add_column("Name")
        char_table.add_column("Role")
        char_table.add_column("Age")
        char_table.add_column("Description")

        for char in characters:
            char_table.add_row(
                char.name,
                char.role.value,
                char.age,
                char.description.physical[:50] + "..." if len(char.description.physical) > 50 else char.description.physical,
            )
        console.print(char_table)

    # Locations table
    if locations:
        console.print("\n[bold]Locations:[/bold]")
        loc_table = Table(show_header=True)
        loc_table.add_column("Name")
        loc_table.add_column("Type")
        loc_table.add_column("Description")

        for loc in locations:
            loc_table.add_row(
                loc.name,
                loc.type.value,
                loc.description[:50] + "..." if len(loc.description) > 50 else loc.description,
            )
        console.print(loc_table)

    console.print("\n[dim]Next: dreamright generate character --name <name>[/dim]")


@generate_app.command("character")
def generate_character(
    name: Optional[str] = typer.Option(None, help="Character name (generates all if not specified)"),
    style: str = typer.Option("webtoon", help="Art style"),
    portrait_only: bool = typer.Option(True, help="Generate only portrait (not full three-view)"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Regenerate even if exists (bypass cache)"),
):
    """Generate character visual assets."""
    manager = load_project()

    if not manager.project.characters:
        console.print("[red]No characters found. Run 'dreamright expand' first.[/red]")
        raise typer.Exit(1)

    # Find character(s) to generate
    if name:
        char = manager.project.get_character_by_name(name)
        if not char:
            console.print(f"[red]Character '{name}' not found.[/red]")
            console.print("Available characters:")
            for c in manager.project.characters:
                console.print(f"  - {c.name}")
            raise typer.Exit(1)
        characters_to_generate = [char]
    else:
        characters_to_generate = manager.project.characters

    async def do_generate():
        generator = CharacterGenerator()
        for char in characters_to_generate:
            console.print(f"\n[cyan]Generating assets for {char.name}...[/cyan]")

            # Create human-readable subfolder name
            char_slug = slugify(char.name)
            char_folder = f"characters/{char_slug}"

            # Build base metadata for the asset
            char_metadata = {
                "type": "character",
                "character_id": char.id,
                "character_name": char.name,
                "role": char.role.value,
                "age": char.age,
                "style": style,
                "visual_tags": char.visual_tags,
                "description": {
                    "physical": char.description.physical,
                    "personality": char.description.personality,
                },
            }

            if portrait_only:
                # Generate portrait only
                image_data, gen_info = await generator.generate_portrait(char, style=style, overwrite_cache=overwrite)
                path = manager.save_asset(
                    char_folder,
                    "portrait.png",
                    image_data,
                    metadata={
                        **char_metadata,
                        "asset_type": "portrait",
                        "gemini": gen_info,
                    },
                )
                char.assets.portrait = path
                console.print(f"  [green]Portrait saved: {path}[/green]")
            else:
                # Generate three-view
                views = await generator.generate_three_view(char, style=style, overwrite_cache=overwrite)
                for view_name, (image_data, gen_info) in views.items():
                    path = manager.save_asset(
                        char_folder,
                        f"{view_name}.png",
                        image_data,
                        metadata={
                            **char_metadata,
                            "asset_type": f"three_view_{view_name}",
                            "gemini": gen_info,
                        },
                    )
                    char.assets.three_view[view_name] = path
                    console.print(f"  [green]{view_name.title()} view saved: {path}[/green]")

        manager.save()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating character assets...", total=None)
        run_async(do_generate())

    console.print("\n[green]Character generation complete![/green]")
    console.print("[dim]Next: dreamright generate location --name <name>[/dim]")


@generate_app.command("location")
def generate_location(
    name: Optional[str] = typer.Option(None, help="Location name (generates all if not specified)"),
    style: str = typer.Option("webtoon", help="Art style"),
    time: str = typer.Option("day", help="Time of day (morning, day, evening, night)"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Regenerate even if exists (bypass cache)"),
):
    """Generate location/background visual assets."""
    manager = load_project()

    if not manager.project.locations:
        console.print("[red]No locations found. Run 'dreamright expand' first.[/red]")
        raise typer.Exit(1)

    # Parse time of day
    try:
        time_of_day = TimeOfDay(time.lower())
    except ValueError:
        console.print(f"[yellow]Unknown time '{time}', using 'day'.[/yellow]")
        time_of_day = TimeOfDay.DAY

    # Find location(s) to generate
    if name:
        loc = manager.project.get_location_by_name(name)
        if not loc:
            console.print(f"[red]Location '{name}' not found.[/red]")
            console.print("Available locations:")
            for l in manager.project.locations:
                console.print(f"  - {l.name}")
            raise typer.Exit(1)
        locations_to_generate = [loc]
    else:
        locations_to_generate = manager.project.locations

    async def do_generate():
        generator = LocationGenerator()
        for loc in locations_to_generate:
            console.print(f"\n[cyan]Generating {loc.name}...[/cyan]")

            # Create human-readable subfolder name
            loc_slug = slugify(loc.name)
            loc_folder = f"locations/{loc_slug}"

            # Build base metadata for the asset
            loc_metadata = {
                "type": "location",
                "location_id": loc.id,
                "location_name": loc.name,
                "location_type": loc.type.value,
                "time_of_day": time_of_day.value,
                "style": style,
                "description": loc.description,
                "visual_tags": loc.visual_tags,
            }

            image_data, gen_info = await generator.generate_reference(
                loc,
                time_of_day=time_of_day,
                style=style,
                overwrite_cache=overwrite,
            )
            path = manager.save_asset(
                loc_folder,
                f"{time_of_day.value}.png",
                image_data,
                metadata={
                    **loc_metadata,
                    "gemini": gen_info,
                },
            )
            loc.assets.variations[time_of_day.value] = path

            if loc.assets.reference is None:
                loc.assets.reference = path

            console.print(f"  [green]Saved: {path}[/green]")

        manager.save()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating location assets...", total=None)
        run_async(do_generate())

    console.print("\n[green]Location generation complete![/green]")
    console.print("[dim]Next: dreamright generate panel[/dim]")


@generate_app.command("panel")
def generate_panel(
    description: str = typer.Argument(..., help="Panel description/action"),
    character: Optional[str] = typer.Option(None, "--char", help="Character name to include"),
    location: Optional[str] = typer.Option(None, "--loc", help="Location name for background"),
    expression: str = typer.Option("neutral", help="Character expression"),
    shot: str = typer.Option("medium", help="Shot type (wide, medium, close_up, extreme_close_up)"),
    dialogue: Optional[str] = typer.Option(None, help="Dialogue text (stored in metadata, not rendered)"),
    style: str = typer.Option("webtoon", help="Art style"),
    scene: int = typer.Option(1, "--scene", "-s", help="Scene number for organizing output"),
    output: Optional[Path] = typer.Option(None, "-o", help="Output file path"),
):
    """Generate a single panel image."""
    manager = load_project()

    # Parse shot type
    try:
        shot_type = ShotType(shot.lower())
    except ValueError:
        console.print(f"[yellow]Unknown shot type '{shot}', using 'medium'.[/yellow]")
        shot_type = ShotType.MEDIUM

    # Build panel specification
    panel = PanelModel(
        number=1,
        composition=PanelComposition(shot_type=shot_type),
        action=description,
    )

    # Add character if specified
    characters_dict = {}
    character_refs = {}
    if character:
        char = manager.project.get_character_by_name(character)
        if char:
            panel.characters.append(
                PanelCharacter(
                    character_id=char.id,
                    expression=expression,
                    position="center",
                )
            )
            characters_dict[char.id] = char

            # Add reference if available
            if char.assets.portrait:
                ref_path = manager.storage.get_absolute_asset_path(char.assets.portrait)
                if ref_path.exists():
                    character_refs[char.id] = ref_path
        else:
            console.print(f"[yellow]Character '{character}' not found, generating without.[/yellow]")

    # Add dialogue if specified
    if dialogue:
        char_id = panel.characters[0].character_id if panel.characters else None
        panel.dialogue.append(
            Dialogue(
                character_id=char_id,
                text=dialogue,
                type=DialogueType.SPEECH,
            )
        )

    # Get location
    loc = None
    location_ref = None
    if location:
        loc = manager.project.get_location_by_name(location)
        if loc and loc.assets.reference:
            ref_path = manager.storage.get_absolute_asset_path(loc.assets.reference)
            if ref_path.exists():
                location_ref = ref_path

    async def do_generate():
        generator = PanelGenerator()
        return await generator.generate_panel(
            panel=panel,
            characters=characters_dict,
            location=loc,
            character_references=character_refs,
            location_reference=location_ref,
            style=style,
            scene_number=scene,
        )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating panel...", total=None)
        image_data, generation_info = run_async(do_generate())

    # Save the panel image and metadata
    if output:
        output_path = output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(image_data)
        # Save metadata JSON alongside the image
        metadata_path = output_path.with_suffix(".json")
        with open(metadata_path, "w") as f:
            json.dump(generation_info, f, indent=2)
    else:
        # Organize by scene subfolder: panels/scene_{n}/panel_{number}.png
        scene_folder = f"panels/scene_{scene}"
        filename = f"panel_{panel.number}.png"
        output_path = manager.save_asset(
            scene_folder,
            filename,
            image_data,
            metadata=generation_info,
        )
        panel.image_path = output_path
        metadata_path = output_path.replace(".png", ".json")

    manager.save()

    console.print(f"\n[green]Panel generated: {output_path}[/green]")
    console.print(f"[green]Metadata saved: {metadata_path}[/green]")


@generate_app.command("panels")
def generate_panels(
    chapter: int = typer.Option(..., "--chapter", "-c", help="Chapter number to generate panels for"),
    scene: Optional[int] = typer.Option(None, "--scene", "-s", help="Generate only a specific scene"),
    style: str = typer.Option("webtoon", help="Art style"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Regenerate even if panels exist (bypass cache)"),
):
    """Generate all panel images for a chapter or scene."""
    from .generators.panel import PanelResult, SceneResult

    manager = load_project()

    # Find the chapter
    target_chapter = None
    for ch in manager.project.chapters:
        if ch.number == chapter:
            target_chapter = ch
            break

    if not target_chapter:
        console.print(f"[red]Chapter {chapter} not found.[/red]")
        console.print("Available chapters:")
        for ch in manager.project.chapters:
            console.print(f"  - Chapter {ch.number}: {ch.title}")
        raise typer.Exit(1)

    if not target_chapter.scenes:
        console.print(f"[red]Chapter {chapter} has no scenes.[/red]")
        raise typer.Exit(1)

    # If scene specified, filter to just that scene
    if scene is not None:
        target_scene = None
        for s in target_chapter.scenes:
            if s.number == scene:
                target_scene = s
                break
        if not target_scene:
            console.print(f"[red]Scene {scene} not found in Chapter {chapter}.[/red]")
            console.print("Available scenes:")
            for s in target_chapter.scenes:
                console.print(f"  - Scene {s.number}: {s.description[:50]}...")
            raise typer.Exit(1)
        scenes_to_generate = [target_scene]
        total_panels = len(target_scene.panels)
        console.print(f"\n[cyan]Generating {total_panels} panels for Chapter {chapter}, Scene {scene}[/cyan]")
    else:
        scenes_to_generate = target_chapter.scenes
        total_panels = sum(len(s.panels) for s in target_chapter.scenes)
        console.print(f"\n[cyan]Generating {total_panels} panels for Chapter {chapter}: {target_chapter.title}[/cyan]")

    # Build lookup dicts
    characters_dict = {char.id: char for char in manager.project.characters}
    locations_dict = {loc.id: loc for loc in manager.project.locations}

    # Build reference paths
    character_refs = {}
    for char in manager.project.characters:
        if char.assets.portrait:
            ref_path = manager.storage.get_absolute_asset_path(char.assets.portrait)
            if ref_path.exists():
                character_refs[char.id] = ref_path

    location_refs = {}
    for loc in manager.project.locations:
        if loc.assets.reference:
            ref_path = manager.storage.get_absolute_asset_path(loc.assets.reference)
            if ref_path.exists():
                location_refs[loc.id] = ref_path

    # Progress callbacks
    current_scene_num = [0]

    def on_scene_start(s):
        current_scene_num[0] = s.number
        desc = s.description[:50] + "..." if len(s.description) > 50 else s.description
        console.print(f"\n  [bold]Scene {s.number}[/bold]: {desc}")

    def on_panel_start(panel):
        console.print(f"    Panel {panel.number}: [cyan]generating...[/cyan]", end="")

    def on_panel_complete(result: PanelResult):
        if result.skipped:
            console.print(f"\r    Panel {result.panel.number}: [dim]already exists (skipped)[/dim]")
        elif result.error:
            console.print(f"\r    Panel {result.panel.number}: [red]failed ({result.error})[/red]")
        else:
            console.print(f"\r    Panel {result.panel.number}: [green]saved[/green]           ")

    async def do_generate():
        generator = PanelGenerator()

        if scene is not None:
            # Generate single scene
            result = await generator.generate_scene_panels(
                scene=scenes_to_generate[0],
                chapter_number=chapter,
                characters=characters_dict,
                locations=locations_dict,
                character_references=character_refs,
                location_references=location_refs,
                output_dir=manager.storage.assets_path,
                style=style,
                overwrite=overwrite,
                on_panel_start=on_panel_start,
                on_panel_complete=on_panel_complete,
            )
            return result.generated_count, result.skipped_count, result.error_count
        else:
            # Find previous chapter's last panel for cross-chapter continuity
            prev_chapter_last_panel = None
            if chapter > 1:
                prev_chapter = None
                for ch in manager.project.chapters:
                    if ch.number == chapter - 1:
                        prev_chapter = ch
                        break
                if prev_chapter and prev_chapter.scenes:
                    last_scene = prev_chapter.scenes[-1]
                    if last_scene.panels:
                        last_panel = last_scene.panels[-1]
                        if last_panel.image_path:
                            prev_path = manager.storage.get_absolute_asset_path(last_panel.image_path)
                            if prev_path.exists():
                                prev_chapter_last_panel = prev_path

            # Generate full chapter
            result = await generator.generate_chapter_panels(
                chapter=target_chapter,
                characters=characters_dict,
                locations=locations_dict,
                character_references=character_refs,
                location_references=location_refs,
                output_dir=manager.storage.assets_path,
                style=style,
                overwrite=overwrite,
                previous_chapter_last_panel=prev_chapter_last_panel,
                on_scene_start=on_scene_start,
                on_panel_start=on_panel_start,
                on_panel_complete=on_panel_complete,
            )
            return result.generated_count, result.skipped_count, result.error_count

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating panels...", total=None)
        generated, skipped, errors = run_async(do_generate())

    manager.save()

    console.print(f"\n[green]Panel generation complete![/green]")
    console.print(f"  Generated: {generated}")
    console.print(f"  Skipped (existing): {skipped}")
    if errors > 0:
        console.print(f"  [red]Errors: {errors}[/red]")
    console.print(f"  Output: assets/panels/chapter-{chapter}/")


def confirm_prompt(prompt: str, title: str = "PROMPT") -> bool:
    """Display a prompt and ask for user confirmation."""
    console.print(f"\n[bold cyan]{'─' * 60}[/bold cyan]")
    console.print(f"[bold cyan]{title}[/bold cyan]")
    console.print(f"[bold cyan]{'─' * 60}[/bold cyan]")
    console.print(prompt)
    console.print(f"[bold cyan]{'─' * 60}[/bold cyan]\n")

    return typer.confirm("Proceed with this prompt?", default=True)


def confirm_result(result: str, title: str = "RESULT") -> bool:
    """Display a result and ask for user confirmation."""
    console.print(f"\n[bold green]{'─' * 60}[/bold green]")
    console.print(f"[bold green]{title}[/bold green]")
    console.print(f"[bold green]{'─' * 60}[/bold green]")
    console.print(result)
    console.print(f"[bold green]{'─' * 60}[/bold green]\n")

    return typer.confirm("Accept this result?", default=True)


@generate_app.command("chapter")
def generate_chapter(
    beat_number: Optional[int] = typer.Option(None, "--beat", "-b", help="Generate chapter for specific beat (1-indexed)"),
    all_beats: bool = typer.Option(False, "--all", "-a", help="Generate chapters for all remaining story beats"),
    panels_per_scene: int = typer.Option(6, help="Target panels per scene"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive mode: confirm prompts and results"),
):
    """Generate chapter(s) from story beats sequentially.

    Chapters are generated one at a time with previous chapter context
    for story continuity. Progress is saved after each chapter.

    Use --interactive for hands-on mode where you confirm each step.
    """
    manager = load_project()

    if not manager.project.story:
        console.print("[red]No story found. Run 'dreamright expand' first.[/red]")
        raise typer.Exit(1)

    story = manager.project.story
    if not story.story_beats:
        console.print("[red]No story beats found. Run 'dreamright expand' first.[/red]")
        raise typer.Exit(1)

    existing_chapters = manager.project.chapters
    existing_numbers = {c.number for c in existing_chapters}

    # Determine which beats to generate
    if all_beats:
        # Generate all remaining (not yet generated) chapters
        beats_to_generate = [
            (i, beat) for i, beat in enumerate(story.story_beats, start=1)
            if i not in existing_numbers
        ]
        if not beats_to_generate:
            console.print("[green]All chapters already generated![/green]")
            raise typer.Exit(0)
    elif beat_number:
        if beat_number < 1 or beat_number > len(story.story_beats):
            console.print(f"[red]Invalid beat number. Must be 1-{len(story.story_beats)}.[/red]")
            raise typer.Exit(1)
        beats_to_generate = [(beat_number, story.story_beats[beat_number - 1])]
    else:
        # Show available beats and status
        console.print("\n[bold]Story Beats:[/bold]")
        for i, beat in enumerate(story.story_beats, start=1):
            existing = i in existing_numbers
            status_mark = "[green]✓[/green]" if existing else "[dim]○[/dim]"
            console.print(f"  {status_mark} {i}. {beat.beat}: {beat.description[:60]}...")

        remaining = len(story.story_beats) - len(existing_numbers)
        console.print(f"\n[dim]{len(existing_numbers)}/{len(story.story_beats)} chapters generated.[/dim]")
        if remaining > 0:
            console.print("[dim]Use --beat N for specific chapter, or --all for remaining.[/dim]")
        raise typer.Exit(0)

    def save_chapter(chapter):
        """Save chapter immediately after generation."""
        # Replace existing or append
        existing_idx = None
        for i, c in enumerate(manager.project.chapters):
            if c.number == chapter.number:
                existing_idx = i
                break

        if existing_idx is not None:
            manager.project.chapters[existing_idx] = chapter
        else:
            manager.project.chapters.append(chapter)
            manager.project.chapters.sort(key=lambda c: c.number)

        manager.save()
        console.print(f"  [green]Saved Chapter {chapter.number}: {chapter.title}[/green]")

    async def do_generate():
        generator = ChapterGenerator()
        generated = []

        # Get all chapters including existing ones (sorted by number)
        all_chapters = sorted(existing_chapters, key=lambda c: c.number)

        for num, beat in beats_to_generate:
            console.print(f"\n[cyan]Generating Chapter {num}: {beat.beat}...[/cyan]")
            if all_chapters:
                console.print(f"  [dim]Using {len(all_chapters)} previous chapter(s) for context[/dim]")

            # Build the prompt
            prompt = generator.build_chapter_prompt(
                story=story,
                beat=beat,
                chapter_number=num,
                characters=manager.project.characters,
                locations=manager.project.locations,
                previous_chapters=all_chapters,
                panels_per_scene=panels_per_scene,
            )

            # Interactive mode: confirm prompt before API call
            if interactive:
                if not confirm_prompt(prompt, f"PROMPT FOR CHAPTER {num}"):
                    console.print("[yellow]Skipped chapter generation.[/yellow]")
                    continue

            # Call the API
            console.print("  [dim]Calling Gemini API...[/dim]")
            chapter = await generator.generate_chapter_from_prompt(
                prompt=prompt,
                characters=manager.project.characters,
                locations=manager.project.locations,
            )

            # Interactive mode: confirm result before saving
            if interactive:
                result_text = generator.format_chapter_result(chapter)
                if not confirm_result(result_text, f"RESULT FOR CHAPTER {num}"):
                    console.print("[yellow]Rejected chapter. Skipping save.[/yellow]")
                    # Option to retry
                    if typer.confirm("Retry generation?", default=False):
                        console.print("  [dim]Retrying...[/dim]")
                        chapter = await generator.generate_chapter_from_prompt(
                            prompt=prompt,
                            characters=manager.project.characters,
                            locations=manager.project.locations,
                        )
                        result_text = generator.format_chapter_result(chapter)
                        if not confirm_result(result_text, f"RETRY RESULT FOR CHAPTER {num}"):
                            console.print("[yellow]Rejected retry. Skipping.[/yellow]")
                            continue
                    else:
                        continue

            # Save immediately after generation
            save_chapter(chapter)

            # Add to context for next chapter
            all_chapters.append(chapter)
            all_chapters.sort(key=lambda c: c.number)
            generated.append(chapter)

        return generated

    chapters = run_async(do_generate())

    # Display results
    console.print("\n[green]Chapter generation complete![/green]")
    for chapter in chapters:
        console.print(f"\n[bold]Chapter {chapter.number}: {chapter.title}[/bold]")
        console.print(f"  Summary: {chapter.summary[:80]}...")
        console.print(f"  Scenes: {len(chapter.scenes)}")
        total_panels = sum(len(s.panels) for s in chapter.scenes)
        console.print(f"  Panels: {total_panels}")

    console.print("\n[dim]Next: dreamright generate panel[/dim]")


@app.command()
def status():
    """Show project status."""
    manager = load_project()
    project = manager.project

    console.print(Panel(
        f"[bold]{project.name}[/bold]\n"
        f"Format: {project.format.value}\n"
        f"Status: {project.status.value}\n"
        f"Created: {project.created_at.strftime('%Y-%m-%d %H:%M')}",
        title="Project",
        border_style="blue",
    ))

    if project.story:
        console.print(f"\n[cyan]Story:[/cyan] {project.story.title}")
        console.print(f"[cyan]Logline:[/cyan] {project.story.logline}")

    console.print(f"\n[cyan]Characters:[/cyan] {len(project.characters)}")
    for char in project.characters:
        has_portrait = "[green]P[/green]" if char.assets.portrait else "[dim]-[/dim]"
        console.print(f"  {has_portrait} {char.name} ({char.role.value})")

    console.print(f"\n[cyan]Locations:[/cyan] {len(project.locations)}")
    for loc in project.locations:
        has_ref = "[green]R[/green]" if loc.assets.reference else "[dim]-[/dim]"
        console.print(f"  {has_ref} {loc.name} ({loc.type.value})")

    console.print(f"\n[cyan]Chapters:[/cyan] {len(project.chapters)}")

    # Count generated assets
    assets_path = manager.storage.assets_path
    if assets_path.exists():
        panel_count = len(list((assets_path / "panels").glob("*.png"))) if (assets_path / "panels").exists() else 0
        console.print(f"\n[cyan]Generated panels:[/cyan] {panel_count}")


@app.command()
def show(
    entity: str = typer.Argument(..., help="Entity to show (story, character:<name>, location:<name>)"),
):
    """Show detailed information about an entity."""
    manager = load_project()

    if entity == "story":
        if not manager.project.story:
            console.print("[red]No story expanded yet.[/red]")
            raise typer.Exit(1)

        story = manager.project.story
        console.print(Panel(
            f"[bold]{story.title}[/bold]\n\n{story.logline}",
            title="Story",
            border_style="green",
        ))
        console.print(f"\n[cyan]Genre:[/cyan] {story.genre.value}")
        console.print(f"[cyan]Tone:[/cyan] {story.tone.value}")
        console.print(f"[cyan]Themes:[/cyan] {', '.join(story.themes)}")
        console.print(f"[cyan]Target Audience:[/cyan] {story.target_audience}")
        console.print(f"[cyan]Episodes:[/cyan] {story.episode_count}")

        console.print("\n[bold]Synopsis:[/bold]")
        console.print(story.synopsis)

        if story.story_beats:
            console.print("\n[bold]Story Beats:[/bold]")
            for beat in story.story_beats:
                console.print(f"  [cyan]{beat.beat}:[/cyan] {beat.description}")

    elif entity.startswith("character:"):
        name = entity.split(":", 1)[1]
        char = manager.project.get_character_by_name(name)
        if not char:
            console.print(f"[red]Character '{name}' not found.[/red]")
            raise typer.Exit(1)

        console.print(Panel(
            f"[bold]{char.name}[/bold] ({char.role.value})\nAge: {char.age}",
            title="Character",
            border_style="green",
        ))
        console.print(f"\n[cyan]Physical:[/cyan] {char.description.physical}")
        console.print(f"[cyan]Personality:[/cyan] {char.description.personality}")
        console.print(f"[cyan]Background:[/cyan] {char.description.background}")
        console.print(f"[cyan]Motivation:[/cyan] {char.description.motivation}")
        console.print(f"\n[cyan]Visual Tags:[/cyan] {', '.join(char.visual_tags)}")

        if char.assets.portrait:
            console.print(f"\n[cyan]Portrait:[/cyan] {char.assets.portrait}")

    elif entity.startswith("location:"):
        name = entity.split(":", 1)[1]
        loc = manager.project.get_location_by_name(name)
        if not loc:
            console.print(f"[red]Location '{name}' not found.[/red]")
            raise typer.Exit(1)

        console.print(Panel(
            f"[bold]{loc.name}[/bold] ({loc.type.value})",
            title="Location",
            border_style="green",
        ))
        console.print(f"\n[cyan]Description:[/cyan] {loc.description}")
        console.print(f"\n[cyan]Visual Tags:[/cyan] {', '.join(loc.visual_tags)}")

        if loc.assets.reference:
            console.print(f"\n[cyan]Reference:[/cyan] {loc.assets.reference}")

    else:
        console.print(f"[red]Unknown entity: {entity}[/red]")
        console.print("Use: story, character:<name>, or location:<name>")
        raise typer.Exit(1)


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
