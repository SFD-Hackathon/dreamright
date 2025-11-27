"""Project management service."""

from pathlib import Path
from typing import Optional

from dreamright_core_schemas import Project, ProjectFormat, ProjectStatus
from dreamright_storage import ProjectManager, JSONStorage
from .exceptions import NotFoundError, ValidationError


class ProjectService:
    """Service for project management operations."""

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize service.

        Args:
            base_path: Base path for projects. If None, uses current directory.
        """
        self.base_path = base_path or Path.cwd()
        self._manager: Optional[ProjectManager] = None

    @property
    def manager(self) -> ProjectManager:
        """Get the project manager, loading if necessary."""
        if self._manager is None:
            self._manager = self.load()
        return self._manager

    def exists(self, path: Optional[Path] = None) -> bool:
        """Check if a project exists at the given path."""
        target = path or self.base_path
        return ProjectManager.exists(target)

    def create(
        self,
        name: str,
        format: ProjectFormat = ProjectFormat.WEBTOON,
        path: Optional[Path] = None,
    ) -> Project:
        """Create a new project.

        Args:
            name: Project name
            format: Project format (webtoon or short_drama)
            path: Directory for project (defaults to base_path)

        Returns:
            Created project

        Raises:
            ValidationError: If directory exists and is not empty
        """
        target = path or self.base_path

        if target.exists() and any(f for f in target.iterdir() if not f.name.startswith('.')):
            raise ValidationError(
                f"Directory {target} already exists and is not empty",
                field="path",
            )

        self._manager = ProjectManager.create(target, name, format.value)
        return self._manager.project

    def load(self, path: Optional[Path] = None) -> ProjectManager:
        """Load an existing project.

        Args:
            path: Project directory (defaults to base_path)

        Returns:
            ProjectManager instance

        Raises:
            NotFoundError: If no project exists at path
        """
        target = path or self.base_path

        if not ProjectManager.exists(target):
            raise NotFoundError("Project", str(target))

        manager = ProjectManager.load(target)
        self._manager = manager
        return manager

    def get(self, path: Optional[Path] = None) -> Project:
        """Get project data.

        Args:
            path: Project directory (defaults to base_path)

        Returns:
            Project instance
        """
        if self._manager is None or (path and path != self.base_path):
            self.load(path)
        return self.manager.project

    def update(
        self,
        name: Optional[str] = None,
        format: Optional[ProjectFormat] = None,
        status: Optional[ProjectStatus] = None,
    ) -> Project:
        """Update project properties.

        Args:
            name: New project name
            format: New project format
            status: New project status

        Returns:
            Updated project
        """
        project = self.manager.project

        if name is not None:
            project.name = name
        if format is not None:
            project.format = format
        if status is not None:
            project.status = status

        self.manager.save()
        return project

    def save(self) -> None:
        """Save current project state."""
        self.manager.save()

    def get_status(self) -> dict:
        """Get detailed project status.

        Returns:
            Status dict with asset counts and generation progress
        """
        project = self.manager.project

        # Count assets
        char_with_assets = sum(1 for c in project.characters if c.assets.portrait)
        loc_with_assets = sum(1 for l in project.locations if l.assets.reference)

        # Count chapters and panels
        total_chapters = len(project.chapters)
        completed_chapters = sum(
            1 for ch in project.chapters
            if ch.status.value == "completed"
        )
        total_panels = sum(
            sum(len(s.panels) for s in ch.scenes)
            for ch in project.chapters
        )
        panels_with_images = sum(
            1
            for ch in project.chapters
            for s in ch.scenes
            for p in s.panels
            if p.image_path
        )

        return {
            "project_id": project.id,
            "project_name": project.name,
            "status": project.status.value,
            "story_expanded": project.story is not None,
            "characters": {
                "total": len(project.characters),
                "with_assets": char_with_assets,
            },
            "locations": {
                "total": len(project.locations),
                "with_assets": loc_with_assets,
            },
            "chapters": {
                "total": total_chapters,
                "completed": completed_chapters,
            },
            "panels": {
                "total": total_panels,
                "generated": panels_with_images,
            },
        }

    def delete(self, path: Optional[Path] = None) -> bool:
        """Delete a project.

        Args:
            path: Project directory

        Returns:
            True if deleted
        """
        import shutil

        target = path or self.base_path
        if target.exists():
            shutil.rmtree(target)
            self._manager = None
            return True
        return False
