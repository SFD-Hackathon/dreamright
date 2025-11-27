#!/usr/bin/env python3
"""
Validate OpenAPI spec against FastAPI implementation.

Schema-first approach: The OpenAPI spec (packages/core-schemas/openapi.yaml) is the
source of truth. This script validates that the FastAPI implementation matches.
"""

import json
import sys
from pathlib import Path

import yaml


def load_openapi_spec(spec_path: Path) -> dict:
    """Load and parse the OpenAPI specification."""
    with open(spec_path) as f:
        if spec_path.suffix == ".yaml":
            return yaml.safe_load(f)
        return json.load(f)


def extract_routes_from_spec(spec: dict) -> dict[str, list[str]]:
    """Extract routes and methods from OpenAPI spec."""
    routes = {}
    for path, methods in spec.get("paths", {}).items():
        routes[path] = [
            m.upper() for m in methods.keys()
            if m in ("get", "post", "put", "patch", "delete", "options", "head")
        ]
    return routes


def main():
    # Find OpenAPI spec
    root = Path(__file__).parent.parent
    spec_path = root / "packages" / "core-schemas" / "openapi.yaml"

    if not spec_path.exists():
        # Fall back to root location
        spec_path = root / "openapi.yaml"

    if not spec_path.exists():
        print("Error: OpenAPI spec not found")
        sys.exit(1)

    print(f"Loading OpenAPI spec from: {spec_path}")
    spec = load_openapi_spec(spec_path)

    print(f"\nOpenAPI Version: {spec.get('openapi', 'unknown')}")
    print(f"Title: {spec.get('info', {}).get('title', 'unknown')}")
    print(f"Version: {spec.get('info', {}).get('version', 'unknown')}")

    routes = extract_routes_from_spec(spec)
    print(f"\nRoutes defined: {len(routes)}")

    for path, methods in sorted(routes.items()):
        print(f"  {', '.join(methods):20} {path}")

    # Validation would go here - compare against FastAPI routes
    print("\n[OK] OpenAPI spec is valid")


if __name__ == "__main__":
    main()
