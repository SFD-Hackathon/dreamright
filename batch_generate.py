#!/usr/bin/env python3
"""
Batch generate multiple DreamRight projects sequentially.

This script allows you to queue up multiple story ideas and generate
complete projects (story, characters, locations, chapters, panels) for each.
Perfect for running overnight or while away from your laptop.
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Retry configuration
MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = 5  # Reduced from 30s since Gemini client has its own retry logic

# Add your story prompts here
PROJECTS = [
    {
        "name": "Vampire Academy",
        "prompt": "At an elite boarding school for vampires, a dhampir guardian-in-training uncovers a conspiracy that threatens both vampire and human worlds.",
        "episodes": 2,
    },
    {
        "name": "Time Loop Detective",
        "prompt": "A detective stuck in a 24-hour time loop must solve a murder that resets every day, with each loop revealing new clues and suspects.",
        "episodes": 3,
    },
    {
        "name": "Cyber Samurai",
        "prompt": "In a dystopian future Tokyo, a former samurai turned hacker fights against megacorporations using both ancient sword techniques and advanced technology.",
        "episodes": 3,
    },
]

LOG_FILE = Path("batch_generate.log")


def log(message: str):
    """Log message to both console and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"[{timestamp}] {message}"
    print(full_message)
    with open(LOG_FILE, "a") as f:
        f.write(full_message + "\n")


def check_project_exists(project_dir: Path) -> bool:
    """Check if project directory and project.json exist with story data."""
    import json
    project_file = project_dir / "project.json"
    if not project_file.exists():
        return False
    try:
        with open(project_file, "r") as f:
            data = json.load(f)
        # Check if story expansion is complete (has characters)
        return len(data.get("characters", [])) > 0
    except Exception:
        return False


def check_characters_generated(project_dir: Path) -> bool:
    """Check if character assets have been generated."""
    assets_dir = project_dir / "assets" / "characters"
    if not assets_dir.exists():
        return False
    # Check if there are any character directories with assets
    for char_dir in assets_dir.iterdir():
        if char_dir.is_dir() and (char_dir / "portrait.png").exists():
            return True
    return False


def check_locations_generated(project_dir: Path) -> bool:
    """Check if location assets have been generated."""
    assets_dir = project_dir / "assets" / "locations"
    if not assets_dir.exists():
        return False
    # Check if there are any location directories with assets
    for loc_dir in assets_dir.iterdir():
        if loc_dir.is_dir() and (loc_dir / "reference.png").exists():
            return True
    return False


def check_chapter_generated(project_dir: Path, beat_num: int) -> bool:
    """Check if chapter script has been generated."""
    import json
    project_file = project_dir / "project.json"
    if not project_file.exists():
        return False

    try:
        with open(project_file, "r") as f:
            data = json.load(f)
        chapters = data.get("chapters", [])
        # Check if beat exists and has scenes
        for chapter in chapters:
            if chapter.get("beat_number") == beat_num and chapter.get("scenes"):
                return True
    except Exception:
        pass
    return False


def check_panels_generated(project_dir: Path, beat_num: int) -> bool:
    """Check if panels have been generated for a chapter."""
    panels_dir = project_dir / "assets" / "panels" / f"chapter-{beat_num}"
    if not panels_dir.exists():
        return False
    # Check if there are any panel images
    for scene_dir in panels_dir.iterdir():
        if scene_dir.is_dir():
            for panel_file in scene_dir.glob("panel-*.png"):
                return True
    return False


def run_command(cmd: list[str], description: str, cwd: Optional[Path] = None, retry: bool = True) -> bool:
    """Run a command with retry logic and return success status.

    Args:
        cmd: Command and arguments
        description: Human-readable description
        cwd: Working directory (optional)
        retry: Whether to retry on failure (default: True)
    """
    log(f"  → {description}")
    log(f"    Command: {' '.join(cmd)}")
    if cwd:
        log(f"    Working directory: {cwd}")

    # Prepare environment with API key
    env = os.environ.copy()
    if "GOOGLE_API_KEY" not in env:
        log(f"    ⚠ Warning: GOOGLE_API_KEY not set in environment")

    max_attempts = MAX_RETRIES if retry else 1

    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            log(f"    ↻ Retry attempt {attempt}/{max_attempts}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout per command
                env=env,
                cwd=cwd,
            )

            if result.returncode == 0:
                log(f"    ✓ Success" + (f" (on attempt {attempt})" if attempt > 1 else ""))
                if result.stdout:
                    log(f"    Output: {result.stdout[:200]}...")
                return True
            else:
                log(f"    ✗ Failed (exit code {result.returncode})")
                if result.stderr:
                    log(f"    Error: {result.stderr[:500]}")

                # If not last attempt, sleep before retry
                if attempt < max_attempts:
                    log(f"    Sleeping {RETRY_SLEEP_SECONDS} seconds before retry...")
                    time.sleep(RETRY_SLEEP_SECONDS)

        except subprocess.TimeoutExpired:
            log(f"    ✗ Timeout (exceeded 1 hour)")
            if attempt < max_attempts:
                log(f"    Sleeping {RETRY_SLEEP_SECONDS} seconds before retry...")
                time.sleep(RETRY_SLEEP_SECONDS)
        except Exception as e:
            log(f"    ✗ Exception: {str(e)}")
            if attempt < max_attempts:
                log(f"    Sleeping {RETRY_SLEEP_SECONDS} seconds before retry...")
                time.sleep(RETRY_SLEEP_SECONDS)

    log(f"    ✗ All {max_attempts} attempts failed")
    return False


