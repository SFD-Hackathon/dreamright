"""Location management service."""

from typing import Callable, Optional

from dreamright_generators.location import LocationGenerator
from dreamright_core_schemas import Location, LocationType
from dreamright_storage import ProjectManager, slugify
from .exceptions import AssetExistsError, NotFoundError

# Callback type aliases for progress reporting
OnLocationStart = Callable[[Location], None]
OnLocationComplete = Callable[[Location, str], None]  # location, path
OnLocationSkip = Callable[[Location, str], None]  # location, reason


class LocationService:
    """Service for location management operations."""

    def __init__(self, manager: ProjectManager):
        """Initialize service with a project manager."""
        self.manager = manager

    def list_locations(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Location], int]:
        """List all locations with pagination.

        Returns:
            Tuple of (locations, total_count)
        """
        locations = self.manager.project.locations
        total = len(locations)
        return locations[offset:offset + limit], total

    def get_location(self, location_id: str) -> Location:
        """Get location by ID.

        Raises:
            NotFoundError: If location not found
        """
        loc = self.manager.project.get_location_by_id(location_id)
        if not loc:
            raise NotFoundError("Location", location_id)
        return loc

    def get_location_by_name(self, name: str) -> Location:
        """Get location by name.

        Raises:
            NotFoundError: If location not found
        """
        loc = self.manager.project.get_location_by_name(name)
        if not loc:
            raise NotFoundError("Location", name)
        return loc

    def create_location(
        self,
        name: str,
        type: LocationType = LocationType.INTERIOR,
        description: str = "",
        visual_tags: Optional[list[str]] = None,
    ) -> Location:
        """Create a new location.

        Returns:
            Created location
        """
        loc = Location(
            name=name,
            type=type,
            description=description,
            visual_tags=visual_tags or [],
        )
        self.manager.project.locations.append(loc)
        self.manager.save()
        return loc

    def update_location(
        self,
        location_id: str,
        name: Optional[str] = None,
        type: Optional[LocationType] = None,
        description: Optional[str] = None,
        visual_tags: Optional[list[str]] = None,
    ) -> Location:
        """Update a location.

        Returns:
            Updated location
        """
        loc = self.get_location(location_id)

        if name is not None:
            loc.name = name
        if type is not None:
            loc.type = type
        if description is not None:
            loc.description = description
        if visual_tags is not None:
            loc.visual_tags = visual_tags

        self.manager.save()
        return loc

    def delete_location(self, location_id: str) -> bool:
        """Delete a location.

        Returns:
            True if deleted
        """
        locs = self.manager.project.locations
        for i, loc in enumerate(locs):
            if loc.id == location_id:
                locs.pop(i)
                self.manager.save()
                return True
        return False

    def get_assets(self, location_id: str) -> dict:
        """Get location assets metadata.

        Returns:
            Assets metadata dict
        """
        loc = self.get_location(location_id)
        return {
            "location_id": loc.id,
            "reference": loc.assets.reference,
        }

    def check_asset_exists(self, location_id: str) -> Optional[str]:
        """Check if location reference asset exists.

        Returns:
            Path to existing asset, or None
        """
        loc = self.get_location(location_id)
        if not loc.assets.reference:
            return None

        ref_path = self.manager.storage.get_absolute_asset_path(loc.assets.reference)
        if ref_path.exists():
            return loc.assets.reference
        return None

    async def generate_asset(
        self,
        location_id: str,
        style: str = "webtoon",
        overwrite: bool = False,
        on_start: Optional[OnLocationStart] = None,
        on_complete: Optional[OnLocationComplete] = None,
    ) -> dict:
        """Generate location reference asset.

        Args:
            location_id: Location ID
            style: Art style
            overwrite: Whether to overwrite existing
            on_start: Callback when generation starts
            on_complete: Callback when generation completes

        Returns:
            Generation result with path

        Raises:
            AssetExistsError: If asset exists and overwrite is False
        """
        loc = self.get_location(location_id)
        loc_slug = slugify(loc.name)
        loc_folder = f"locations/{loc_slug}"

        # Check existing
        if not overwrite:
            existing = self.check_asset_exists(location_id)
            if existing:
                raise AssetExistsError("location", loc.name, existing)

        # Notify start
        if on_start:
            on_start(loc)

        # Generate
        generator = LocationGenerator()
        image_data, gen_info = await generator.generate_reference(
            loc,
            style=style,
            overwrite_cache=overwrite,
        )

        # Save
        metadata = {
            "type": "location",
            "location_id": loc.id,
            "location_name": loc.name,
            "location_type": loc.type.value,
            "style": style,
            "description": loc.description,
            "visual_tags": loc.visual_tags,
            "gemini": gen_info,
        }

        path = self.manager.save_asset(
            loc_folder,
            "reference.png",
            image_data,
            metadata=metadata,
        )
        loc.assets.reference = path
        self.manager.save()

        # Notify complete
        if on_complete:
            on_complete(loc, path)

        return {
            "location_id": loc.id,
            "path": path,
            "style": style,
        }

    async def generate_reference_sheet(
        self,
        location_id: str,
        style: str = "webtoon",
        overwrite: bool = False,
        on_start: Optional[OnLocationStart] = None,
        on_complete: Optional[OnLocationComplete] = None,
    ) -> dict:
        """Generate multi-angle reference sheet for a location.

        Creates a 2x2 grid showing the location from different angles:
        - Wide establishing shot (eye level)
        - Medium shot (high angle)
        - Close-up details
        - Low angle shot

        Args:
            location_id: Location ID
            style: Art style
            overwrite: Whether to overwrite existing
            on_start: Callback when generation starts
            on_complete: Callback when generation completes

        Returns:
            Generation result with path
        """
        loc = self.get_location(location_id)
        loc_slug = slugify(loc.name)
        loc_folder = f"locations/{loc_slug}"

        # Check existing
        if not overwrite and loc.assets.reference_sheet:
            sheet_path = self.manager.storage.get_absolute_asset_path(loc.assets.reference_sheet)
            if sheet_path.exists():
                raise AssetExistsError("location reference sheet", loc.name, loc.assets.reference_sheet)

        # Notify start
        if on_start:
            on_start(loc)

        # Generate
        generator = LocationGenerator()
        image_data, gen_info = await generator.generate_reference_sheet(
            loc,
            style=style,
            overwrite_cache=overwrite,
        )

        # Save
        metadata = {
            "type": "location_reference_sheet",
            "location_id": loc.id,
            "location_name": loc.name,
            "location_type": loc.type.value,
            "style": style,
            "views": ["wide_eye_level", "medium_high_angle", "closeup_details", "low_angle"],
            "description": loc.description,
            "visual_tags": loc.visual_tags,
            "gemini": gen_info,
        }

        path = self.manager.save_asset(
            loc_folder,
            "reference_sheet.png",
            image_data,
            metadata=metadata,
        )
        loc.assets.reference_sheet = path
        self.manager.save()

        # Notify complete
        if on_complete:
            on_complete(loc, path)

        return {
            "location_id": loc.id,
            "path": path,
            "style": style,
            "type": "reference_sheet",
        }

    async def generate_all_assets(
        self,
        style: str = "webtoon",
        overwrite: bool = False,
        on_start: Optional[OnLocationStart] = None,
        on_complete: Optional[OnLocationComplete] = None,
        on_skip: Optional[OnLocationSkip] = None,
    ) -> list[dict]:
        """Generate assets for all locations without references.

        Args:
            style: Art style
            overwrite: Whether to overwrite existing
            on_start: Callback when generation starts for each location
            on_complete: Callback when generation completes for each location
            on_skip: Callback when location is skipped

        Returns:
            List of generation results
        """
        results = []
        for loc in self.manager.project.locations:
            existing = self.check_asset_exists(loc.id)
            if existing and not overwrite:
                if on_skip:
                    on_skip(loc, "asset_exists")
                results.append({
                    "location_id": loc.id,
                    "skipped": True,
                    "reason": "asset_exists",
                    "path": existing,
                })
            else:
                result = await self.generate_asset(
                    loc.id,
                    style=style,
                    overwrite=overwrite,
                    on_start=on_start,
                    on_complete=on_complete,
                )
                results.append(result)
        return results
