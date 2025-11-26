"""Test script for generating chapter 1 and first few panels."""

import asyncio
import json
from pathlib import Path

# Add project to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from dreamright.models import Project
from dreamright.generators.chapter import ChapterGenerator
from dreamright.generators.panel import PanelGenerator
from dreamright.gemini_client import get_client


async def main():
    # Load project
    project_path = Path("/Users/long/Documents/Github/dreamright-20251126-data/ghost-seer/project.json")
    project = Project.model_validate_json(project_path.read_text())

    print(f"Project: {project.name}")
    print(f"Story: {project.story.title}")
    print(f"Characters: {[c.name for c in project.characters]}")
    print(f"Locations: {[l.name for l in project.locations]}")
    print(f"Story beats: {len(project.story.story_beats)}")
    print()

    # Initialize generators
    client = get_client()
    chapter_gen = ChapterGenerator(client)
    panel_gen = PanelGenerator(client)

    # Generate chapter 1 if not exists
    if not project.chapters:
        print("=" * 60)
        print("GENERATING CHAPTER 1")
        print("=" * 60)

        beat = project.story.story_beats[0]
        print(f"Beat: {beat.beat}")
        print(f"Description: {beat.description}")
        print()

        # Build and show prompt
        prompt = chapter_gen.build_chapter_prompt(
            story=project.story,
            beat=beat,
            chapter_number=1,
            characters=project.characters,
            locations=project.locations,
            previous_chapters=None,
        )
        print("PROMPT:")
        print("-" * 40)
        print(prompt)
        print("-" * 40)
        print()

        # Generate chapter
        print("Calling Gemini API...")
        chapter = await chapter_gen.generate_chapter_from_prompt(
            prompt=prompt,
            characters=project.characters,
            locations=project.locations,
        )

        # Display result
        print()
        print("GENERATED CHAPTER:")
        print("-" * 40)
        print(chapter_gen.format_chapter_result(chapter))
        print("-" * 40)

        # Save to project
        project.chapters.append(chapter)
        project_path.write_text(project.model_dump_json(indent=2))
        print(f"\nSaved chapter to {project_path}")
    else:
        chapter = project.chapters[0]
        print(f"Using existing chapter: {chapter.title}")
        print(chapter_gen.format_chapter_result(chapter))

    # Generate first 3 panels
    print()
    print("=" * 60)
    print("GENERATING PANEL IMAGES")
    print("=" * 60)

    # Setup paths - organize by scene subfolder
    assets_dir = project_path.parent / "assets"
    panels_dir = assets_dir / "panels"
    panels_dir.mkdir(parents=True, exist_ok=True)

    # Build character references
    char_refs = {}
    for char in project.characters:
        if char.assets.portrait:
            portrait_path = project_path.parent / char.assets.portrait
            if portrait_path.exists():
                char_refs[char.id] = portrait_path
                print(f"Character ref: {char.name} -> {portrait_path}")

    # Build character lookup
    char_lookup = {c.id: c for c in project.characters}
    loc_lookup = {l.id: l for l in project.locations}

    # Generate first scene's panels (up to 3)
    scene = chapter.scenes[0]
    print(f"\nScene {scene.number}: {scene.description[:50]}...")
    print(f"Location: {scene.location_id}")
    print(f"Time: {scene.time_of_day.value}")

    # Get location reference
    loc_ref = None
    if scene.location_id and scene.location_id in loc_lookup:
        loc = loc_lookup[scene.location_id]
        if loc.assets.reference:
            loc_ref_path = project_path.parent / loc.assets.reference
            if loc_ref_path.exists():
                loc_ref = loc_ref_path
                print(f"Location ref: {loc.name} -> {loc_ref}")

    location = loc_lookup.get(scene.location_id) if scene.location_id else None

    prev_panel_path = None
    for i, panel in enumerate(scene.panels[:3]):
        print()
        print(f"--- Panel {panel.number} ---")
        print(f"Shot: {panel.composition.shot_type.value}, Angle: {panel.composition.angle.value}")
        print(f"Action: {panel.action}")
        if panel.continues_from_previous:
            print(f"Continuity: {panel.continuity_note}")
        if panel.characters:
            chars = ", ".join(f"{pc.character_id[:8]}({pc.expression})" for pc in panel.characters)
            print(f"Characters: {chars}")

        # Generate image
        print("Generating image...")
        image_data, generation_info = await panel_gen.generate_panel(
            panel=panel,
            characters=char_lookup,
            location=location,
            time_of_day=scene.time_of_day,
            character_references=char_refs,
            location_reference=loc_ref,
            previous_panel_image=prev_panel_path if panel.continues_from_previous else None,
            scene_number=scene.number,
            chapter_number=chapter.number,
        )

        # Save image - organize by scene subfolder: panels/scene_{n}/panel_{n}.png
        scene_dir = panels_dir / f"scene_{scene.number}"
        scene_dir.mkdir(parents=True, exist_ok=True)

        panel_path = scene_dir / f"panel_{panel.number}.png"
        panel_path.write_bytes(image_data)
        print(f"Saved: {panel_path}")

        # Save metadata JSON
        metadata_path = scene_dir / f"panel_{panel.number}.json"
        metadata_path.write_text(json.dumps(generation_info, indent=2))
        print(f"Metadata: {metadata_path}")

        # Update previous panel path for next iteration
        prev_panel_path = panel_path

    print()
    print("=" * 60)
    print("DONE!")
    print(f"Generated images in: {panels_dir}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
