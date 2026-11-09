"""
Module 10 – Evidence File Validator
=====================================
Extended file validation for evidence uploads supporting images, video clips,
and documents — with MIME type verification, magic-byte signature checking,
and size limits.

Malware scanning is handled as an integration point (configured via
EVIDENCE_MALWARE_SCAN_ENABLED env var). The scan adapter interface is
defined here so future implementations can be plugged in without changing
the validation pipeline.
"""

from __future__ import annotations

import io
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Allowed MIME types and their file-signature magic bytes
# ---------------------------------------------------------------------------

# (mime_type) -> list of (offset, magic_bytes) tuples
_MAGIC_SIGNATURES: dict[str, list[tuple[int, bytes]]] = {
    # Images
    "image/jpeg":      [(0, b"\xff\xd8\xff")],
    "image/png":       [(0, b"\x89PNG\r\n\x1a\n")],
    "image/webp":      [(0, b"RIFF"), (8, b"WEBP")],
    # Video
    "video/mp4":       [(4, b"ftyp")],
    "video/quicktime": [(4, b"ftyp"), (4, b"moov")],
    "video/x-msvideo": [(0, b"RIFF"), (8, b"AVI ")],
    "video/x-matroska": [(0, b"\x1a\x45\xdf\xa3")],
    # Documents
    "application/pdf": [(0, b"%PDF")],
    "text/plain":      [],  # No reliable magic for plain text — content inspection only
}

ALLOWED_EVIDENCE_MIME_TYPES: set[str] = set(_MAGIC_SIGNATURES.keys())

# Maximum sizes per evidence type category
MAX_IMAGE_BYTES: int = int(os.environ.get("EVIDENCE_MAX_IMAGE_BYTES", str(20 * 1024 * 1024)))   # 20 MB
MAX_VIDEO_BYTES: int = int(os.environ.get("EVIDENCE_MAX_VIDEO_BYTES", str(2 * 1024 * 1024 * 1024)))  # 2 GB
MAX_DOC_BYTES:   int = int(os.environ.get("EVIDENCE_MAX_DOC_BYTES",   str(50 * 1024 * 1024)))   # 50 MB


def _get_max_size(mime_type: str) -> int:
    if mime_type.startswith("image/"):
        return MAX_IMAGE_BYTES
    if mime_type.startswith("video/"):
        return MAX_VIDEO_BYTES
    return MAX_DOC_BYTES


@dataclass(frozen=True)
class ValidatedEvidenceFile:
    content: bytes
    mime_type: str
    file_extension: str
    file_size: int
    sanitized_name: str


def sanitize_evidence_filename(filename: str | None) -> str:
    """Sanitize an uploaded filename — basename only, no traversal, max 255 chars."""
    if not filename:
        return "evidence_file.bin"
    base = Path(filename).name.strip()
    # Remove null bytes and control characters
    base = "".join(c for c in base if ord(c) >= 32)
    if not base or base in {".", ".."}:
        return "evidence_file.bin"
    return base[:255]


def _check_magic_bytes(content: bytes, mime_type: str) -> bool:
    """
    Verify that the file's leading bytes match known magic signatures for the
    declared MIME type. Returns True if acceptable, False if suspicious.
    """
    sigs = _MAGIC_SIGNATURES.get(mime_type)
    if sigs is None:
        return False  # unknown type
    if not sigs:
        return True   # e.g. text/plain — no reliable magic
    return all(
        len(content) > offset + len(magic) and content[offset : offset + len(magic)] == magic
        for offset, magic in sigs
    )


def validate_evidence_file(
    content: bytes,
    declared_mime: str,
    original_filename: str | None = None,
) -> ValidatedEvidenceFile:
    """
    Validate an uploaded evidence file.

    Checks performed (in order):
      1. Non-empty content
      2. Allowed MIME type
      3. File size limit (per MIME category)
      4. Magic-byte signature verification
      5. Sanitize filename

    Raises ValueError with a descriptive message on any failure.
    Does NOT modify the content bytes.
    """
    if not content:
        raise ValueError("Evidence file is empty")

    normalized_mime = (declared_mime or "").lower().strip()
    # Normalize common variants
    if normalized_mime == "image/jpg":
        normalized_mime = "image/jpeg"

    if normalized_mime not in ALLOWED_EVIDENCE_MIME_TYPES:
        raise ValueError(
            f"Unsupported evidence file type '{declared_mime}'. "
            f"Allowed: {sorted(ALLOWED_EVIDENCE_MIME_TYPES)}"
        )

    max_size = _get_max_size(normalized_mime)
    if len(content) > max_size:
        raise ValueError(
            f"Evidence file size ({len(content):,} bytes) exceeds "
            f"the maximum allowed for '{normalized_mime}' ({max_size:,} bytes)"
        )

    if not _check_magic_bytes(content, normalized_mime):
        raise ValueError(
            f"File content does not match declared MIME type '{normalized_mime}'. "
            "Possible MIME/content mismatch or unsupported file variant."
        )

    # Derive extension from MIME
    ext = mimetypes.guess_extension(normalized_mime) or ".bin"
    # mimetypes sometimes returns .jpe for image/jpeg
    _ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "application/pdf": ".pdf",
    }
    ext = _ext_map.get(normalized_mime, ext)

    safe_name = sanitize_evidence_filename(original_filename)

    return ValidatedEvidenceFile(
        content=content,
        mime_type=normalized_mime,
        file_extension=ext,
        file_size=len(content),
        sanitized_name=safe_name,
    )


# ---------------------------------------------------------------------------
# Malware scan integration point
# ---------------------------------------------------------------------------

class MalwareScanResult:
    def __init__(self, clean: bool, scanner: str, details: str | None = None) -> None:
        self.clean = clean
        self.scanner = scanner
        self.details = details


def malware_scan(content: bytes, filename: str) -> MalwareScanResult:
    """
    Integration point for malware scanning.

    In this prototype the scan is simulated (always clean).
    Replace with a real ClamAV / VirusTotal / vendor SDK call when deploying.
    Enable via: EVIDENCE_MALWARE_SCAN_ENABLED=true (env var).
    """
    enabled = os.environ.get("EVIDENCE_MALWARE_SCAN_ENABLED", "false").lower() == "true"
    if not enabled:
        return MalwareScanResult(clean=True, scanner="DISABLED", details="Malware scanning disabled in config")

    # TODO: wire up ClamAV or vendor SDK here
    # import clamd; cd = clamd.ClamdUnixSocket(); result = cd.instream(io.BytesIO(content))
    return MalwareScanResult(
        clean=True,
        scanner="STUB",
        details="Malware scanning stub — replace with real implementation",
    )
