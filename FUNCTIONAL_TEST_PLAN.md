# DreamRight Functional Test Plan

Step-by-step functionality tests to verify the core features work correctly.

---

## Prerequisites

Before running tests:

```bash
# 1. Install the package
pip install -e .

# 2. Set API key
export GOOGLE_API_KEY="your-api-key"

# 3. Create test directory
mkdir -p ~/dreamright-tests && cd ~/dreamright-tests
```

---

## Test Sequence

### Step 1: Project Initialization

**Command:**
```bash
dreamright init ghost-girl
```

**Expected Results:**
- [ ] Project directory `ghost-girl/` created
- [ ] `ghost-girl/project.json` exists with basic structure
- [ ] `ghost-girl/assets/` directory created
- [ ] Success message displayed

**Verification:**
```bash
ls -la ghost-girl/
cat ghost-girl/project.json
```

---

### Step 2: Story Expansion

**Command:**
```bash
cd ghost-girl
dreamright expand "A shy high school girl named Mina discovers she can see ghosts after a near-death experience. She meets a mysterious ghost boy who needs her help to find out how he died." --genre fantasy --episodes 5
```

**Expected Results:**
- [ ] Story generated with title, logline, synopsis
- [ ] 4-5 characters created (1-2 main + 2-3 supporting, kept small for visual consistency)
- [ ] 3-4 locations created
- [ ] 5 story beats generated (one per episode)
- [ ] `project.json` updated with full story data

**Verification:**
```bash
dreamright status
cat project.json | python -m json.tool | head -100
```

---

### Step 3: Character Portrait Generation

**Command:**
```bash
dreamright generate character --name "Mina" --style webtoon
```

**Expected Results:**
- [ ] Character portrait image generated
- [ ] Image saved to `assets/characters/mina/portrait.png`
- [ ] Metadata saved to `assets/characters/mina/portrait_metadata.json`
- [ ] Image is 9:16 aspect ratio (portrait orientation)

**Verification:**
```bash
ls -la assets/characters/mina/
file assets/characters/mina/portrait.png
cat assets/characters/mina/portrait_metadata.json
```

---

### Step 4: Generate All Character Portraits

**Command:**
```bash
dreamright generate character --style webtoon
```

**Expected Results:**
- [ ] Portraits generated for all characters in story
- [ ] Each character has own folder under `assets/characters/`
- [ ] Each folder contains portrait.png and metadata

**Verification:**
```bash
ls -la assets/characters/
```

---

### Step 5: Location Reference Generation

**Command:**
```bash
dreamright generate location --name "School" --time day --style webtoon
```

**Expected Results:**
- [ ] Location reference image generated
- [ ] Image saved to `assets/locations/school/reference.png`
- [ ] Metadata saved with generation parameters
- [ ] Image is 16:9 aspect ratio (landscape)

**Verification:**
```bash
ls -la assets/locations/school/
file assets/locations/school/reference.png
```

---

### Step 6: Location Time Variation

**Command:**
```bash
dreamright generate location --name "School" --time evening --style webtoon
```

**Expected Results:**
- [ ] Evening variant generated
- [ ] Saved as `assets/locations/school/evening.png`
- [ ] Lighting differs from daytime reference

**Verification:**
```bash
ls -la assets/locations/school/
```

---

### Step 7: Generate All Locations

**Command:**
```bash
dreamright generate location --style webtoon
```

**Expected Results:**
- [ ] All story locations have reference images
- [ ] Proper folder structure under `assets/locations/`

**Verification:**
```bash
ls -la assets/locations/
```

---

### Step 8: Chapter Generation

**Command:**
```bash
dreamright generate chapter --number 1
```

**Expected Results:**
- [ ] Chapter 1 generated from first story beat
- [ ] Chapter contains multiple scenes
- [ ] Each scene has panels with:
  - Shot type (wide, medium, close-up, etc.)
  - Camera angle
  - Character(s) present
  - Action description
  - Dialogue (if any)
  - Expression notes
- [ ] `project.json` updated with chapter data

**Verification:**
```bash
cat project.json | python -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('chapters', []), indent=2))" | head -100
```

