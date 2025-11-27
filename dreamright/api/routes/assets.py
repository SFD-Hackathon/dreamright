"""Asset routes."""

import json
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from ..deps import get_project_manager, get_project_path, verify_token
from ..schemas import (
    AssetMetadata,
    ErrorResponse,
    PaginatedResponse,
    PaginationMeta,
)

router = APIRouter(prefix="/projects/{project_id}/assets", tags=["Assets"])


@router.get(
    "",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def list_assets(
    project_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
    type: Optional[str] = Query(None, description="Filter by asset type"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List all assets."""
    manager = get_project_manager(project_id)
    assets_path = manager.storage.assets_path

    if not assets_path.exists():
        return PaginatedResponse(
            data=[],
            pagination=PaginationMeta(total=0, limit=limit, offset=offset, has_more=False),
        )

    # Collect all asset files
    assets = []

    # Define asset type directories
    type_dirs = {
        "character": "characters",
        "location": "locations",
        "panel": "panels",
    }

    # Filter by type if specified
    if type:
        if type not in type_dirs:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid asset type. Must be one of: {list(type_dirs.keys())}",
            )
        dirs_to_scan = [(type, assets_path / type_dirs[type])]
    else:
        dirs_to_scan = [(t, assets_path / d) for t, d in type_dirs.items()]

    for asset_type, dir_path in dirs_to_scan:
        if not dir_path.exists():
            continue

        for file_path in dir_path.rglob("*.png"):
            rel_path = file_path.relative_to(assets_path)
            metadata_path = file_path.with_suffix(".json")

            asset_info = {
                "type": asset_type,
                "path": str(rel_path),
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "has_metadata": metadata_path.exists(),
            }

            if metadata_path.exists():
                try:
                    with open(metadata_path) as f:
                        metadata = json.load(f)
                    asset_info["generated_at"] = metadata.get("generated_at")
                    asset_info["style"] = metadata.get("style")
                except Exception:
                    pass

            assets.append(asset_info)

    # Sort by path
    assets.sort(key=lambda a: a["path"])

    total = len(assets)
    paginated = assets[offset:offset + limit]

    return PaginatedResponse(
        data=paginated,
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + limit < total,
        ),
    )


@router.get(
    "/{asset_type}/{asset_id:path}",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_asset_file(
    project_id: str,
    asset_type: str,
    asset_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Get asset file (image)."""
    manager = get_project_manager(project_id)
    assets_path = manager.storage.assets_path

    # Map asset type to directory
    type_dirs = {
        "characters": "characters",
        "locations": "locations",
        "panels": "panels",
    }

    if asset_type not in type_dirs:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid asset type. Must be one of: {list(type_dirs.keys())}",
        )

    # Construct file path
    file_path = assets_path / type_dirs[asset_type] / asset_id

    # Ensure the path doesn't escape the assets directory
    try:
        file_path.resolve().relative_to(assets_path.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid asset path")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Asset not found")

    # Determine media type
    suffix = file_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(file_path, media_type=media_type)


@router.get(
    "/{asset_type}/{asset_id:path}/metadata",
    response_model=AssetMetadata,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_asset_metadata(
    project_id: str,
    asset_type: str,
    asset_id: str,
    token: Annotated[Optional[str], Depends(verify_token)],
):
    """Get asset metadata."""
    manager = get_project_manager(project_id)
    assets_path = manager.storage.assets_path

    # Map asset type to directory
    type_dirs = {
        "characters": "characters",
        "locations": "locations",
        "panels": "panels",
    }

    if asset_type not in type_dirs:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid asset type. Must be one of: {list(type_dirs.keys())}",
        )

    # Construct metadata path
    asset_path = assets_path / type_dirs[asset_type] / asset_id
    metadata_path = asset_path.with_suffix(".json")

    # Ensure the path doesn't escape the assets directory
    try:
        metadata_path.resolve().relative_to(assets_path.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid asset path")

    if not metadata_path.exists():
        # Check if asset exists but no metadata
        if asset_path.exists():
            return AssetMetadata(type=asset_type.rstrip("s"))
        raise HTTPException(status_code=404, detail="Asset not found")

    try:
        with open(metadata_path) as f:
            data = json.load(f)

        return AssetMetadata(
            type=data.get("type", asset_type.rstrip("s")),
            generated_at=data.get("generated_at"),
            style=data.get("style"),
            prompt=data.get("gemini", {}).get("prompt"),
            model=data.get("gemini", {}).get("model"),
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid metadata file")
