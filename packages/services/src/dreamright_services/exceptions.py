"""Service layer exceptions."""

from typing import Optional


class ServiceError(Exception):
    """Base exception for service errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(ServiceError):
    """Resource not found."""

    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(
            f"{resource_type} '{resource_id}' not found",
            code="NOT_FOUND",
        )


class ValidationError(ServiceError):
    """Validation error."""

    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        super().__init__(message, code="VALIDATION_ERROR")


class DependencyError(ServiceError):
    """Dependency not met error."""

    def __init__(
        self,
        message: str,
        missing_dependencies: list[dict],
    ):
        self.missing_dependencies = missing_dependencies
        super().__init__(message, code="DEPENDENCY_ERROR")


class AssetExistsError(ServiceError):
    """Asset already exists."""

    def __init__(self, asset_type: str, asset_id: str, path: str):
        self.asset_type = asset_type
        self.asset_id = asset_id
        self.path = path
        super().__init__(
            f"{asset_type} asset for '{asset_id}' already exists at {path}",
            code="ASSET_EXISTS",
        )


class GenerationError(ServiceError):
    """Error during AI generation."""

    def __init__(self, message: str, details: Optional[dict] = None):
        self.details = details or {}
        super().__init__(message, code="GENERATION_ERROR")
