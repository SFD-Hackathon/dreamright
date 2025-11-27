#!/usr/bin/env python3
"""Simple Swagger UI server for inspecting the DreamRight OpenAPI spec."""

import argparse
from pathlib import Path

import uvicorn
import yaml
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse

# Load OpenAPI spec
OPENAPI_PATH = Path(__file__).parent / "openapi.yaml"


def load_openapi_spec() -> dict:
    """Load the OpenAPI specification from YAML file."""
    with open(OPENAPI_PATH) as f:
        return yaml.safe_load(f)


app = FastAPI(
    title="DreamRight API Docs",
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
    openapi_url=None,  # Disable default openapi.json
)


@app.get("/openapi.json")
async def get_openapi():
    """Serve the OpenAPI specification as JSON."""
    return JSONResponse(content=load_openapi_spec())


@app.get("/", include_in_schema=False)
async def swagger_ui():
    """Serve Swagger UI at root."""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="DreamRight API - Swagger UI",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )


def main():
    """Run the Swagger UI server."""
    parser = argparse.ArgumentParser(description="Serve Swagger UI for DreamRight API")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    print(f"\n  Swagger UI available at: http://{args.host}:{args.port}/\n")
    uvicorn.run(
        "swagger_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
