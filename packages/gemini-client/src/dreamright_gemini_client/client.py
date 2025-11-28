"""Gemini API client wrapper for DreamRight."""

import functools
import hashlib
import json
import os
import pickle
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Optional, Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

T = TypeVar("T", bound=BaseModel)
F = TypeVar("F", bound=Callable[..., Any])


class LRUCache:
    """LRU cache for API responses with optional disk persistence."""

    def __init__(
        self,
        max_size: int = 100,
        cache_dir: Optional[Path] = None,
        cache_name: str = "cache",
    ):
        """Initialize LRU cache.

        Args:
            max_size: Maximum number of items to cache in memory
            cache_dir: Directory for persistent cache storage (None for memory-only)
            cache_name: Name for this cache (used in filename)
        """
        self.max_size = max_size
        self.cache_dir = cache_dir
        self.cache_name = cache_name
        self._cache: OrderedDict[str, Any] = OrderedDict()

        # Load from disk if cache_dir is specified
        if self.cache_dir:
            self._load_from_disk()

    @property
    def _cache_file(self) -> Optional[Path]:
        """Get the cache file path."""
        if self.cache_dir:
            return self.cache_dir / f"{self.cache_name}.pkl"
        return None

    def _load_from_disk(self) -> None:
        """Load cache from disk."""
        if not self._cache_file or not self._cache_file.exists():
            return

        try:
            with open(self._cache_file, "rb") as f:
                data = pickle.load(f)
                # Load up to max_size items, most recent first
                items = list(data.items())[-self.max_size :]
                self._cache = OrderedDict(items)
        except (pickle.PickleError, EOFError, OSError):
            # If cache is corrupted, start fresh
            self._cache = OrderedDict()

    def _save_to_disk(self) -> None:
        """Save cache to disk."""
        if not self._cache_file:
            return

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(self._cache_file, "wb") as f:
                pickle.dump(dict(self._cache), f)
        except (pickle.PickleError, OSError):
            # Silently fail on save errors
            pass

    def get(self, key: str) -> tuple[bool, Any]:
        """Get item from cache."""
        if key in self._cache:
            self._cache.move_to_end(key)
            return True, self._cache[key]
        return False, None

    def set(self, key: str, value: Any, persist: bool = True) -> None:
        """Set item in cache."""
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
        self._cache[key] = value

        if persist and self.cache_dir:
            self._save_to_disk()

    def clear(self) -> None:
        """Clear the cache (memory and disk)."""
        self._cache.clear()
        if self._cache_file and self._cache_file.exists():
            self._cache_file.unlink()

    def __len__(self) -> int:
        return len(self._cache)


def _make_cache_key(method_name: str, *args, **kwargs) -> str:
    """Create a hash key from method name and arguments."""
    key_parts = [method_name]

    for arg in args:
        if isinstance(arg, Path):
            if arg.exists():
                with open(arg, "rb") as f:
                    content_hash = hashlib.md5(f.read()).hexdigest()
                key_parts.append(f"path:{arg}:{content_hash}")
            else:
                key_parts.append(f"path:{arg}")
        elif isinstance(arg, bytes):
            key_parts.append(f"bytes:{hashlib.md5(arg).hexdigest()}")
        elif isinstance(arg, type) and issubclass(arg, BaseModel):
            key_parts.append(f"schema:{arg.__name__}:{json.dumps(arg.model_json_schema(), sort_keys=True)}")
        else:
            key_parts.append(repr(arg))

    for k, v in sorted(kwargs.items()):
        if k == "overwrite_cache":
            continue  # Skip the control parameter
        if isinstance(v, Path):
            if v.exists():
                with open(v, "rb") as f:
                    content_hash = hashlib.md5(f.read()).hexdigest()
                key_parts.append(f"{k}=path:{v}:{content_hash}")
            else:
                key_parts.append(f"{k}=path:{v}")
        elif isinstance(v, bytes):
            key_parts.append(f"{k}=bytes:{hashlib.md5(v).hexdigest()}")
        elif isinstance(v, list):
            list_parts = []
            for item in v:
                if isinstance(item, Path) and item.exists():
                    with open(item, "rb") as f:
                        content_hash = hashlib.md5(f.read()).hexdigest()
                    list_parts.append(f"path:{item}:{content_hash}")
                else:
                    list_parts.append(repr(item))
            key_parts.append(f"{k}=[{','.join(list_parts)}]")
        else:
            key_parts.append(f"{k}={repr(v)}")

    key_string = "|".join(key_parts)
    return hashlib.sha256(key_string.encode()).hexdigest()


