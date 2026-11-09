from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re

from PIL import Image, UnidentifiedImageError

# Approved image formats and their MIME types
ALLOWED_IMAGE_TYPES: dict[str, tuple[str, str]] = {
    "image/jpeg": ("JPEG", ".jpg"),
    "image/jpg": ("JPEG", ".jpg"),
    "image/png": ("PNG", ".png"),
    "image/webp": ("WEBP", ".webp"),
}


@dataclass(frozen=True)
class ValidatedImage:
    content: bytes
    file_type: str
    extension: str
    width: int
    height: int
    sanitized_original_name: str


def sanitize_filename(filename: str | None) -> str:
    """Sanitize uploaded original filename to prevent path traversal and shell injection."""
    if not filename:
        return "unnamed_image.jpg"

    # Extract basename only to strip directory paths
    base_name = Path(filename).name
    # Strip null bytes and control chars
    base_name = re.sub(r"[\x00-\x1f\x7f]", "", base_name).strip()
    if not base_name or base_name in {".", ".."}:
        return "unnamed_image.jpg"

    # Truncate to maximum length of 255 characters
    return base_name[:255]


def validate_image_content(
    content: bytes,
    content_type: str | None,
    original_filename: str | None = None,
    *,
    max_size: int = 10 * 1024 * 1024,
    max_dimension: int = 10000,
) -> ValidatedImage:
    """
    Validates uploaded image bytes, MIME type, dimensions, and actual image integrity.
    Rejects unsupported types, oversized files, corrupt files, and MIME/content mismatches.
    """
    if not content:
        raise ValueError("Image file is empty")

    if len(content) > max_size:
        max_mb = max_size // (1024 * 1024)
        raise ValueError(f"Image exceeds the maximum allowed size of {max_mb}MB ({max_size} bytes)")

    normalized_mime = (content_type or "").lower().strip()
    if normalized_mime == "image/jpg":
        normalized_mime = "image/jpeg"

    if normalized_mime not in ALLOWED_IMAGE_TYPES:
        raise ValueError("Unsupported image format. Allowed formats are JPEG (.jpg, .jpeg), PNG (.png), and WEBP (.webp)")

    # Decode and verify actual binary image content using Pillow
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()

        # Reopen to read image metadata (verify() invalidates some properties)
        with Image.open(BytesIO(content)) as image:
            width = image.width
            height = image.height
            detected_format = (image.format or "").upper()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Uploaded file is not a valid or readable image") from exc

    expected_format, default_ext = ALLOWED_IMAGE_TYPES[normalized_mime]

    # Content-type vs true binary format mismatch check
    if detected_format != expected_format:
        raise ValueError(
            f"Image MIME type '{content_type}' does not match actual detected image format '{detected_format}'"
        )

    if width < 1 or height < 1:
        raise ValueError("Image dimensions must be at least 1x1 pixel")

    if width > max_dimension or height > max_dimension:
        raise ValueError(f"Image dimensions ({width}x{height}) exceed maximum allowed dimension of {max_dimension}px")

    safe_name = sanitize_filename(original_filename)

    return ValidatedImage(
        content=content,
        file_type=normalized_mime,
        extension=default_ext,
        width=width,
        height=height,
        sanitized_original_name=safe_name,
    )