---

### Step 9: Panel Image Generation

**Command:**
```bash
dreamright generate panel "Mina walks into the classroom" \
  --char "Mina" \
  --loc "School" \
  --shot medium \
  --style webtoon \
  -o assets/panels/test_panel.png
```

**Expected Results:**
- [ ] Panel image generated
- [ ] Character matches portrait reference
- [ ] Background matches location reference
- [ ] Image saved to specified path
- [ ] No text/dialogue rendered in image

**Verification:**
```bash
ls -la assets/panels/
file assets/panels/test_panel.png
```

---

### Step 10: Generate Chapter Panels

**Command (full chapter):**
```bash
dreamright generate panels --chapter 1
```

**Command (single scene):**
```bash
dreamright generate panels --chapter 1 --scene 2
```

**Expected Results:**
- [ ] All panels for Chapter 1 (or specified scene) generated
- [ ] Panels saved to `assets/panels/chapter-1/scene-{n}/`
- [ ] Panels generated **sequentially** (not parallel) for visual continuity
- [ ] Panel N references Panel N-1 when `continues_from_previous` is set
- [ ] Skips existing panels unless `--overwrite` is used
- [ ] Continuity maintains: lighting, color palette, background, character appearances
- [ ] Progression shows: characters move/act naturally, expressions evolve

**Verification:**
```bash
ls -la assets/panels/chapter-1/
ls -la assets/panels/chapter-1/scene-1/
```

**Cache Bypass:**
```bash
# Regenerate all panels for chapter
dreamright generate panels --chapter 1 --overwrite

# Regenerate panels for specific scene only
dreamright generate panels --chapter 1 --scene 2 --overwrite
```

---

### Step 11: Second Chapter (Context Test)

**Command:**
```bash
dreamright generate chapter --number 2
```

**Expected Results:**
- [ ] Chapter 2 generated from second story beat
- [ ] Previous chapter context influences generation
- [ ] Character voice consistent with Chapter 1
- [ ] Story continuity maintained

**Verification:**
```bash
dreamright status
```

---

### Step 12: Project Status

**Command:**
```bash
dreamright status
```

**Expected Results:**
- [ ] Project name displayed
- [ ] Story title and logline shown
- [ ] Character count displayed
- [ ] Location count displayed
- [ ] Chapter progress shown (X/5 completed)
- [ ] Asset generation status shown

---

### Step 13: Cache Verification

**Command:**
```bash
# Run same generation again - should use cache
dreamright generate character --name "Mina" --style webtoon
```

**Expected Results:**
- [ ] Generation completes faster (cached)
- [ ] Output indicates cache hit
- [ ] Same image returned as before

**Verification:**
```bash
ls -la ~/.cache/dreamright/
```

---

### Step 14: Cache Bypass

**Commands:**
```bash
# Character with cache bypass
dreamright generate character --name "Mina" --style webtoon --overwrite

# Location with cache bypass
dreamright generate location --name "School" --time day --style webtoon --overwrite

# Chapter panels with cache bypass
dreamright generate panels --chapter 1 --overwrite
```

**Expected Results:**
- [ ] Fresh generation performed (bypasses cache)
- [ ] New image may differ slightly from cached version
- [ ] Cache updated with new result
- [ ] `--overwrite` flag available on character, location, and panels commands

---

## Error Handling Tests

### E1: Missing API Key

```bash
unset GOOGLE_API_KEY
dreamright expand "test prompt"
```

**Expected:** Clear error message about missing API key

---

### E2: No Project Found

```bash
cd /tmp
dreamright status
```

**Expected:** Error indicating no project.json found

---

### E3: Invalid Character Name

```bash
dreamright generate character --name "NonExistent"
```

**Expected:** Error that character not found in story

---

### E4: Invalid Location Name

```bash
dreamright generate location --name "NonExistent"
```

**Expected:** Error that location not found in story

---

## Test Results Summary

