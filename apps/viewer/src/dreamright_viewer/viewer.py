#!/usr/bin/env python3
"""
Local web server for viewing DreamRight webtoon projects with vertical scroll format.
"""

import argparse
import html as html_escape
import http.server
import json
import mimetypes
import os
import re
import socketserver
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

DEFAULT_PORT = 8000
PROJECTS_DIR = Path("projects")

# Safe project ID pattern (alphanumeric, hyphens, underscores only)
SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def slugify(text: str) -> str:
    """Convert text to a URL/filename-friendly slug.

    Args:
        text: Text to slugify

    Returns:
        Slugified text (lowercase, hyphens instead of spaces)
    """
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and underscores with hyphens
    text = re.sub(r'[\s_]+', '-', text)
    # Remove any characters that aren't alphanumeric or hyphens
    text = re.sub(r'[^\w\-]', '', text)
    # Remove multiple consecutive hyphens
    text = re.sub(r'-+', '-', text)
    # Strip leading/trailing hyphens
    text = text.strip('-')
    return text


def escape(text: str) -> str:
    """Safely escape text for HTML output."""
    if text is None:
        return ""
    return html_escape.escape(str(text))


def validate_project_id(project_id: str) -> bool:
    """Validate project ID to prevent path traversal."""
    if not project_id or not SAFE_ID_PATTERN.match(project_id):
        return False
    # Extra check: ensure no path separators
    if "/" in project_id or "\\" in project_id or ".." in project_id:
        return False
    return True


def safe_project_path(project_id: str) -> Path | None:
    """Get validated project path, returns None if invalid."""
    if not validate_project_id(project_id):
        return None
    project_path = (PROJECTS_DIR / project_id).resolve()
    # Ensure path is under PROJECTS_DIR
    try:
        project_path.relative_to(PROJECTS_DIR.resolve())
    except ValueError:
        return None
    return project_path


class WebtoonHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler for serving webtoon content."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        # Check for debug mode in query params
        debug_mode = query.get("debug", ["0"])[0] == "1"

        try:
            if path == "/" or path == "":
                self.send_index()
            elif path.startswith("/project/") and "/chapter" not in path:
                # /project/{project_id} - cover page
                parts = path.split("/")
                if len(parts) >= 3:
                    project_id = parts[2]
                    if not validate_project_id(project_id):
                        self.send_error(400, "Invalid project ID")
                        return
                    self.send_project_cover(project_id)
                else:
                    self.send_error(404, "Project not found")
            elif path.startswith("/view/"):
                # /view/{project_id}/chapter/{N}
                parts = path.split("/")
                if len(parts) >= 5 and parts[3] == "chapter":
                    project_id = parts[2]
                    if not validate_project_id(project_id):
                        self.send_error(400, "Invalid project ID")
                        return
                    try:
                        chapter_num = int(parts[4])
                    except ValueError:
                        self.send_error(400, "Invalid chapter number")
                        return
                    self.send_chapter_viewer(project_id, chapter_num, debug_mode, query)
                else:
                    self.send_error(404, "Chapter not found")
            elif path.startswith("/api/projects"):
                self.send_projects_list()
            elif path.startswith("/api/project/"):
                parts = path.split("/")
                if len(parts) < 4:
                    self.send_error(400, "Invalid API request")
                    return
                project_id = parts[3]
                if not validate_project_id(project_id):
                    self.send_error(400, "Invalid project ID")
                    return
                self.send_project_data(project_id)
            elif path.startswith("/projects/"):
                # Serve static files from projects directory only
                self.serve_project_asset(path)
            else:
                # Block all other paths - don't serve arbitrary files
                self.send_error(404, "Not found")
        except Exception as e:
            self.send_error(500, f"Server error: {type(e).__name__}")

    def serve_project_asset(self, path: str):
        """Serve static assets from projects directory with path validation."""
        # Remove leading /projects/
        relative_path = path[10:]  # len("/projects/") = 10

        # Validate and resolve path
        try:
            full_path = (PROJECTS_DIR / relative_path).resolve()
            # Ensure path is under PROJECTS_DIR
            full_path.relative_to(PROJECTS_DIR.resolve())
        except (ValueError, RuntimeError):
            self.send_error(403, "Access denied")
            return

        if not full_path.exists() or not full_path.is_file():
            self.send_error(404, "File not found")
            return

        # Serve the file
        content_type, _ = mimetypes.guess_type(str(full_path))
        content_type = content_type or "application/octet-stream"

        try:
            with open(full_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-type", content_type)
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except IOError:
            self.send_error(500, "Error reading file")

    def load_project(self, project_id: str) -> dict | None:
        """Load project data from project.json with error handling."""
        project_path = safe_project_path(project_id)
        if not project_path:
            return None
        project_json = project_path / "project.json"
        if not project_json.exists():
            return None
        try:
            return json.loads(project_json.read_text())
        except (json.JSONDecodeError, IOError):
            return None

    def send_index(self):
        """Send the main index page listing all projects."""
        projects = []
        if PROJECTS_DIR.exists():
            for project_dir in PROJECTS_DIR.iterdir():
                if project_dir.is_dir():
                    project_json = project_dir / "project.json"
                    if project_json.exists():
                        data = json.loads(project_json.read_text())
                        story = data.get("story", {})
                        chapters = data.get("chapters", [])
                        total_panels = sum(
                            sum(len(scene.get("panels", [])) for scene in ch.get("scenes", []))
                            for ch in chapters
                        )
                        projects.append(
                            {
                                "id": project_dir.name,
                                "name": data.get("name", project_dir.name),
                                "title": story.get("title", "Untitled"),
                                "logline": story.get("logline", ""),
                                "genre": story.get("genre", ""),
                                "chapters": len(chapters),
                                "panels": total_panels,
                                "characters": len(data.get("characters", [])),
                            }
                        )

        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DreamRight Viewer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }
        h1 { text-align: center; margin-bottom: 30px; color: #fff; }
        .projects { max-width: 900px; margin: 0 auto; }
        .project {
            display: block;
            background: #16213e;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            text-decoration: none;
            color: #fff;
            border: 1px solid transparent;
            transition: border-color 0.2s, transform 0.2s;
        }
        .project:hover { border-color: #e94560; transform: translateX(5px); }
        .project h2 { color: #e94560; margin-bottom: 8px; font-size: 1.5rem; }
        .project .genre {
            display: inline-block;
            background: #e94560;
            color: #fff;
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 11px;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        .project .logline { color: #aaa; margin-bottom: 15px; font-style: italic; line-height: 1.5; }
        .project .stats { display: flex; gap: 20px; flex-wrap: wrap; }
        .project .stat {
            background: #0f3460;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 13px;
        }
        .project .stat strong { color: #e94560; }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }
        .empty-state h2 { color: #888; margin-bottom: 15px; }
    </style>
</head>
<body>
    <h1>DreamRight Viewer</h1>
    <div class="projects">
"""
        if projects:
            for p in projects:
                logline = escape(p['logline'][:200]) + ('...' if len(p['logline']) > 200 else '')
                html += f"""
        <a href="/project/{escape(p['id'])}" class="project">
            <span class="genre">{escape(p['genre'])}</span>
            <h2>{escape(p['title'])}</h2>
            <p class="logline">{logline}</p>
            <div class="stats">
                <span class="stat"><strong>{p['chapters']}</strong> chapters</span>
                <span class="stat"><strong>{p['panels']}</strong> panels</span>
                <span class="stat"><strong>{p['characters']}</strong> characters</span>
            </div>
        </a>
"""
        else:
            html += """
        <div class="empty-state">
            <h2>No projects found</h2>
            <p>Create a project with: dreamright init my-project</p>
        </div>
"""

        html += """
    </div>
</body>
</html>
"""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def send_project_cover(self, project_id: str):
        """Send the project cover/introduction page."""
        data = self.load_project(project_id)
        if not data:
            self.send_error(404, "Project not found")
            return

        story = data.get("story", {})
        characters = data.get("characters", [])
        locations = data.get("locations", [])
        chapters = data.get("chapters", [])

        # Build chapter stats
        chapter_stats = []
        total_panels = 0
        for ch in chapters:
            panel_count = sum(len(scene.get("panels", [])) for scene in ch.get("scenes", []))
            total_panels += panel_count
            chapter_stats.append(
                {
                    "number": ch.get("number", 0),
                    "title": ch.get("title", "Untitled"),
                    "summary": ch.get("summary", ""),
                    "scenes": len(ch.get("scenes", [])),
                    "panels": panel_count,
                }
            )

        # Get first character portrait as cover
        cover_img = ""
        if characters:
            first_char = characters[0]
            char_name = slugify(first_char.get("name", ""))
            portrait_path = PROJECTS_DIR / project_id / "assets" / "characters" / char_name / "portrait.png"
            if portrait_path.exists():
                cover_img = f"/projects/{project_id}/assets/characters/{char_name}/portrait.png"

        main_chars = [c for c in characters if c.get("role") == "protagonist"]
        supporting_chars = [c for c in characters if c.get("role") != "protagonist"]

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{story.get('title', 'Project')} - DreamRight</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            color: #fff;
            min-height: 100vh;
        }}
        .back-link {{
            position: fixed;
            top: 20px;
            left: 20px;
            color: #e94560;
            text-decoration: none;
            font-size: 14px;
            z-index: 100;
            background: rgba(0,0,0,0.5);
            padding: 8px 16px;
            border-radius: 20px;
            transition: background 0.2s;
        }}
        .back-link:hover {{ background: rgba(233,69,96,0.3); }}

        .hero {{
            position: relative;
            min-height: 70vh;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }}
        .hero-bg {{
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background-size: cover;
            background-position: center;
            filter: blur(20px) brightness(0.4);
            transform: scale(1.1);
        }}
        .hero-content {{
            position: relative;
            z-index: 1;
            display: flex;
            gap: 50px;
            max-width: 1200px;
            padding: 40px;
            align-items: center;
        }}
        .cover-image {{
            width: 300px;
            height: 450px;
            border-radius: 12px;
            object-fit: cover;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
            border: 3px solid rgba(255,255,255,0.1);
            background: linear-gradient(135deg, #e94560, #ff6b8a);
        }}
        .hero-info {{ max-width: 600px; }}
        .hero-info h1 {{
            font-family: 'Playfair Display', serif;
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 15px;
            line-height: 1.1;
        }}
        .genre-tag {{
            display: inline-block;
            background: #e94560;
            color: #fff;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 20px;
        }}
        .logline {{
            font-size: 1.1rem;
            line-height: 1.7;
            color: rgba(255,255,255,0.85);
            margin-bottom: 25px;
        }}
        .stats {{
            display: flex;
            gap: 30px;
            margin-bottom: 25px;
        }}
        .stat {{ text-align: center; }}
        .stat-value {{
            font-size: 2rem;
            font-weight: 700;
            color: #e94560;
        }}
        .stat-label {{
            font-size: 12px;
            color: rgba(255,255,255,0.6);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .start-btn {{
            display: inline-block;
            background: linear-gradient(135deg, #e94560, #ff6b8a);
            color: #fff;
            padding: 15px 40px;
            border-radius: 30px;
            text-decoration: none;
            font-weight: 600;
            font-size: 16px;
            margin-top: 20px;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 10px 30px rgba(233,69,96,0.4);
        }}
        .start-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 15px 40px rgba(233,69,96,0.5);
        }}

        .content {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 60px 40px;
        }}
        .section {{ margin-bottom: 60px; }}
        .section-title {{
            font-family: 'Playfair Display', serif;
            font-size: 2rem;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 2px solid rgba(255,255,255,0.1);
        }}

        .characters-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 25px;
        }}
        .character-card {{
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .character-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.3);
        }}
        .character-card.protagonist {{ border-color: #e94560; }}
        .character-img {{
            width: 100%;
            height: auto;
            object-fit: contain;
            background: rgba(0,0,0,0.3);
        }}
        .character-info {{ padding: 20px; }}
        .character-name {{
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 5px;
        }}
        .character-role {{
            font-size: 12px;
            color: #e94560;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}
        .character-desc {{
            font-size: 13px;
            color: rgba(255,255,255,0.7);
            line-height: 1.5;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .chapters-list {{
            display: flex;
            flex-direction: column;
            gap: 15px;
        }}
        .chapter-card {{
            display: flex;
            align-items: center;
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 20px 25px;
            text-decoration: none;
            color: #fff;
            border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.2s;
        }}
        .chapter-card:hover {{
            background: rgba(233,69,96,0.2);
            border-color: #e94560;
            transform: translateX(10px);
        }}
        .chapter-num {{
            font-size: 2rem;
            font-weight: 700;
            color: #e94560;
            min-width: 80px;
        }}
        .chapter-details {{ flex: 1; }}
        .chapter-title {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 5px;
        }}
        .chapter-summary {{
            font-size: 13px;
            color: rgba(255,255,255,0.6);
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        .chapter-stats {{
            font-size: 12px;
            color: rgba(255,255,255,0.5);
            min-width: 120px;
            text-align: right;
        }}

        .locations-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 25px;
        }}
        .location-card {{
            position: relative;
            border-radius: 16px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.05);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .location-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.3);
        }}
        .location-card img {{
            width: 100%;
            height: 180px;
            object-fit: cover;
            background: linear-gradient(135deg, #24243e, #302b63);
        }}
        .location-overlay {{
            padding: 20px;
            background: transparent;
        }}
        .location-type {{
            font-size: 12px;
            color: #e94560;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
        }}
        .location-name {{
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        .location-desc {{
            font-size: 13px;
            color: rgba(255,255,255,0.7);
            line-height: 1.5;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        @media (max-width: 768px) {{
            .hero-content {{
                flex-direction: column;
                text-align: center;
                padding: 20px;
            }}
            .cover-image {{ width: 200px; height: 300px; }}
            .hero-info h1 {{ font-size: 2rem; }}
            .stats {{ justify-content: center; }}
        }}

        /* Modal styles */
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.85);
            z-index: 1000;
            overflow-y: auto;
            padding: 40px 20px;
        }}
        .modal-overlay.active {{ display: flex; justify-content: center; align-items: flex-start; }}
        .modal {{
            background: #1a1a2e;
            border-radius: 20px;
            max-width: 900px;
            width: 100%;
            position: relative;
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 25px 80px rgba(0,0,0,0.5);
        }}
        .modal-close {{
            position: absolute;
            top: 15px; right: 20px;
            background: rgba(255,255,255,0.1);
            border: none;
            color: #fff;
            font-size: 24px;
            cursor: pointer;
            width: 40px; height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10;
        }}
        .modal-close:hover {{ background: #e94560; }}
        .modal-header {{
            padding: 30px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            display: flex;
            gap: 25px;
            align-items: flex-start;
        }}
        .modal-portrait {{
            width: 200px;
            flex-shrink: 0;
            border-radius: 12px;
            overflow: hidden;
        }}
        .modal-portrait img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        .modal-title-area {{
            flex: 1;
        }}
        .modal-role {{
            color: #e94560;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}
        .modal-name {{
            font-family: 'Playfair Display', serif;
            font-size: 2rem;
            margin-bottom: 10px;
        }}
        .modal-age {{ color: rgba(255,255,255,0.6); margin-bottom: 15px; }}
        .modal-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .modal-tag {{
            background: rgba(233,69,96,0.2);
            color: #e94560;
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 12px;
        }}
        .modal-body {{
            padding: 30px;
        }}
        .modal-section {{
            margin-bottom: 25px;
        }}
        .modal-section-title {{
            color: #e94560;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .modal-section p {{
            color: rgba(255,255,255,0.8);
            line-height: 1.7;
        }}
        .modal-images {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        .modal-images img {{
            width: 100%;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s;
        }}
        .modal-images img:hover {{ transform: scale(1.02); }}
        .character-card, .location-card {{ cursor: pointer; }}
    </style>
</head>
<body>
    <a href="/" class="back-link">&larr; All Projects</a>

    <div class="hero">
        <div class="hero-bg" style="background-image: url('{cover_img}');"></div>
        <div class="hero-content">
            <img src="{cover_img}" alt="{escape(story.get('title', ''))}" class="cover-image" onerror="this.style.background='linear-gradient(135deg, #e94560, #ff6b8a)'">
            <div class="hero-info">
                <span class="genre-tag">{escape(story.get('genre', 'drama'))}</span>
                <h1>{escape(story.get('title', 'Untitled'))}</h1>
                <p class="logline">{escape(story.get('logline', ''))}</p>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">{len(chapters)}</div>
                        <div class="stat-label">Chapters</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{total_panels}</div>
                        <div class="stat-label">Panels</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{len(characters)}</div>
                        <div class="stat-label">Characters</div>
                    </div>
                </div>
                <a href="/view/{project_id}/chapter/1" class="start-btn">Start Reading</a>
            </div>
        </div>
    </div>

    <div class="content">
        <div class="section">
            <h2 class="section-title">Characters</h2>
            <div class="characters-grid">
"""
        for char in main_chars + supporting_chars:
            char_name = char.get("name", "")
            char_slug = slugify(char_name)
            char_img = f"/projects/{project_id}/assets/characters/{char_slug}/portrait.png"
            char_sheet = f"/projects/{project_id}/assets/characters/{char_slug}/sheet.png"
            role = char.get("role", "supporting")
            role_class = "protagonist" if role == "protagonist" else ""
            desc = char.get("description", {})
            physical = desc.get("physical", "") if isinstance(desc, dict) else ""
            personality = desc.get("personality", "") if isinstance(desc, dict) else ""
            backstory = char.get("backstory", "")
            age = char.get("age", "")
            visual_tags = char.get("visual_tags", [])
            tags_json = json.dumps(visual_tags) if visual_tags else "[]"

            html += f"""
                <div class="character-card {role_class}" onclick="openCharacterModal(this)"
                     data-name="{escape(char_name)}"
                     data-role="{escape(role)}"
                     data-age="{escape(str(age))}"
                     data-physical="{escape(physical)}"
                     data-personality="{escape(personality)}"
                     data-backstory="{escape(backstory)}"
                     data-portrait="{char_img}"
                     data-sheet="{char_sheet}"
                     data-tags='{tags_json}'>
                    <img src="{char_img}" alt="{escape(char_name)}" class="character-img" onerror="this.style.background='linear-gradient(135deg, #24243e, #302b63)'">
                    <div class="character-info">
                        <div class="character-role">{escape(role)}</div>
                        <div class="character-name">{escape(char_name)}</div>
                        <p class="character-desc">{escape(physical[:150])}</p>
                    </div>
                </div>
"""

        html += """
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">Chapters</h2>
            <div class="chapters-list">
"""
        for ch in chapter_stats:
            ch_summary = escape(ch['summary'][:100]) + '...'
            html += f"""
                <a href="/view/{escape(project_id)}/chapter/{ch['number']}" class="chapter-card">
                    <div class="chapter-num">{ch['number']}</div>
                    <div class="chapter-details">
                        <div class="chapter-title">{escape(ch['title'])}</div>
                        <div class="chapter-summary">{ch_summary}</div>
                    </div>
                    <div class="chapter-stats">{ch['scenes']} scenes, {ch['panels']} panels</div>
                </a>
"""

        html += """
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">Locations</h2>
            <div class="locations-grid">
"""
        for loc in locations:
            loc_name = loc.get("name", "")
            loc_slug = slugify(loc_name)
            # Try to get image from assets, fallback to reference.png
            loc_assets = loc.get("assets", {})
            loc_ref = loc_assets.get("reference", "")
            if loc_ref:
                loc_img = f"/projects/{project_id}/{loc_ref}"
            else:
                loc_img = f"/projects/{project_id}/assets/locations/{loc_slug}/reference.png"
            loc_type = loc.get("type", "interior")
            loc_desc = loc.get("description", "")
            loc_visual_tags = loc.get("visual_tags", [])
            loc_tags_json = json.dumps(loc_visual_tags) if loc_visual_tags else "[]"

            html += f"""
                <div class="location-card" onclick="openLocationModal(this)"
                     data-name="{escape(loc_name)}"
                     data-type="{escape(loc_type)}"
                     data-description="{escape(loc_desc)}"
                     data-image="{loc_img}"
                     data-tags='{loc_tags_json}'>
                    <img src="{loc_img}" alt="{escape(loc_name)}" onerror="this.style.display='none'">
                    <div class="location-overlay">
                        <div class="location-type">{escape(loc_type)}</div>
                        <div class="location-name">{escape(loc_name)}</div>
                        <div class="location-desc">{escape(loc_desc[:100])}</div>
                    </div>
                </div>
"""

        html += """
            </div>
        </div>
    </div>

    <!-- Modal -->
    <div class="modal-overlay" id="modalOverlay" onclick="if(event.target===this)closeModal()">
        <div class="modal">
            <button class="modal-close" onclick="closeModal()">&times;</button>
            <div class="modal-header">
                <div class="modal-portrait" id="modalPortrait"></div>
                <div class="modal-title-area">
                    <div class="modal-role" id="modalRole"></div>
                    <h2 class="modal-name" id="modalName"></h2>
                    <div class="modal-age" id="modalAge"></div>
                    <div class="modal-tags" id="modalTags"></div>
                </div>
            </div>
            <div class="modal-body" id="modalBody"></div>
        </div>
    </div>

    <script>
        function openCharacterModal(el) {
            const name = el.dataset.name;
            const role = el.dataset.role;
            const age = el.dataset.age;
            const physical = el.dataset.physical;
            const personality = el.dataset.personality;
            const backstory = el.dataset.backstory;
            const portrait = el.dataset.portrait;
            const sheet = el.dataset.sheet;
            const tags = JSON.parse(el.dataset.tags || '[]');

            document.getElementById('modalRole').textContent = role;
            document.getElementById('modalName').textContent = name;
            document.getElementById('modalAge').textContent = age ? 'Age: ' + age : '';

            document.getElementById('modalPortrait').innerHTML = `<img src="${portrait}" alt="${name}" onerror="this.parentElement.style.display='none'">`;

            let tagsHtml = tags.map(t => `<span class="modal-tag">${t}</span>`).join('');
            document.getElementById('modalTags').innerHTML = tagsHtml;

            let bodyHtml = '';
            if (physical) {
                bodyHtml += `<div class="modal-section"><div class="modal-section-title">Physical Description</div><p>${physical}</p></div>`;
            }
            if (personality) {
                bodyHtml += `<div class="modal-section"><div class="modal-section-title">Personality</div><p>${personality}</p></div>`;
            }
            if (backstory) {
                bodyHtml += `<div class="modal-section"><div class="modal-section-title">Backstory</div><p>${backstory}</p></div>`;
            }
            bodyHtml += `<div class="modal-section"><div class="modal-section-title">Character Sheet</div><div class="modal-images"><img src="${sheet}" alt="Character Sheet" onerror="this.parentElement.innerHTML='<p style=\\'color:#666\\'>No character sheet available</p>'"></div></div>`;

            document.getElementById('modalBody').innerHTML = bodyHtml;
            document.getElementById('modalOverlay').classList.add('active');
            document.body.style.overflow = 'hidden';
        }

        function openLocationModal(el) {
            const name = el.dataset.name;
            const type = el.dataset.type;
            const description = el.dataset.description;
            const image = el.dataset.image;
            const tags = JSON.parse(el.dataset.tags || '[]');

            document.getElementById('modalRole').textContent = type;
            document.getElementById('modalName').textContent = name;
            document.getElementById('modalAge').textContent = '';

            document.getElementById('modalPortrait').innerHTML = `<img src="${image}" alt="${name}" onerror="this.parentElement.style.display='none'">`;

            let tagsHtml = tags.map(t => `<span class="modal-tag">${t}</span>`).join('');
            document.getElementById('modalTags').innerHTML = tagsHtml;

            let bodyHtml = '';
            if (description) {
                bodyHtml += `<div class="modal-section"><div class="modal-section-title">Description</div><p>${description}</p></div>`;
            }
            bodyHtml += `<div class="modal-section"><div class="modal-section-title">Reference Image</div><div class="modal-images"><img src="${image}" alt="${name}"></div></div>`;

            document.getElementById('modalBody').innerHTML = bodyHtml;
            document.getElementById('modalOverlay').classList.add('active');
            document.body.style.overflow = 'hidden';
        }

        function closeModal() {
            document.getElementById('modalOverlay').classList.remove('active');
            document.body.style.overflow = '';
        }

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeModal();
        });
    </script>
</body>
</html>
"""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def send_chapter_viewer(self, project_id: str, chapter_num: int, debug_mode: bool = False, query: dict = None):
        """Send the chapter viewer page with vertical scroll."""
        if query is None:
            query = {}
        data = self.load_project(project_id)
        if not data:
            self.send_error(404, "Project not found")
            return

        story = data.get("story", {})
        characters = data.get("characters", [])
        chapters = data.get("chapters", [])

        # Find chapter
        chapter = None
        for ch in chapters:
            if ch.get("number") == chapter_num:
                chapter = ch
                break

        if not chapter:
            self.send_error(404, "Chapter not found")
            return

        # Build character lookup
        char_lookup = {c.get("id"): c for c in characters}

        # Collect all panels from scenes
        panels = []
        for scene in chapter.get("scenes", []):
            scene_num = scene.get("number", 0)
            for panel in scene.get("panels", []):
                panel_num = panel.get("number", 0)
                panel_path = (
                    PROJECTS_DIR
                    / project_id
                    / "assets"
                    / "panels"
                    / f"chapter-{chapter_num}"
                    / f"scene-{scene_num}"
                    / f"panel-{panel_num}.png"
                )
                panels.append(
                    {
                        "scene_num": scene_num,
                        "panel_num": panel_num,
                        "panel": panel,
                        "scene": scene,
                        "exists": panel_path.exists(),
                        "url": f"/projects/{project_id}/assets/panels/chapter-{chapter_num}/scene-{scene_num}/panel-{panel_num}.png",
                    }
                )

        debug_toggle_url = f"/view/{project_id}/chapter/{chapter_num}{'?debug=1' if not debug_mode else ''}"
        debug_toggle_text = "Debug: OFF" if not debug_mode else "Debug: ON"

        # Check for text overlay toggle
        show_text = query.get("text", ["1"])[0] != "0"
        text_toggle_url = f"/view/{project_id}/chapter/{chapter_num}?text={'0' if show_text else '1'}{'&debug=1' if debug_mode else ''}"
        text_toggle_text = "Text: ON" if show_text else "Text: OFF"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{escape(story.get('title', 'Project'))} - Ch.{chapter_num}: {escape(chapter.get('title', ''))}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Comic+Neue:wght@400;700&family=Bangers&family=JetBrains+Mono:wght@400;500&family=Luckiest+Guy&display=swap" rel="stylesheet">
    <style>
        :root {{
            --text-scale: 1.3;
            --bubble-font-size: calc(16px * var(--text-scale));
            --speaker-font-size: calc(11px * var(--text-scale));
            --thought-font-size: calc(15px * var(--text-scale));
            --narrator-font-size: calc(15px * var(--text-scale));
            --sfx-font-size: calc(32px * var(--text-scale));
            --debug-font-size: calc(14px * var(--text-scale));
            --debug-title-size: calc(12px * var(--text-scale));
            --debug-action-size: calc(15px * var(--text-scale));
            --debug-detail-size: calc(12px * var(--text-scale));
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: #0a0a0f;
            min-height: 100vh;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }}
        .header {{
            position: fixed;
            top: 0; left: 0; right: 0;
            background: rgba(0,0,0,0.95);
            color: #fff;
            padding: 10px 15px;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #222;
        }}
        .header a {{ color: #e94560; text-decoration: none; }}
        .header h1 {{ font-size: 16px; }}
        .debug-toggle {{
            background: {'#e94560' if debug_mode else '#333'};
            color: #fff;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
            transition: background 0.2s;
        }}
        .debug-toggle:hover {{ background: {'#ff6b8a' if debug_mode else '#555'}; }}

        .chapter-container {{
            max-width: {'1400px' if debug_mode else '800px'};
            margin: 0 auto;
            padding-top: 50px;
        }}

        .panel-row {{
            display: {'flex' if debug_mode else 'block'};
            gap: 0;
            margin-bottom: {'2px' if debug_mode else '0'};
            background: {'#12121a' if debug_mode else 'transparent'};
        }}

        .debug-left {{
            display: {'block' if debug_mode else 'none'};
            width: 280px;
            flex-shrink: 0;
            background: #0d1117;
            border-right: 1px solid #333;
            padding: 15px;
            font-size: var(--debug-font-size);
            color: #888;
            font-family: 'JetBrains Mono', monospace;
        }}
        .debug-left .section-title {{
            color: #58a6ff;
            font-weight: 600;
            margin-bottom: 8px;
            text-transform: uppercase;
            font-size: var(--debug-title-size);
        }}
        .debug-left .info-block {{
            margin-bottom: 12px;
            padding-bottom: 10px;
            border-bottom: 1px solid #222;
        }}
        .debug-left .info-row {{
            display: flex;
            flex-direction: column;
            margin-bottom: 8px;
        }}
        .debug-left .info-label {{
            color: #666;
            font-size: 10px;
            text-transform: uppercase;
            margin-bottom: 2px;
        }}
        .debug-left .info-value {{
            color: #9cdcfe;
            word-break: break-word;
            padding-left: 8px;
            border-left: 2px solid #333;
        }}

        .panel {{
            position: relative;
            flex: 1;
            min-width: 0;
        }}
        .panel img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        .panel .placeholder {{
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            min-height: 300px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #666;
            font-size: 14px;
        }}

        .debug-right {{
            display: {'block' if debug_mode else 'none'};
            width: 350px;
            flex-shrink: 0;
            background: #0d1117;
            border-left: 1px solid #333;
            padding: 15px;
            font-size: var(--debug-font-size);
            color: #888;
            font-family: 'JetBrains Mono', monospace;
            overflow-y: auto;
        }}
        .debug-right .section-title {{
            color: #f97583;
            font-weight: 600;
            margin-bottom: 8px;
            text-transform: uppercase;
            font-size: var(--debug-title-size);
        }}
        .debug-right .action-text {{
            color: #c9d1d9;
            font-size: var(--debug-action-size);
            line-height: 1.6;
            margin-bottom: 12px;
            padding: 12px;
            background: #161b22;
            border-radius: 6px;
            border-left: 4px solid #e94560;
        }}
        .debug-right .chars-list {{
            margin-bottom: 12px;
        }}
        .debug-right .char-item {{
            padding: 10px 12px;
            background: #161b22;
            border-radius: 6px;
            margin-bottom: 6px;
        }}
        .debug-right .char-name {{
            color: #79c0ff;
            font-weight: 500;
            font-size: var(--debug-font-size);
        }}
        .debug-right .char-detail {{
            color: #8b949e;
            font-size: var(--debug-detail-size);
            margin-top: 4px;
        }}

        .end-card {{
            text-align: center;
            padding: 50px 20px;
            color: #fff;
        }}
        .end-card h2 {{ margin-bottom: 20px; }}
        .end-card a {{
            display: inline-block;
            background: #e94560;
            color: #fff;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            margin: 5px;
        }}

        /* Dialogue and text overlay styles */
        .panel-content {{
            position: relative;
        }}
        .text-overlay {{
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            pointer-events: none;
            padding: 15px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .text-top {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            align-items: flex-start;
        }}
        .text-bottom {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            align-items: flex-end;
        }}

        /* Speech bubble */
        .speech-bubble {{
            background: #fff;
            color: #111;
            padding: 12px 18px;
            border-radius: 20px;
            font-family: 'Comic Neue', cursive;
            font-size: var(--bubble-font-size);
            font-weight: 700;
            max-width: 75%;
            position: relative;
            box-shadow: 2px 3px 0 rgba(0,0,0,0.3);
            border: 2px solid #111;
            line-height: 1.4;
            text-transform: uppercase;
        }}
        .speech-bubble::after {{
            content: '';
            position: absolute;
            bottom: -10px;
            left: 20px;
            border-width: 10px 8px 0 8px;
            border-style: solid;
            border-color: #fff transparent transparent transparent;
        }}
        .speech-bubble::before {{
            content: '';
            position: absolute;
            bottom: -14px;
            left: 18px;
            border-width: 12px 10px 0 10px;
            border-style: solid;
            border-color: #111 transparent transparent transparent;
        }}
        .speech-bubble.right {{
            align-self: flex-end;
        }}
        .speech-bubble.right::after {{
            left: auto;
            right: 20px;
        }}
        .speech-bubble.right::before {{
            left: auto;
            right: 18px;
        }}
        .speech-bubble .speaker {{
            font-size: var(--speaker-font-size);
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
            display: block;
        }}

        /* Thought bubble */
        .thought-bubble {{
            background: rgba(255,255,255,0.95);
            color: #333;
            padding: 14px 20px;
            border-radius: 25px;
            font-family: 'Comic Neue', cursive;
            font-size: var(--thought-font-size);
            font-style: italic;
            max-width: 70%;
            position: relative;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            border: 2px dashed #888;
            line-height: 1.4;
            text-transform: uppercase;
        }}
        .thought-bubble::after {{
            content: '...';
            position: absolute;
            bottom: -18px;
            left: 25px;
            font-size: 20px;
            color: #888;
            letter-spacing: 3px;
        }}
        .thought-bubble .speaker {{
            font-size: var(--speaker-font-size);
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
            display: block;
            font-style: normal;
        }}

        /* Narrator box */
        .narrator-box {{
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            color: #fff;
            padding: 14px 22px;
            font-family: 'Comic Neue', cursive;
            font-size: var(--narrator-font-size);
            font-weight: 700;
            max-width: 85%;
            border-left: 4px solid #e94560;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            line-height: 1.5;
            text-transform: uppercase;
        }}
        .narrator-box.top {{
            align-self: flex-start;
        }}

        /* SFX text */
        .sfx-container {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            justify-content: center;
            pointer-events: none;
        }}
        .sfx-text {{
            font-family: 'Bangers', 'Luckiest Guy', cursive;
            font-size: var(--sfx-font-size);
            color: #fff;
            text-shadow:
                3px 3px 0 #e94560,
                -1px -1px 0 #000,
                1px -1px 0 #000,
                -1px 1px 0 #000,
                1px 1px 0 #000,
                0 0 20px rgba(233,69,96,0.5);
            letter-spacing: 2px;
            text-transform: uppercase;
            transform: rotate(-5deg);
        }}
        .sfx-text:nth-child(2) {{
            transform: rotate(3deg);
            color: #ffeb3b;
            text-shadow:
                3px 3px 0 #ff5722,
                -1px -1px 0 #000,
                1px -1px 0 #000,
                -1px 1px 0 #000,
                1px 1px 0 #000;
        }}
        .sfx-text:nth-child(3) {{
            transform: rotate(-8deg);
            font-size: 24px;
        }}

        /* Panel number badge */
        .panel-badge {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0,0,0,0.7);
            color: #888;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
            pointer-events: none;
        }}

        @media (max-width: 600px) {{
            .speech-bubble, .thought-bubble {{ font-size: 12px; padding: 8px 12px; }}
            .narrator-box {{ font-size: 11px; padding: 10px 14px; }}
            .sfx-text {{ font-size: 22px; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <a href="/project/{project_id}">&larr; Back</a>
        <h1>Ch.{chapter_num}: {escape(chapter.get('title', ''))}</h1>
        <div style="display: flex; align-items: center; gap: 10px;">
            <span>{len(panels)} panels</span>
            <div class="size-control" style="display: flex; align-items: center; gap: 6px; background: #222; padding: 4px 10px; border-radius: 4px;">
                <span style="font-size: 11px; color: #888;">A</span>
                <input type="range" id="textSizeSlider" min="0.8" max="2.0" step="0.1" value="1.3" style="width: 80px; cursor: pointer;">
                <span style="font-size: 15px; color: #888; font-weight: bold;">A</span>
            </div>
            <a href="{text_toggle_url}" class="text-toggle" style="background: {'#4caf50' if show_text else '#333'}; color: #fff; padding: 6px 12px; border-radius: 4px; font-size: 12px; font-weight: 500; text-decoration: none;">{text_toggle_text}</a>
            <a href="{debug_toggle_url}" class="debug-toggle">{debug_toggle_text}</a>
        </div>
    </div>

    <div class="chapter-container">
"""

        for p in panels:
            panel = p["panel"]
            scene = p["scene"]
            composition = panel.get("composition", {})

            html += f"""
        <div class="panel-row">
"""
            # Left debug panel
            if debug_mode:
                html += f"""
            <div class="debug-left">
                <div class="info-block">
                    <div class="section-title">Scene</div>
                    <div class="info-row"><span class="info-label">number:</span><span class="info-value">{escape(str(scene.get('number', 'N/A')))}</span></div>
                    <div class="info-row"><span class="info-label">location:</span><span class="info-value">{escape(str(scene.get('location_id', 'N/A')))}</span></div>
                    <div class="info-row"><span class="info-label">time:</span><span class="info-value">{escape(str(scene.get('time_of_day', 'N/A')))}</span></div>
                </div>
                <div class="info-block">
                    <div class="section-title">Panel</div>
                    <div class="info-row"><span class="info-label">number:</span><span class="info-value">{escape(str(panel.get('number', 'N/A')))}</span></div>
                    <div class="info-row"><span class="info-label">shot:</span><span class="info-value">{escape(str(composition.get('shot_type', 'N/A')))}</span></div>
                    <div class="info-row"><span class="info-label">angle:</span><span class="info-value">{escape(str(composition.get('angle', 'N/A')))}</span></div>
                </div>
            </div>
"""

            # Center panel image with text overlays
            dialogue = panel.get("dialogue", [])
            sfx = panel.get("sfx", [])

            html += f"""
            <div class="panel">
                <div class="panel-content">
"""
            if p["exists"]:
                html += f"""                    <img src="{p['url']}" alt="Scene {p['scene_num']} Panel {p['panel_num']}" loading="lazy">
"""
            else:
                html += f"""                    <div class="placeholder">Panel not generated yet</div>
"""

            # Add text overlay if there's dialogue or SFX and text is enabled
            if show_text and (dialogue or sfx):
                html += """                    <div class="text-overlay">
                        <div class="text-top">
"""
                # Process dialogue - first half goes at top
                top_dialogues = dialogue[:len(dialogue)//2 + 1] if len(dialogue) > 1 else dialogue
                for idx, d in enumerate(top_dialogues):
                    char_id = d.get("character_id")
                    text = escape(d.get("text", ""))
                    dtype = d.get("type", "speech")

                    if char_id:
                        char = char_lookup.get(char_id, {})
                        speaker = char.get("name", "")
                    else:
                        speaker = ""

                    if dtype == "thought":
                        html += f"""                            <div class="thought-bubble">"""
                        if speaker:
                            html += f"""<span class="speaker">{escape(speaker)}</span>"""
                        html += f"""{text}</div>
"""
                    elif not char_id and dtype == "speech":
                        # Narrator or unknown speaker
                        html += f"""                            <div class="narrator-box top">{text}</div>
"""
                    else:
                        right_class = " right" if idx % 2 == 1 else ""
                        html += f"""                            <div class="speech-bubble{right_class}">"""
                        if speaker:
                            html += f"""<span class="speaker">{escape(speaker)}</span>"""
                        html += f"""{text}</div>
"""

                html += """                        </div>
"""

                # SFX in the middle
                if sfx:
                    html += """                        <div class="sfx-container">
"""
                    for s in sfx[:3]:  # Limit to 3 SFX
                        html += f"""                            <span class="sfx-text">{escape(s)}</span>
"""
                    html += """                        </div>
"""

                # Bottom dialogues
                html += """                        <div class="text-bottom">
"""
                bottom_dialogues = dialogue[len(dialogue)//2 + 1:] if len(dialogue) > 1 else []
                for idx, d in enumerate(bottom_dialogues):
                    char_id = d.get("character_id")
                    text = escape(d.get("text", ""))
                    dtype = d.get("type", "speech")

                    if char_id:
                        char = char_lookup.get(char_id, {})
                        speaker = char.get("name", "")
                    else:
                        speaker = ""

                    if dtype == "thought":
                        html += f"""                            <div class="thought-bubble">"""
                        if speaker:
                            html += f"""<span class="speaker">{escape(speaker)}</span>"""
                        html += f"""{text}</div>
"""
                    elif not char_id and dtype == "speech":
                        html += f"""                            <div class="narrator-box">{text}</div>
"""
                    else:
                        right_class = " right" if idx % 2 == 0 else ""
                        html += f"""                            <div class="speech-bubble{right_class}">"""
                        if speaker:
                            html += f"""<span class="speaker">{escape(speaker)}</span>"""
                        html += f"""{text}</div>
"""

                html += """                        </div>
                    </div>
"""

            html += """                </div>
            </div>
"""

            # Right debug panel
            if debug_mode:
                action = panel.get("action", "")
                panel_chars = panel.get("characters", [])
                scene_char_ids = scene.get("character_ids", [])

                html += f"""
            <div class="debug-right">
                <div class="section-title">Action</div>
                <div class="action-text">{escape(action)}</div>
                <div class="section-title">Panel Characters</div>
                <div class="chars-list">
"""
                if panel_chars:
                    for pc in panel_chars:
                        char_id = pc.get("character_id", "")
                        char = char_lookup.get(char_id, {})
                        html += f"""
                    <div class="char-item">
                        <div class="char-name">{escape(char.get('name', char_id))}</div>
                        <div class="char-detail">expr: {escape(str(pc.get('expression', 'N/A')))} | pos: {escape(str(pc.get('position', 'N/A')))}</div>
                    </div>
"""
                else:
                    html += """<div class="char-item" style="color: #666;">No specific characters</div>
"""
                html += """
                </div>
"""
                # Show all scene characters
                if scene_char_ids:
                    html += """                <div class="section-title" style="margin-top: 10px;">Scene Characters</div>
                <div class="chars-list">
"""
                    for char_id in scene_char_ids:
                        char = char_lookup.get(char_id, {})
                        html += f"""
                    <div class="char-item" style="padding: 6px 10px;">
                        <div class="char-name">{escape(char.get('name', char_id))}</div>
                    </div>
"""
                    html += """
                </div>
"""
                html += """
            </div>
"""

            html += """
        </div>
"""

        # Next/prev chapter links
        prev_ch = chapter_num - 1 if chapter_num > 1 else None
        next_ch = chapter_num + 1 if chapter_num < len(chapters) else None

        html += f"""
        <div class="end-card">
            <h2>End of Chapter {chapter_num}</h2>
"""
        if prev_ch:
            html += f"""            <a href="/view/{project_id}/chapter/{prev_ch}">&larr; Previous Chapter</a>
"""
        html += f"""            <a href="/project/{project_id}">Back to Overview</a>
"""
        if next_ch:
            html += f"""            <a href="/view/{project_id}/chapter/{next_ch}">Next Chapter &rarr;</a>
"""
        html += """
        </div>
    </div>
    <script>
        const slider = document.getElementById('textSizeSlider');
        const savedSize = localStorage.getItem('textScale');
        if (savedSize) {
            slider.value = savedSize;
            document.documentElement.style.setProperty('--text-scale', savedSize);
        }
        slider.addEventListener('input', function() {
            document.documentElement.style.setProperty('--text-scale', this.value);
            localStorage.setItem('textScale', this.value);
        });
    </script>
</body>
</html>
"""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def send_projects_list(self):
        """Send JSON list of projects."""
        projects = []
        if PROJECTS_DIR.exists():
            for project_dir in PROJECTS_DIR.iterdir():
                if project_dir.is_dir():
                    project_json = project_dir / "project.json"
                    if project_json.exists():
                        data = json.loads(project_json.read_text())
                        story = data.get("story", {})
                        projects.append(
                            {
                                "id": project_dir.name,
                                "title": story.get("title", "Untitled"),
                                "chapters": len(data.get("chapters", [])),
                            }
                        )

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(projects).encode())

    def send_project_data(self, project_id: str):
        """Send JSON data for a specific project."""
        project_json = PROJECTS_DIR / project_id / "project.json"
        if project_json.exists():
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(project_json.read_bytes())
        else:
            self.send_error(404, "Project not found")


def run_server(port: int = DEFAULT_PORT, projects_dir: str | None = None):
    """Run the web server."""
    global PROJECTS_DIR

    if projects_dir:
        PROJECTS_DIR = Path(projects_dir)
    else:
        PROJECTS_DIR = Path.cwd() / "projects"

    os.chdir(Path(__file__).parent)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), WebtoonHandler) as httpd:
        print(f"DreamRight Viewer running at http://localhost:{port}")
        print(f"Projects directory: {PROJECTS_DIR}")
        print("Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


def main():
    parser = argparse.ArgumentParser(description="DreamRight Viewer - Local webtoon viewer")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT, help="Port to run on")
    parser.add_argument("--projects", type=str, default=None, help="Projects directory")
    args = parser.parse_args()

    run_server(port=args.port, projects_dir=args.projects)


if __name__ == "__main__":
    main()
