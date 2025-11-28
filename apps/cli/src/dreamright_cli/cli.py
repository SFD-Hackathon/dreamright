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

from dreamright_generators.chapter import ChapterGenerator
from dreamright_generators.character import CharacterGenerator
from dreamright_generators.location import LocationGenerator
from dreamright_generators.story import StoryExpander
from dreamright_core_schemas import (
    CameraAngle,
    Dialogue,
    DialogueType,
    Genre,
    Panel as PanelModel,
    PanelCharacter,
    PanelComposition,
    ProjectFormat,
    ProjectStatus,
    ShotType,
    Tone,
)
from dreamright_storage import ProjectManager, slugify

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


def resolve_project_path(project: Optional[str] = None) -> Path:
    """Resolve project path from project ID or use current directory.

    Args:
        project: Optional project ID or path. If provided, looks for:
                 1. Exact path if it exists
                 2. projects/{project} relative to current directory
                 3. projects/{project} relative to DREAMRIGHT_ROOT env var
                 If None, uses current working directory.

    Returns:
        Resolved project path.

    Raises:
        typer.Exit: If project cannot be found.
    """
    import os

    if project is None:
        return Path.cwd()

    # Try as exact path first
    project_path = Path(project)
    if project_path.exists() and ProjectManager.exists(project_path):
        return project_path

    # Try relative to current directory's projects folder
    cwd_projects = Path.cwd() / "projects" / project
    if cwd_projects.exists() and ProjectManager.exists(cwd_projects):
        return cwd_projects

    # Try relative to DREAMRIGHT_ROOT env var
    root = os.environ.get("DREAMRIGHT_ROOT")
    if root:
        root_projects = Path(root) / "projects" / project
        if root_projects.exists() and ProjectManager.exists(root_projects):
            return root_projects

    # Not found - show helpful error
    console.print(f"[red]Project '{project}' not found.[/red]")
    console.print("Searched in:")
    console.print(f"  - {project_path}")
    console.print(f"  - {cwd_projects}")
    if root:
        console.print(f"  - {Path(root) / 'projects' / project}")

    # List available projects if projects/ exists
    projects_dir = Path.cwd() / "projects"
    if projects_dir.exists():
        available = [p.name for p in projects_dir.iterdir() if p.is_dir() and ProjectManager.exists(p)]
        if available:
            console.print("\nAvailable projects:")
            for name in sorted(available):
                console.print(f"  - {name}")

    raise typer.Exit(1)


def load_project(project: Optional[str] = None) -> ProjectManager:
    """Load the project from specified path or current directory.

    Args:
        project: Optional project ID or path. See resolve_project_path for details.
    """
    path = resolve_project_path(project)
    if not ProjectManager.exists(path):
        console.print("[red]No project found in current directory.[/red]")
        console.print("Run [cyan]dreamright init <name>[/cyan] to create a project.")
        raise typer.Exit(1)
    return ProjectManager.load(path)


def run_async(coro):
    """Run an async coroutine.

    Handles both standalone CLI usage and environments with existing event loops
    (Jupyter notebooks, IDEs, etc.) by using nest_asyncio when needed.
    """
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            return asyncio.run(coro)
        else:
            # Event loop already running (Jupyter, IDE, etc.)
            # Use nest_asyncio to allow nested event loops
            import nest_asyncio
            nest_asyncio.apply()
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
    format: ProjectFormat = typer.Option(
        ProjectFormat.WEBTOON,
        "--format", "-f",
        help="Project format",
        case_sensitive=False,
        show_choices=True,
    ),
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
        manager = ProjectManager.create(path, name, format.value)

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
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID or path (uses current directory if not specified)"),
):
    """Expand a story prompt into full story structure."""
    manager = load_project(project)

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
    overwrite: bool = typer.Option(False, "--overwrite", help="Regenerate even if exists (bypass cache)"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID or path (uses current directory if not specified)"),
):
    """Generate character reference sheets (full-body three-view turnaround).

    Creates a single image showing front, side, and back views of each character.
    This provides the best reference for panel generation with consistent
    costume and appearance from all angles.
    """
    from dreamright_services import CharacterService
    from dreamright_services.exceptions import NotFoundError

    manager = load_project(project)
    service = CharacterService(manager)

    if not manager.project.characters:
        console.print("[red]No characters found. Run 'dreamright expand' first.[/red]")
        raise typer.Exit(1)

    # Find character(s) to generate
    if name:
        try:
            char = service.get_character_by_name(name)
            character_ids = [char.id]
        except NotFoundError:
            console.print(f"[red]Character '{name}' not found.[/red]")
            console.print("Available characters:")
            for c in manager.project.characters:
                console.print(f"  - {c.name}")
            raise typer.Exit(1)
    else:
        character_ids = None  # Generate all

    # Callbacks for progress
    def on_start(char):
        console.print(f"\n[cyan]Generating assets for {char.name}...[/cyan]")

    def on_progress(step_desc):
        console.print(f"  [dim]{step_desc}[/dim]")

    def on_complete(char, path):
        console.print(f"  [green]Complete! Sheet saved: {path}[/green]")

    def on_skip(char, reason):
        console.print(f"\n[dim]{char.name}: assets already exist (use --overwrite to regenerate)[/dim]")

    async def do_generate():
        if character_ids:
            # Single character
            return await service.generate_asset(
                character_ids[0],
                style=style,
                overwrite=overwrite,
                on_start=on_start,
                on_complete=on_complete,
                on_progress=on_progress,
            )
        else:
            # All characters
            return await service.generate_all_assets(
                style=style,
                overwrite=overwrite,
                on_start=on_start,
                on_complete=on_complete,
                on_skip=on_skip,
                on_progress=on_progress,
            )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating character sheets...", total=None)
        run_async(do_generate())

    console.print("\n[green]Character generation complete![/green]")
    console.print("[dim]Next: dreamright generate location --name <name>[/dim]")