def get_executable() -> str:
    """Find the dreamright executable."""
    # 1. Try local venv
    venv_path = Path.cwd() / ".venv" / "bin" / "dreamright"
    if venv_path.exists():
        return str(venv_path)
    
    # 2. Try system path
    import shutil
    path = shutil.which("dreamright")
    if path:
        return path
        
    # 3. Fallback
    return "dreamright"


def generate_project(project_config: dict) -> bool:
    """Generate a complete project from config."""
    name = project_config["name"]
    prompt = project_config["prompt"]
    episodes = project_config.get("episodes", 3)

    log(f"\n{'='*80}")
    log(f"Starting project: {name}")
    log(f"Prompt: {prompt}")
    log(f"Episodes: {episodes}")
    log(f"{'='*80}\n")

    # Ensure projects directory exists
    projects_root = Path.cwd() / "projects"
    projects_root.mkdir(exist_ok=True)

    project_dir = projects_root / name.lower().replace(" ", "-")
    dreamright_cmd = get_executable()
    log(f"Using executable: {dreamright_cmd}")

    # Step 1: Initialize project (skip if directory already exists)
    if project_dir.exists():
        log(f"  ⏭ Project directory already exists, skipping init")
    else:
        # Run in current dir (root), it will create the project folder
        if not run_command(
            [dreamright_cmd, "init", name],
            f"Initialize project '{name}'"
        ):
            log(f"✗ Failed to initialize project '{name}', skipping")
            return False

    # Step 2: Expand story (skip if project has character data)
    if check_project_exists(project_dir):
        log(f"  ⏭ Story already generated with characters, skipping expand")
    else:
        # Run INSIDE the project directory
        if not run_command(
            [dreamright_cmd, "expand", prompt, "--episodes", str(episodes)],
            f"Generate story for '{name}'",
            cwd=project_dir
        ):
            log(f"✗ Failed to generate story for '{name}', skipping")
            return False

    # Assets generation (no sleep needed - rate limiting handled by client)

    # Step 3: Generate all characters (skip if already done)
    if check_characters_generated(project_dir):
        log(f"  ⏭ Characters already generated, skipping")
    else:
        if not run_command(
            [dreamright_cmd, "generate", "character"],
            f"Generate all characters for '{name}'",
            cwd=project_dir
        ):
            log(f"⚠ Warning: Character generation failed for '{name}', continuing anyway")

    # No sleep needed between asset types

    # Step 4: Generate all locations (skip if already done)
    if check_locations_generated(project_dir):
        log(f"  ⏭ Locations already generated, skipping")
    else:
        if not run_command(
            [dreamright_cmd, "generate", "location"],
            f"Generate all locations for '{name}'",
            cwd=project_dir
        ):
            log(f"⚠ Warning: Location generation failed for '{name}', continuing anyway")

    # Step 5: Generate chapters and panels
    for beat_num in range(1, episodes + 1):
        # No sleep needed - rate limiting handled by client

        # Generate chapter script (skip if already done, with retries)
        if check_chapter_generated(project_dir, beat_num):
            log(f"  ⏭ Chapter {beat_num} script already generated, skipping")
        else:
            if not run_command(
                [dreamright_cmd, "generate", "chapter", "--beat", str(beat_num)],
                f"Generate chapter script for beat {beat_num}",
                cwd=project_dir
            ):
                log(f"✗ Chapter {beat_num} script generation failed after {MAX_RETRIES} attempts, skipping panels")
                continue

        # No sleep needed before panels

        # Generate panels (skip if already done, with retries)
        if check_panels_generated(project_dir, beat_num):
            log(f"  ⏭ Panels for chapter {beat_num} already generated, skipping")
        else:
            if not run_command(
                [dreamright_cmd, "generate", "panels", "--chapter", str(beat_num)],
                f"Generate panels for chapter {beat_num}",
                cwd=project_dir
            ):
                log(f"✗ Panel generation failed for chapter {beat_num} after {MAX_RETRIES} attempts")

    log(f"\n✓ Completed project: {name}\n")
    return True


def main():
    """Main entry point."""
    # Clear log file at start
    with open(LOG_FILE, "w") as f:
        f.write("")

    log(f"\n{'#'*80}")
    log(f"# BATCH PROJECT GENERATION")
    log(f"# Total projects: {len(PROJECTS)}")
    log(f"# Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'#'*80}\n")

    successes = 0
    failures = 0

    start_time = time.time()

    for i, project in enumerate(PROJECTS, 1):
        log(f"\n[Project {i}/{len(PROJECTS)}]")

        if generate_project(project):
            successes += 1
        else:
            failures += 1

        # Minimal sleep between projects to avoid API rate limits
        if i < len(PROJECTS):
            log(f"\n  Brief pause before next project...\n")
            time.sleep(2)

    elapsed = time.time() - start_time
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)

    log(f"\n{'#'*80}")
    log(f"# BATCH GENERATION COMPLETE")
    log(f"# Successful: {successes}/{len(PROJECTS)}")
    log(f"# Failed: {failures}/{len(PROJECTS)}")
    log(f"# Total time: {int(hours)}h {int(minutes)}m {int(seconds)}s")
    log(f"# Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'#'*80}\n")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
