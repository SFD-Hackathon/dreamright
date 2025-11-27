"""Storage backends for DreamRight projects."""

import json
import re
import shutil
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dreamright_core_schemas import Project


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


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def save_project(self, project: Project) -> None:
        """Save project data."""
        ...

    @abstractmethod
    def load_project(self) -> Project:
        """Load project data."""
        ...

    @abstractmethod
    def project_exists(self) -> bool:
        """Check if project exists."""
        ...

    @abstractmethod
    def save_asset(
        self,
        asset_type: str,
        filename: str,
        data: bytes,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Save an asset file and return its path."""
        ...

    @abstractmethod
    def get_asset_path(self, asset_type: str, filename: str) -> Path:
        """Get the full path for an asset."""
        ...

    @abstractmethod
    def save_asset_metadata(
        self,
        asset_type: str,
        base_filename: str,
        metadata: dict[str, Any],
    ) -> str:
        """Save metadata JSON for an asset."""
        ...


class JSONStorage(StorageBackend):
    """File-based JSON storage backend."""

    PROJECT_FILE = "project.json"
    ASSETS_DIR = "assets"

    def __init__(self, base_path: Path):
        """Initialize storage with base project path.

        Args:
            base_path: Root directory for the project
        """
        self.base_path = Path(base_path)
        self.project_file = self.base_path / self.PROJECT_FILE
        self.assets_path = self.base_path / self.ASSETS_DIR

    def initialize(self) -> None:
        """Create directory structure for a new project."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.assets_path.mkdir(exist_ok=True)

        # Create asset subdirectories
        for subdir in ["characters", "locations", "panels"]:
            (self.assets_path / subdir).mkdir(exist_ok=True)

    def project_exists(self) -> bool:
        """Check if project file exists."""
        return self.project_file.exists()

    def save_project(self, project: Project) -> None:
        """Save project to JSON file."""
        # Update timestamp
        project.updated_at = datetime.now()

        # Serialize to JSON
        data = project.model_dump(mode="json")

        # Write atomically
        temp_file = self.project_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        # Rename to final file
        temp_file.rename(self.project_file)

    def load_project(self) -> Project:
        """Load project from JSON file."""
        if not self.project_exists():
            raise FileNotFoundError(f"Project not found at {self.project_file}")

        with open(self.project_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return Project.model_validate(data)

    def _backup_file(self, file_path: Path) -> Optional[Path]:
        """Backup an existing file before overwriting.

        Args:
            file_path: Path to the file to backup

        Returns:
            Path to the backup file, or None if file didn't exist
        """
        if not file_path.exists():
            return None

        # Create backup directory
        backup_dir = file_path.parent / ".backup"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = backup_dir / backup_name

        # Copy file to backup
        shutil.copy2(file_path, backup_path)

        return backup_path

    def save_asset(
        self,
        asset_type: str,
        filename: str,
        data: bytes,
        metadata: Optional[dict[str, Any]] = None,
        backup: bool = True,
    ) -> str:
        """Save an asset file.

        Args:
            asset_type: Type of asset (characters, locations, panels, chapters)
            filename: Name of the file
            data: Binary data to save
            metadata: Optional metadata dict to save alongside the asset
            backup: Whether to backup existing file before overwriting

        Returns:
            Relative path to the saved asset
        """
        asset_dir = self.assets_path / asset_type
        asset_dir.mkdir(parents=True, exist_ok=True)

        asset_path = asset_dir / filename

        # Backup existing file if requested
        if backup and asset_path.exists():
            self._backup_file(asset_path)
            # Also backup metadata if it exists
            metadata_path = asset_dir / f"{Path(filename).stem}.json"
            if metadata_path.exists():
                self._backup_file(metadata_path)

        with open(asset_path, "wb") as f:
            f.write(data)

        # Save metadata if provided
        if metadata is not None:
            self.save_asset_metadata(asset_type, Path(filename).stem, metadata)

        # Return relative path from project root
        return str(asset_path.relative_to(self.base_path))

    def save_asset_metadata(
        self,
        asset_type: str,
        base_filename: str,
        metadata: dict[str, Any],
    ) -> str:
        """Save metadata JSON for an asset.

        Args:
            asset_type: Type of asset (characters, locations, panels, chapters)
            base_filename: Base filename without extension
            metadata: Metadata dict to save

        Returns:
            Relative path to the saved metadata file
        """
        asset_dir = self.assets_path / asset_type
        asset_dir.mkdir(parents=True, exist_ok=True)

        # Add timestamp to metadata
        metadata_with_timestamp = {
            **metadata,
            "generated_at": datetime.now().isoformat(),
        }

        metadata_path = asset_dir / f"{base_filename}.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata_with_timestamp, f, indent=2, ensure_ascii=False)

        return str(metadata_path.relative_to(self.base_path))

    def get_asset_path(self, asset_type: str, filename: str) -> Path:
        """Get full path for an asset."""
        return self.assets_path / asset_type / filename

    def get_absolute_asset_path(self, relative_path: str) -> Path:
        """Convert relative asset path to absolute."""
        return self.base_path / relative_path

    def delete_asset(self, relative_path: str) -> bool:
        """Delete an asset file.

        Args:
            relative_path: Relative path from project root

        Returns:
            True if deleted, False if not found
        """
        full_path = self.base_path / relative_path
        if full_path.exists():
            full_path.unlink()
            return True
        return False

    def list_assets(self, asset_type: str) -> list[Path]:
        """List all assets of a given type."""
        asset_dir = self.assets_path / asset_type
        if not asset_dir.exists():
            return []
        return list(asset_dir.iterdir())


class ProjectManager:
    """High-level project management interface."""

    def __init__(self, storage: StorageBackend):
        """Initialize with a storage backend."""
        self.storage = storage
        self._project: Optional[Project] = None

    @classmethod
    def create(cls, path: Path, name: str, format: str = "webtoon") -> "ProjectManager":
        """Create a new project.

        Args:
            path: Directory for the project
            name: Project name
            format: Project format (webtoon or short_drama)

        Returns:
            ProjectManager instance
        """
        from dreamright_core_schemas import ProjectFormat

        storage = JSONStorage(path)
        storage.initialize()

        project = Project(
            name=name,
            format=ProjectFormat(format),
        )

        manager = cls(storage)
        manager._project = project
        manager.save()

        return manager

    @classmethod
    def load(cls, path: Path) -> "ProjectManager":
        """Load an existing project.

        Args:
            path: Directory containing the project

        Returns:
            ProjectManager instance
        """
        storage = JSONStorage(path)
        manager = cls(storage)
        manager._project = storage.load_project()
        return manager

    @classmethod
    def exists(cls, path: Path) -> bool:
        """Check if a project exists at path."""
        storage = JSONStorage(path)
        return storage.project_exists()

    @property
    def project(self) -> Project:
        """Get the current project."""
        if self._project is None:
            raise RuntimeError("No project loaded")
        return self._project

    def save(self) -> None:
        """Save the current project."""
        if self._project is None:
            raise RuntimeError("No project to save")
        self.storage.save_project(self._project)

    def save_asset(
        self,
        asset_type: str,
        filename: str,
        data: bytes,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Save an asset and return its relative path."""
        return self.storage.save_asset(asset_type, filename, data, metadata)

    def get_asset_path(self, asset_type: str, filename: str) -> Path:
        """Get full path for an asset."""
        return self.storage.get_asset_path(asset_type, filename)
