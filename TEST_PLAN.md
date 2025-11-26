# DreamRight Test Plan

This document outlines the comprehensive testing strategy for the DreamRight webtoon/drama generation tool.

## Table of Contents

1. [Overview](#overview)
2. [Test Categories](#test-categories)
3. [Unit Tests](#unit-tests)
4. [Integration Tests](#integration-tests)
5. [End-to-End Tests](#end-to-end-tests)
6. [Test Infrastructure](#test-infrastructure)
7. [Test Data & Fixtures](#test-data--fixtures)
8. [Execution Plan](#execution-plan)

---

## Overview

### Testing Goals
- Ensure correctness of all generation pipelines
- Validate data model integrity and serialization
- Verify CLI commands work as expected
- Test caching behavior and persistence
- Confirm project storage and asset management
- Validate error handling and edge cases

### Testing Stack
- **Framework:** pytest + pytest-asyncio
- **Mocking:** unittest.mock / pytest-mock
- **Coverage:** pytest-cov
- **Fixtures:** pytest fixtures with conftest.py

---

## Test Categories

| Category | Scope | API Calls | Run Frequency |
|----------|-------|-----------|---------------|
| Unit | Single function/class | Mocked | Every commit |
| Integration | Module interactions | Mocked | Every PR |
| E2E | Full workflows | Real (optional) | Pre-release |
| Smoke | Critical paths | Real | Daily/Weekly |

---

## Unit Tests

### 1. Models (`tests/test_models.py`)

**Test Cases:**

| Test | Description | Priority |
|------|-------------|----------|
| `test_story_creation` | Create Story with valid data | High |
| `test_story_validation_errors` | Invalid story data raises ValidationError | High |
| `test_character_role_enum` | CharacterRole enum values are correct | Medium |
| `test_shot_type_enum` | ShotType enum values are correct | Medium |
| `test_camera_angle_enum` | CameraAngle enum values are correct | Medium |
| `test_panel_model` | Panel model with all fields | High |
| `test_scene_model` | Scene with multiple panels | High |
| `test_chapter_model` | Chapter with scenes and panels | High |
| `test_project_get_character_by_name` | Lookup character by name works | High |
| `test_project_get_location_by_id` | Lookup location by ID works | High |
| `test_model_serialization` | Models serialize to JSON correctly | High |
| `test_model_deserialization` | Models deserialize from JSON correctly | High |

### 2. Storage (`tests/test_storage.py`)

**Test Cases:**

| Test | Description | Priority |
|------|-------------|----------|
| `test_json_storage_save_project` | Save project to JSON file | High |
| `test_json_storage_load_project` | Load project from JSON file | High |
| `test_json_storage_project_not_found` | Raises error for missing project | High |
| `test_project_manager_init` | Initialize new project creates structure | High |
| `test_project_manager_save_character_asset` | Save character portrait with metadata | High |
| `test_project_manager_save_location_asset` | Save location image with metadata | High |
| `test_project_manager_save_panel_asset` | Save panel image with metadata | High |
| `test_asset_backup_on_overwrite` | Backup created before overwriting asset | Medium |
| `test_slugify_folder_names` | Folder names are slugified correctly | Medium |
| `test_metadata_json_format` | Metadata files have correct structure | Medium |

### 3. Gemini Client (`tests/test_gemini_client.py`)

**Test Cases:**

| Test | Description | Priority |
|------|-------------|----------|
| `test_lru_cache_get_set` | Cache stores and retrieves values | High |
| `test_lru_cache_eviction` | LRU eviction when capacity exceeded | High |
| `test_lru_cache_persistence` | Cache persists to disk and reloads | High |
| `test_cache_key_generation` | Consistent cache keys from prompts | Medium |
| `test_cache_key_with_images` | Image file hashing for cache keys | Medium |
| `test_generate_text_cached` | Text generation returns cached result | High |
| `test_generate_structured_cached` | Structured generation uses cache | High |
| `test_generate_image_cached` | Image generation uses cache | High |
| `test_overwrite_cache_flag` | overwrite_cache bypasses cache | High |
| `test_api_error_handling` | API errors are handled gracefully | High |

### 4. Story Generator (`tests/test_generators/test_story.py`)

**Test Cases:**

| Test | Description | Priority |
|------|-------------|----------|
| `test_expand_story_basic` | Expand simple premise to full story | High |
| `test_expand_story_with_genre` | Genre parameter affects output | Medium |
| `test_expand_story_with_episodes` | Episode count parameter works | Medium |
| `test_expand_story_character_count` | At least 5 characters generated | Medium |
| `test_expand_story_location_count` | At least 3 locations generated | Medium |
| `test_story_beats_structure` | Story beats follow arc structure | High |
| `test_character_visual_tags` | Characters have visual descriptions | High |

### 5. Character Generator (`tests/test_generators/test_character.py`)

**Test Cases:**

| Test | Description | Priority |
|------|-------------|----------|
| `test_generate_portrait` | Generate character portrait image | High |
| `test_generate_three_view` | Generate front/side/back views | High |
| `test_portrait_aspect_ratio` | Portrait is 9:16 aspect ratio | Medium |
| `test_art_style_parameter` | Art style affects prompt | Medium |
| `test_character_visual_tags_in_prompt` | Visual tags included in prompt | High |

### 6. Location Generator (`tests/test_generators/test_location.py`)

**Test Cases:**

| Test | Description | Priority |
|------|-------------|----------|
| `test_generate_reference_image` | Generate location reference | High |
| `test_generate_time_variation` | Generate time-of-day variant | High |
| `test_reference_aspect_ratio` | Reference is 16:9 aspect ratio | Medium |
| `test_time_of_day_lighting` | Time affects lighting in prompt | Medium |
| `test_weather_parameter` | Weather affects prompt | Low |

### 7. Chapter Generator (`tests/test_generators/test_chapter.py`)

**Test Cases:**

| Test | Description | Priority |
|------|-------------|----------|
| `test_generate_chapter_basic` | Generate chapter from story beat | High |
| `test_chapter_has_scenes` | Chapter contains scenes | High |
| `test_scenes_have_panels` | Scenes contain panels | High |
| `test_panel_continuity_markers` | Continuity flags are set | High |
| `test_two_tier_context_headlines` | Previous chapter headlines included | High |
| `test_two_tier_context_details` | Last 2 chapters have full details | High |
| `test_shot_type_variety` | Varied shot types in chapter | Medium |
| `test_dialogue_types` | Different dialogue types used | Medium |

### 8. Panel Generator (`tests/test_generators/test_panel.py`)

**Test Cases:**

| Test | Description | Priority |
|------|-------------|----------|
| `test_generate_panel_basic` | Generate panel from specification | High |
| `test_panel_with_character_ref` | Character reference image used | High |
| `test_panel_with_location_ref` | Location reference image used | High |
| `test_panel_with_previous_panel` | Previous panel for continuity | High |
| `test_panel_aspect_ratio_normal` | Normal panel is 4:3 | Medium |
| `test_panel_aspect_ratio_splash` | Splash page is 9:16 | Medium |
| `test_no_text_in_image` | Prompt specifies no text | Medium |

---

## Integration Tests

### 1. Generation Pipeline (`tests/integration/test_pipeline.py`)

**Test Cases:**

| Test | Description | Priority |
|------|-------------|----------|
| `test_story_to_characters_flow` | Story expansion → Character generation | High |
| `test_story_to_locations_flow` | Story expansion → Location generation | High |
| `test_chapter_generation_flow` | Story → Chapter → Panels | High |
| `test_multi_chapter_continuity` | Generate 3 chapters with context | High |
| `test_full_project_creation` | Init → Expand → Assets → Chapters | High |

### 2. Storage Integration (`tests/integration/test_storage_integration.py`)

**Test Cases:**

| Test | Description | Priority |
|------|-------------|----------|
| `test_save_and_reload_project` | Full project save/load cycle | High |
| `test_asset_organization` | Assets in correct folders | High |
| `test_incremental_saves` | Multiple saves don't corrupt data | High |
| `test_large_project_performance` | 10+ chapters, 100+ panels | Medium |

### 3. Cache Integration (`tests/integration/test_cache_integration.py`)

**Test Cases:**

| Test | Description | Priority |
|------|-------------|----------|
| `test_cache_across_sessions` | Cache persists between runs | High |
| `test_cache_invalidation` | Stale cache entries cleared | Medium |
| `test_concurrent_cache_access` | Multiple async cache reads | Medium |

---

## End-to-End Tests

### CLI Commands (`tests/e2e/test_cli.py`)

**Test Cases:**

| Test | Description | Priority |
|------|-------------|----------|
| `test_cli_init` | `dreamright init <name>` creates project | High |
| `test_cli_expand` | `dreamright expand <prompt>` works | High |
| `test_cli_status` | `dreamright status` shows project info | High |
| `test_cli_generate_character` | `generate character --name X` works | High |
| `test_cli_generate_location` | `generate location --name X` works | High |
| `test_cli_generate_panel` | `generate panel <desc>` works | High |
| `test_cli_generate_chapter` | `generate chapter` works | High |
| `test_cli_help` | All commands have help text | Medium |
| `test_cli_error_no_project` | Error when no project.json | High |
| `test_cli_error_missing_api_key` | Error when API key missing | High |

### Workflow Tests (`tests/e2e/test_workflows.py`)

**Test Cases:**

| Test | Description | Priority |
|------|-------------|----------|
| `test_complete_webtoon_workflow` | Full story creation pipeline | High |
| `test_resume_existing_project` | Continue work on saved project | High |
| `test_regenerate_single_asset` | Regenerate one character | Medium |

---

## Test Infrastructure

### Directory Structure

```
tests/
├── conftest.py                 # Shared fixtures
├── test_models.py              # Model unit tests
├── test_storage.py             # Storage unit tests
├── test_gemini_client.py       # Client unit tests
├── test_generators/
│   ├── __init__.py
│   ├── test_story.py
│   ├── test_character.py
│   ├── test_location.py
│   ├── test_chapter.py
│   └── test_panel.py
├── integration/
│   ├── __init__.py
│   ├── test_pipeline.py
│   ├── test_storage_integration.py
│   └── test_cache_integration.py
├── e2e/
│   ├── __init__.py
│   ├── test_cli.py
│   └── test_workflows.py
└── fixtures/
    ├── sample_project.json
    ├── sample_story.json
    ├── sample_chapter.json
    └── images/
        ├── sample_portrait.png
        └── sample_location.png
```

### conftest.py Fixtures

```python
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def temp_project_dir(tmp_path):
    """Create temporary project directory."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    return project_dir

@pytest.fixture
def mock_gemini_client():
    """Mock GeminiClient with predefined responses."""
    client = MagicMock()
    client.generate_text = AsyncMock(return_value="Generated text")
    client.generate_structured = AsyncMock()
    client.generate_image = AsyncMock(return_value=b"fake_image_data")
    return client

@pytest.fixture
def sample_story():
    """Return sample Story model for testing."""
    from dreamright.models import Story
    return Story(
        title="Test Story",
        logline="A test story for testing.",
        genre="fantasy",
        tone="dramatic",
        themes=["courage", "friendship"],
        synopsis="A hero embarks on a journey.",
        beats=["Introduction", "Rising action", "Climax", "Resolution"]
    )

@pytest.fixture
def sample_character():
    """Return sample Character model for testing."""
    from dreamright.models import Character, CharacterRole
    return Character(
        name="Test Hero",
        role=CharacterRole.PROTAGONIST,
        age="25",
        description="A brave hero with dark hair.",
        visual_tags=["dark hair", "blue eyes", "tall"],
        personality="Brave and determined"
    )

@pytest.fixture
def sample_project(sample_story, sample_character):
    """Return complete sample Project for testing."""
    from dreamright.models import Project
    return Project(
        name="test-project",
        story=sample_story,
        characters=[sample_character],
        locations=[],
        chapters=[]
    )
```

### Mocking Strategy

#### Gemini API Mocking

```python
# For unit tests - mock the entire client
@pytest.fixture
def mock_gemini_responses():
    return {
        "story_expansion": {...},  # Sample story JSON
        "chapter_generation": {...},  # Sample chapter JSON
        "image_bytes": b"PNG_FAKE_DATA"
    }

# For integration tests - mock at HTTP level
@pytest.fixture
def mock_httpx_client(httpx_mock):
    httpx_mock.add_response(
        url="https://generativelanguage.googleapis.com/*",
        json={"candidates": [{"content": "..."}]}
    )
```

---

## Test Data & Fixtures

### Sample Project (fixtures/sample_project.json)

A complete project with:
- Story with 5 beats
- 5 characters with full details
- 3 locations with descriptions
- 2 chapters with scenes/panels

### Sample Images

- `sample_portrait.png`: 512x912 test character portrait
- `sample_location.png`: 1920x1080 test location background
- `sample_panel.png`: 800x600 test panel image

---

## Execution Plan

### Phase 1: Unit Tests (Week 1)

1. Set up test infrastructure (conftest.py, fixtures)
2. Implement model tests
3. Implement storage tests
4. Implement gemini_client tests (with mocks)
5. Implement generator tests (with mocks)

### Phase 2: Integration Tests (Week 2)

1. Implement pipeline integration tests
2. Implement storage integration tests
3. Implement cache integration tests
4. Add performance benchmarks

### Phase 3: E2E Tests (Week 3)

1. Implement CLI tests with Click testing
2. Implement workflow tests
3. Add smoke tests for real API (optional, gated)

### Running Tests

```bash
# Run all unit tests
pytest tests/ -v --ignore=tests/integration --ignore=tests/e2e

# Run integration tests
pytest tests/integration/ -v

# Run E2E tests (requires API key)
GOOGLE_API_KEY=xxx pytest tests/e2e/ -v

# Run with coverage
pytest tests/ --cov=dreamright --cov-report=html

# Run specific test file
pytest tests/test_models.py -v

# Run tests matching pattern
pytest -k "test_story" -v
```

### CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run unit tests
        run: pytest tests/ --ignore=tests/e2e -v --cov=dreamright

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Unit test coverage | > 80% |
| Integration test coverage | > 60% |
| All critical paths tested | 100% |
| CI build time | < 5 minutes |
| No flaky tests | 0 |

---

## Appendix: Test Naming Conventions

- `test_<function>_<scenario>` - e.g., `test_save_project_empty_story`
- Use descriptive names over short names
- Group related tests in classes: `class TestStoryGenerator:`
- Use `@pytest.mark.slow` for slow tests
- Use `@pytest.mark.integration` for integration tests
- Use `@pytest.mark.e2e` for end-to-end tests