def cached(cache_attr: str):
    """Decorator for caching async method results.

    Args:
        cache_attr: Name of the cache attribute on self (e.g., "_text_cache")

    The decorated method can accept an `overwrite_cache` parameter.
    If True, bypasses cache and makes a fresh API call.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            overwrite_cache = kwargs.pop("overwrite_cache", False)
            cache: LRUCache = getattr(self, cache_attr)

            # Create cache key from method name and arguments
            cache_key = _make_cache_key(func.__name__, *args, **kwargs)

            # Check cache unless overwrite requested
            if not overwrite_cache:
                found, cached_value = cache.get(cache_key)
                if found:
                    return cached_value

            # Call the actual method
            result = await func(self, *args, **kwargs)

            # Cache the result
            cache.set(cache_key, result)

            return result

        return wrapper  # type: ignore

    return decorator


class GeminiClient:
    """Wrapper for Google Gemini API."""

    DEFAULT_MODEL = "gemini-3-pro-preview"
    IMAGE_MODEL = "gemini-3-pro-image-preview"

    # Default cache directory (in user's home)
    DEFAULT_CACHE_DIR = Path.home() / ".cache" / "dreamright"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        image_model: Optional[str] = None,
        cache_size: int = 100,
        cache_dir: Optional[Path] = None,
        persist_cache: bool = True,
    ):
        """Initialize Gemini client.

        Args:
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
            model: Model to use for text generation
            image_model: Model to use for image generation
            cache_size: Maximum number of items to cache (default 100)
            cache_dir: Directory for persistent cache (default ~/.cache/dreamright)
            persist_cache: Whether to persist cache to disk (default True)
        """
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GOOGLE_API_KEY environment variable is required. "
                "Get one at https://aistudio.google.com/apikey"
            )

        self.model = model or self.DEFAULT_MODEL
        self.image_model = image_model or self.IMAGE_MODEL

        # Initialize client
        self.client = genai.Client(api_key=self.api_key)

        # Determine cache directory
        if persist_cache:
            self._cache_dir = cache_dir or self.DEFAULT_CACHE_DIR
        else:
            self._cache_dir = None

        # Initialize LRU caches for different generation types
        self._text_cache = LRUCache(
            max_size=cache_size,
            cache_dir=self._cache_dir,
            cache_name="text_cache",
        )
        self._structured_cache = LRUCache(
            max_size=cache_size,
            cache_dir=self._cache_dir,
            cache_name="structured_cache",
        )
        self._image_cache = LRUCache(
            max_size=cache_size,
            cache_dir=self._cache_dir,
            cache_name="image_cache",
        )

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._text_cache.clear()
        self._structured_cache.clear()
        self._image_cache.clear()

    def cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache sizes and location
        """
        return {
            "text_cache": len(self._text_cache),
            "structured_cache": len(self._structured_cache),
            "image_cache": len(self._image_cache),
            "cache_dir": str(self._cache_dir) if self._cache_dir else None,
            "persistent": self._cache_dir is not None,
        }

    @cached("_text_cache")
    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> str:
        """Generate text response.

        Args:
            prompt: User prompt
            system_instruction: System instruction for the model
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            overwrite_cache: If True, bypass cache (handled by decorator)

        Returns:
            Generated text
        """
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        # Manual retry logic with exponential backoff for network errors
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                break  # Success, exit retry loop
            except Exception as e:
                if attempt < max_attempts - 1:  # Don't wait on last attempt
                    import asyncio
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"  Network error (attempt {attempt + 1}/{max_attempts}), retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise  # Re-raise on final attempt

        return response.text

    def _extract_json_text(self, response) -> str:
        """Extract and clean JSON text from a Gemini response.

        Handles:
        - None responses
        - Missing or empty candidates
        - Code fences (```json ... ```)
        - Multiple candidates (takes first)

        Args:
            response: Gemini API response

        Returns:
            Cleaned JSON string

        Raises:
            RuntimeError: If no valid JSON text can be extracted
        """
        # Check for valid response
        if response is None:
            raise RuntimeError("Gemini API returned None response")

        # Check for candidates
        if not hasattr(response, "candidates") or not response.candidates:
            raise RuntimeError(
                "Gemini API response has no candidates. "
                "This may indicate content was blocked or an API error occurred."
            )

        # Get text from first candidate
        candidate = response.candidates[0]

        # Check finish reason for potential issues
        if hasattr(candidate, "finish_reason"):
            finish_reason = str(candidate.finish_reason)
            if "SAFETY" in finish_reason:
                raise RuntimeError(
                    f"Gemini blocked response due to safety filters: {finish_reason}"
                )

        # Get text content
        text = response.text
        if text is None:
            # Try to get text from candidate content parts
            if hasattr(candidate, "content") and candidate.content:
                parts = candidate.content.parts
                if parts:
                    text_parts = [p.text for p in parts if hasattr(p, "text") and p.text]
                    if text_parts:
                        text = text_parts[0]

        if text is None or not text.strip():
            raise RuntimeError(
                "Gemini API returned empty text. "
                "Check if the prompt was valid and not blocked."
            )

        # Strip code fences if present (```json ... ``` or ``` ... ```)
        text = text.strip()
        if text.startswith("```"):
            # Remove opening fence (with optional language identifier)
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            else:
                text = text[3:]  # Just "```" without newline

        if text.endswith("```"):
            text = text[:-3]

        return text.strip()

    @cached("_structured_cache")
    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
    ) -> T:
        """Generate structured output matching a Pydantic schema.

        Args:
            prompt: User prompt
            response_schema: Pydantic model class for response
            system_instruction: System instruction for the model
            temperature: Sampling temperature
            overwrite_cache: If True, bypass cache (handled by decorator)

        Returns:
            Parsed response matching the schema

        Raises:
            RuntimeError: If response cannot be parsed as valid JSON
            pydantic.ValidationError: If JSON doesn't match schema
        """
        config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=response_schema,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        # Manual retry logic with exponential backoff for network errors
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                break  # Success, exit retry loop
            except Exception as e:
                if attempt < max_attempts - 1:  # Don't wait on last attempt
                    import asyncio
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"  Network error (attempt {attempt + 1}/{max_attempts}), retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise  # Re-raise on final attempt

        # Extract and clean JSON text
        json_text = self._extract_json_text(response)

        try:
            return response_schema.model_validate_json(json_text)
        except Exception as e:
            # Provide more context on parse failures
            preview = json_text[:200] + "..." if len(json_text) > 200 else json_text
            raise RuntimeError(
                f"Failed to parse Gemini response as {response_schema.__name__}: {e}\n"
                f"Response preview: {preview}"
            ) from e

    def _load_reference_image(self, path: Path) -> Optional[types.Part]:
        """Load a reference image as a Gemini Part."""
        if not path.exists():
            return None

        with open(path, "rb") as f:
            image_data = f.read()

        suffix = path.suffix.lower()
        mime_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix, "image/png")

        return types.Part.from_bytes(data=image_data, mime_type=mime_type)

    @cached("_image_cache")
    async def generate_image(
        self,
        prompt: str,
        reference_images: Optional[list[tuple[Path, str]]] = None,
        aspect_ratio: str = "1:1",
        resolution: str = "1K",
        style: Optional[str] = None,
    ) -> tuple[bytes, dict]:
        """Generate an image.

        Args:
            prompt: Image generation prompt
            reference_images: Optional list of (path, role) tuples for consistency.
                Role examples: "previous panel", "character reference", "location reference"
            aspect_ratio: Aspect ratio (1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9)
            resolution: Image resolution (1K, 2K, 4K)
            style: Optional style modifier
            overwrite_cache: If True, bypass cache (handled by decorator)

        Returns:
            Tuple of (image_data, response_metadata)
        """
        # Build the full prompt
        full_prompt = prompt
        if style:
            full_prompt = f"{style} style. {full_prompt}"

        contents: list[Any] = []

        # Add reference images if provided, each with its role label
        if reference_images:
            loaded_count = 0
            for ref_path, role in reference_images:
                part = self._load_reference_image(ref_path)
                if part:
                    contents.append(f"[{role}]:")
                    contents.append(part)
                    loaded_count += 1

            if loaded_count > 0:
                contents.append(
                    f"Using the labeled reference images above to maintain visual consistency: {full_prompt}"
                )
            else:
                contents.append(full_prompt)
        else:
            contents.append(full_prompt)

        config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=resolution,
            ),
        )

        # Manual retry logic with exponential backoff for network errors
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.image_model,
                    contents=contents,
                    config=config,
                )
                break  # Success, exit retry loop
            except Exception as e:
                if attempt < max_attempts - 1:  # Don't wait on last attempt
                    import asyncio
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"  Network error (attempt {attempt + 1}/{max_attempts}), retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise  # Re-raise on final attempt

        # Extract response metadata
        response_metadata: dict[str, Any] = {}
        candidate = response.candidates[0]

        if hasattr(candidate, "finish_reason") and candidate.finish_reason:
            response_metadata["finish_reason"] = str(candidate.finish_reason)

        if hasattr(candidate, "safety_ratings") and candidate.safety_ratings:
            response_metadata["safety_ratings"] = [
                {"category": str(r.category), "probability": str(r.probability)}
                for r in candidate.safety_ratings
            ]

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata
            response_metadata["usage"] = {
                "prompt_tokens": getattr(usage, "prompt_token_count", None),
                "candidates_tokens": getattr(usage, "candidates_token_count", None),
                "total_tokens": getattr(usage, "total_token_count", None),
            }

        # Extract image and text from response
        text_parts = []
        image_data = None

        for part in candidate.content.parts:
            if part.inline_data is not None:
                image_data = part.inline_data.data
            elif hasattr(part, "text") and part.text:
                text_parts.append(part.text)

        if text_parts:
            response_metadata["generated_text"] = "\n".join(text_parts)

        if image_data is None:
            raise RuntimeError("No image generated in response")

        return image_data, response_metadata


# Singleton instance for convenience
_client: Optional[GeminiClient] = None


def get_client() -> GeminiClient:
    """Get or create the global Gemini client."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client


def set_client(client: GeminiClient) -> None:
    """Set the global Gemini client."""
    global _client
    _client = client
