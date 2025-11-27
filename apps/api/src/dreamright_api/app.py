"""DreamRight API application."""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dreamright_services.exceptions import (
    AssetExistsError,
    DependencyError,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from .deps import settings
from .routes import (
    assets_router,
    chapters_router,
    characters_router,
    jobs_router,
    locations_router,
    panels_router,
    projects_router,
    story_router,
)


def create_app(
    projects_dir: Optional[Path] = None,
    require_auth: bool = False,
    api_keys: Optional[set[str]] = None,
) -> FastAPI:
    """Create the FastAPI application.

    Args:
        projects_dir: Directory for storing projects
        require_auth: Whether to require authentication
        api_keys: Set of valid API keys

    Returns:
        FastAPI application
    """
    # Configure settings
    if projects_dir:
        settings.projects_dir = projects_dir
    if require_auth:
        settings.require_auth = require_auth
    if api_keys:
        settings.api_keys = api_keys

    # Ensure projects directory exists
    settings.projects_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="DreamRight API",
        description="""
AI-powered webtoon and short-form drama production API.

## Workflow

The typical workflow for creating a webtoon project is:

1. Create a project (`POST /projects`)
2. Expand a story prompt (`POST /projects/{id}/story`)
3. Generate character assets (`POST /projects/{id}/characters/{id}/assets`)
4. Generate location assets (`POST /projects/{id}/locations/{id}/assets`)
5. Generate chapters sequentially (`POST /projects/{id}/chapters`)
6. Generate panels for each chapter (`POST /projects/{id}/chapters/{id}/panels`)

## Asset Dependencies

- Panel generation requires character portraits and location references to exist
- Chapter N generation requires Chapter N-1 to exist (for story continuity)
- Panel generation for Chapter N requires Chapter N-1 panels to exist (for visual continuity)

## Async Operations

Long-running generation operations return `202 Accepted` with a job resource.
Poll the job status endpoint (`GET /jobs/{id}`) for completion.
""",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "field": exc.field,
                }
            },
        )

    @app.exception_handler(DependencyError)
    async def dependency_handler(request: Request, exc: DependencyError):
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
                "missing_dependencies": exc.missing_dependencies,
            },
        )

    @app.exception_handler(AssetExistsError)
    async def asset_exists_handler(request: Request, exc: AssetExistsError):
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
                "asset_type": exc.asset_type,
                "asset_id": exc.asset_id,
                "existing_path": exc.path,
            },
        )

    @app.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    # Register routers
    app.include_router(projects_router)
    app.include_router(story_router)
    app.include_router(characters_router)
    app.include_router(locations_router)
    app.include_router(chapters_router)
    app.include_router(panels_router)
    app.include_router(jobs_router)
    app.include_router(assets_router)

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


# Default app instance for uvicorn
app = create_app()