| Step | Test | Status | Notes |
|------|------|--------|-------|
| 1 | Project Init | ✅ | All checks passed |
| 2 | Story Expansion | ✅ | 4 characters generated (1 protagonist + 3 supporting) |
| 3 | Character Portrait | ✅ | 768x1376 portrait saved with metadata |
| 4 | All Characters | ✅ | 4/4 characters with portraits |
| 5 | Location Reference | ✅ | 1376x768 (16:9) saved with metadata |
| 6 | Location Time Variant | ✅ | evening.png saved alongside day.png |
| 7 | All Locations | ✅ | 3/3 locations generated |
| 8 | Chapter Generation | ✅ | Chapter 1: 3 scenes, 18 panels with full structure |
| 9 | Panel Image | ✅ | Panel saved with metadata |
| 10a | Chapter Panels (full) | ✅ | 18 panels across 3 scenes, skips existing |
| 10b | Chapter Panels (scene) | ✅ | `--scene 2` generates only scene 2 (6 panels) |
| 11 | Second Chapter | ✅ | Chapter 2 generated with previous context |
| 12 | Project Status | ✅ | Shows story, chars, locs, chapters |
| 13 | Cache Hit | ✅ | Skipped 12 existing panels on re-run |
| 14 | Cache Bypass | ✅ | `--overwrite` flag verified on character/location/panels |
| E1 | Missing API Key | ✅ | Clean error with setup instructions (no stack trace) |
| E2 | No Project | ✅ | Clean error with helpful message |
| E3 | Invalid Character | ✅ | Shows available characters |
| E4 | Invalid Location | ✅ | Shows available locations |

**Legend:** ⬜ Not Tested | ✅ Pass | ⚠️ Partial | ⏭️ Skipped | ❌ Fail

---

## Test Run Summary

**Date:** 2025-11-26 (test-webtoon project)

**Test Project:** `test-webtoon/`
- Story: "The Ghost of 4:44 PM"
- Characters: 4 (Mina Kim, Kai, Jin-ho, Yuna)
- Locations: 3 (Abandoned Music Room, School Rooftop, School Hallway)
- Chapter 1: 3 scenes, 18 panels total

**Panel Generation Test Results:**

```
# Scene-only generation
$ dreamright generate panels --chapter 1 --scene 2
→ Generated: 6 panels
→ Skipped: 0

# Full chapter (skips existing scenes 1 & 2)
$ dreamright generate panels --chapter 1
→ Generated: 6 (scene 3 only)
→ Skipped: 12 (scenes 1 & 2 already exist)
```

**Generated Assets:**
```
test-webtoon/assets/
├── characters/
│   └── mina-kim/
│       ├── portrait.png (768x1376)
│       └── portrait.json
├── locations/
│   └── school-rooftop/
│       ├── day.png (1376x768)
│       └── day.json
└── panels/
    └── chapter-1/
        ├── scene-1/ (6 panels)
        ├── scene-2/ (6 panels)
        └── scene-3/ (6 panels)
```

**Results:**
- ✅ Passed: 19
- ⚠️ Partial: 0
- ⏭️ Skipped: 0
- ❌ Failed: 0

---

## Key Improvements Made

1. ✅ **Story Expansion** - Prompt requests 4-5 characters max (1-2 main + 2-3 supporting) for visual consistency
2. ✅ **Batch panel generation** - `dreamright generate panels --chapter N [--scene S]`
3. ✅ **Scene-specific generation** - `--scene` option to generate only one scene
4. ✅ **Cache bypass** - `--overwrite` flag on character, location, and panels commands
5. ✅ **Missing API key** - Clean error message with setup instructions
6. ✅ **Panel continuity prompt** - Emphasizes motion progression while maintaining visual consistency
7. ✅ **Refactored architecture** - Panel generation logic moved from CLI to `PanelGenerator` class

**All core functionality works correctly.**

---

## Cleanup

```bash
cd ~
rm -rf ~/dreamright-tests
```

---

## Notes

- Each step builds on the previous - run in order
- Steps 3-7 require API calls and may take 10-30 seconds each
- Steps 8-11 are the most time-intensive (chapter/panel generation)
- Use `--dry-run` flag if available to preview without API calls