@generate_app.command("location")
def generate_location(
    name: Optional[str] = typer.Option(None, help="Location name (generates all if not specified)"),
    style: str = typer.Option("webtoon", help="Art style"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Regenerate even if exists (bypass cache)"),
    sheet: bool = typer.Option(False, "--sheet", help="Generate multi-angle reference sheet (2x2 grid)"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID or path (uses current directory if not specified)"),
):
    """Generate location/background visual assets.

    By default generates single reference images. Use --sheet to generate
    multi-angle reference sheets showing wide, high angle, close-up, and low angle views.
    """
    from dreamright_services import LocationService
    from dreamright_services.exceptions import NotFoundError

    manager = load_project(project)
    service = LocationService(manager)

    if not manager.project.locations:
        console.print("[red]No locations found. Run 'dreamright expand' first.[/red]")
        raise typer.Exit(1)

    # Find location(s) to generate
    if name:
        try:
            loc = service.get_location_by_name(name)
            location_ids = [loc.id]
        except NotFoundError:
            console.print(f"[red]Location '{name}' not found.[/red]")
            console.print("Available locations:")
            for l in manager.project.locations:
                console.print(f"  - {l.name}")
            raise typer.Exit(1)
    else:
        location_ids = [l.id for l in manager.project.locations]

    asset_type = "reference sheet" if sheet else "reference"

    # Callbacks for progress
    def on_start(loc):
        console.print(f"\n[cyan]Generating {loc.name} {asset_type}...[/cyan]")

    def on_complete(loc, path):
        console.print(f"  [green]Saved: {path}[/green]")

    def on_skip(loc, reason):
        console.print(f"\n[dim]{loc.name}: {asset_type} already exists (use --overwrite to regenerate)[/dim]")

    async def do_generate():
        results = []
        for loc_id in location_ids:
            loc = service.get_location(loc_id)

            # Check if asset exists
            if sheet:
                existing = loc.assets.reference_sheet
            else:
                existing = loc.assets.reference

            if existing and not overwrite:
                on_skip(loc, "asset_exists")
                results.append({"location_id": loc_id, "skipped": True, "path": existing})
                continue

            try:
                if sheet:
                    result = await service.generate_reference_sheet(
                        loc_id,
                        style=style,
                        overwrite=overwrite,
                        on_start=on_start,
                        on_complete=on_complete,
                    )
                else:
                    result = await service.generate_asset(
                        loc_id,
                        style=style,
                        overwrite=overwrite,
                        on_start=on_start,
                        on_complete=on_complete,
                    )
                results.append(result)
            except Exception as e:
                console.print(f"  [red]Error: {e}[/red]")
                results.append({"location_id": loc_id, "error": str(e)})
        return results

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Generating location {asset_type}s...", total=None)
        run_async(do_generate())

    console.print(f"\n[green]Location {asset_type} generation complete![/green]")
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
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID or path (uses current directory if not specified)"),
):
    """Generate a single panel image."""
    manager = load_project(project)

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
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID or path (uses current directory if not specified)"),
):
    """Generate all panel images for a chapter or scene."""
    from dreamright_generators.panel import PanelResult
    from dreamright_services import PanelService
    from dreamright_services.exceptions import DependencyError, NotFoundError

    manager = load_project(project)
    service = PanelService(manager)

    # Validate chapter exists
    try:
        target_chapter = service.get_chapter(chapter)
    except NotFoundError:
        console.print(f"[red]Chapter {chapter} not found.[/red]")
        console.print("Available chapters:")
        for ch in manager.project.chapters:
            console.print(f"  - Chapter {ch.number}: {ch.title}")
        raise typer.Exit(1)

    # Validate scene exists if specified
    if scene is not None:
        try:
            service.get_scene(chapter, scene)
        except NotFoundError:
            console.print(f"[red]Scene {scene} not found in Chapter {chapter}.[/red]")
            console.print("Available scenes:")
            for s in target_chapter.scenes:
                console.print(f"  - Scene {s.number}: {s.description[:50]}...")
            raise typer.Exit(1)

    # Validate dependencies using service layer
    missing = service.validate_dependencies(chapter, scene)
    if missing:
        console.print("[red]Error: Missing required assets for panel generation.[/red]\n")

        # Group by type for CLI-friendly output
        char_deps = [d for d in missing if d["type"] in ("character", "character_asset")]
        loc_deps = [d for d in missing if d["type"] in ("location", "location_asset")]
        other_deps = [d for d in missing if d["type"] not in ("character", "character_asset", "location", "location_asset")]

        if char_deps:
            console.print("[yellow]Missing character assets:[/yellow]")
            for dep in char_deps:
                console.print(f"  - {dep['message']}")
            console.print("\nGenerate character assets with:")
            console.print("  [cyan]dreamright generate character[/cyan]")

        if loc_deps:
            if char_deps:
                console.print()
            console.print("[yellow]Missing location assets:[/yellow]")
            for dep in loc_deps:
                console.print(f"  - {dep['message']}")
            console.print("\nGenerate location assets with:")
            console.print("  [cyan]dreamright generate location[/cyan]")

        if other_deps:
            if char_deps or loc_deps:
                console.print()
            console.print("[yellow]Other missing dependencies:[/yellow]")
            for dep in other_deps:
                console.print(f"  - {dep['message']}")
                if dep.get("resolution"):
                    console.print(f"    {dep['resolution']}")

        raise typer.Exit(1)

    # Calculate total panels for progress display
    if scene is not None:
        target_scene = service.get_scene(chapter, scene)
        total_panels = len(target_scene.panels)
        console.print(f"\n[cyan]Generating {total_panels} panels for Chapter {chapter}, Scene {scene}[/cyan]")
    else:
        total_panels = sum(len(s.panels) for s in target_chapter.scenes)
        console.print(f"\n[cyan]Generating {total_panels} panels for Chapter {chapter}: {target_chapter.title}[/cyan]")

    # Progress callbacks for CLI output
    def on_scene_start(s):
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
        return await service.generate_panels(
            chapter_number=chapter,
            scene_number=scene,
            style=style,
            overwrite=overwrite,
            on_scene_start=on_scene_start,
            on_panel_start=on_panel_start,
            on_panel_complete=on_panel_complete,
        )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating panels...", total=None)
        result = run_async(do_generate())

    console.print(f"\n[green]Panel generation complete![/green]")
    console.print(f"  Generated: {result['generated_count']}")
    console.print(f"  Skipped (existing): {result['skipped_count']}")
    if result['error_count'] > 0:
        console.print(f"  [red]Errors: {result['error_count']}[/red]")
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
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID or path (uses current directory if not specified)"),
):
    """Generate chapter(s) from story beats sequentially.

    Chapters are generated one at a time with previous chapter context
    for story continuity. Progress is saved after each chapter.

    Use --interactive for hands-on mode where you confirm each step.
    """
    from dreamright_generators.chapter import ChapterGenerator
    from dreamright_services import ChapterService
    from dreamright_services.exceptions import DependencyError, ValidationError

    manager = load_project(project)
    service = ChapterService(manager)

    # Handle no arguments - show status
    if not all_beats and beat_number is None:
        status = service.get_generation_status()
        if not status["story_expanded"]:
            console.print("[red]No story found. Run 'dreamright expand' first.[/red]")
            raise typer.Exit(1)

        console.print("\n[bold]Story Beats:[/bold]")
        story = manager.project.story
        existing_numbers = {c.number for c in manager.project.chapters}
        for i, beat in enumerate(story.story_beats, start=1):
            existing = i in existing_numbers
            status_mark = "[green]✓[/green]" if existing else "[dim]○[/dim]"
            console.print(f"  {status_mark} {i}. {beat.beat}: {beat.description[:60]}...")

        console.print(f"\n[dim]{status['generated_chapters']}/{status['total_beats']} chapters generated.[/dim]")
        if status["remaining_beats"]:
            console.print("[dim]Use --beat N for specific chapter, or --all for remaining.[/dim]")
        raise typer.Exit(0)

    # Determine which beats to generate
    if all_beats:
        remaining = service.get_remaining_beats()
        if not remaining:
            console.print("[green]All chapters already generated![/green]")
            raise typer.Exit(0)
        beat_numbers_to_generate = [num for num, _ in remaining]
    else:
        # Validate beat number
        try:
            service.validate_beat_number(beat_number)
        except ValidationError as e:
            console.print(f"[red]{e.message}[/red]")
            raise typer.Exit(1)
        beat_numbers_to_generate = [beat_number]

    # Validate dependencies for first beat
    first_beat = beat_numbers_to_generate[0]
    missing = service.validate_dependencies(first_beat)
    if missing:
        dep = missing[0]
        console.print(f"[red]Error: {dep['message']}[/red]")
        console.print(f"Run: [cyan]dreamright generate chapter --beat {dep['chapter_number']}[/cyan]")
        console.print("\n[dim]Chapters must be generated sequentially for story continuity.[/dim]")
        raise typer.Exit(1)

    # Callbacks for progress and interactive mode
    generator = ChapterGenerator()  # For formatting results in interactive mode

    def on_start(num, beat):
        console.print(f"\n[cyan]Generating Chapter {num}: {beat.beat}...[/cyan]")
        existing_count = len([c for c in manager.project.chapters if c.number < num])
        if existing_count:
            console.print(f"  [dim]Using {existing_count} previous chapter(s) for context[/dim]")

    def on_prompt_ready(prompt, num, beat):
        if interactive:
            return confirm_prompt(prompt, f"PROMPT FOR CHAPTER {num}")
        console.print("  [dim]Calling Gemini API...[/dim]")
        return True

    def on_result_ready(chapter, num):
        if interactive:
            result_text = generator.format_chapter_result(chapter)
            if confirm_result(result_text, f"RESULT FOR CHAPTER {num}"):
                return (True, False)  # Accept
            console.print("[yellow]Rejected chapter.[/yellow]")
            retry = typer.confirm("Retry generation?", default=False)
            return (False, retry)
        return (True, False)  # Accept without confirmation

    def on_complete(chapter):
        console.print(f"  [green]Saved Chapter {chapter.number}: {chapter.title}[/green]")

    async def do_generate():
        return await service.generate_chapters(
            beat_numbers=beat_numbers_to_generate,
            panels_per_scene=panels_per_scene,
            on_start=on_start,
            on_prompt_ready=on_prompt_ready,
            on_result_ready=on_result_ready,
            on_complete=on_complete,
        )

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
def status(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID or path (uses current directory if not specified)"),
):
    """Show project status."""
    manager = load_project(project)
    proj = manager.project

    console.print(Panel(
        f"[bold]{proj.name}[/bold]\n"
        f"Format: {proj.format.value}\n"
        f"Status: {proj.status.value}\n"
        f"Created: {proj.created_at.strftime('%Y-%m-%d %H:%M')}",
        title="Project",
        border_style="blue",
    ))

    if proj.story:
        console.print(f"\n[cyan]Story:[/cyan] {proj.story.title}")
        console.print(f"[cyan]Logline:[/cyan] {proj.story.logline}")

    console.print(f"\n[cyan]Characters:[/cyan] {len(proj.characters)}")
    for char in proj.characters:
        has_portrait = "[green]P[/green]" if char.assets.portrait else "[dim]-[/dim]"
        console.print(f"  {has_portrait} {char.name} ({char.role.value})")

    console.print(f"\n[cyan]Locations:[/cyan] {len(proj.locations)}")
    for loc in proj.locations:
        has_ref = "[green]R[/green]" if loc.assets.reference else "[dim]-[/dim]"
        console.print(f"  {has_ref} {loc.name} ({loc.type.value})")

    console.print(f"\n[cyan]Chapters:[/cyan] {len(proj.chapters)}")

    # Count generated assets
    assets_path = manager.storage.assets_path
    if assets_path.exists():
        panel_count = len(list((assets_path / "panels").glob("*.png"))) if (assets_path / "panels").exists() else 0
        console.print(f"\n[cyan]Generated panels:[/cyan] {panel_count}")


@app.command()
def show(
    entity: str = typer.Argument(..., help="Entity to show (story, character:<name>, location:<name>)"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID or path (uses current directory if not specified)"),
):
    """Show detailed information about an entity."""
    manager = load_project(project)

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


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
    projects_dir: Optional[Path] = typer.Option(None, help="Directory for storing projects"),
):
    """Start the DreamRight API server."""
    import uvicorn

    from dreamright_api.app import create_app
    from dreamright_api.deps import settings

    # Configure projects directory
    if projects_dir:
        settings.projects_dir = projects_dir
    else:
        settings.projects_dir = Path.cwd() / "projects"

    console.print(f"\n[bold]DreamRight API Server[/bold]")
    console.print(f"  Projects: {settings.projects_dir}")
    console.print(f"  URL: http://{host}:{port}")
    console.print(f"  Docs: http://{host}:{port}/docs")
    console.print()

    if reload:
        uvicorn.run(
            "dreamright.api.app:app",
            host=host,
            port=port,
            reload=True,
        )
    else:
        app_instance = create_app(projects_dir=settings.projects_dir)
        uvicorn.run(app_instance, host=host, port=port)


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
