"""
Module 10 – Evidence Storage Abstraction
=========================================
Pluggable storage backend for evidence files.

Supports LOCAL filesystem today and is designed to swap to
S3-compatible, Azure Blob, or GCS without changing the evidence service.

Security:
  - Files are stored under a configurable root outside the web-server document root.
  - No public URLs are generated — content is served only via authenticated endpoints.
  - SHA-256 hashes are computed on write and can be re-verified on read.
  - Encryption keys must come from environment variables, never from source code.
"""

from __future__ import annotations

import hashlib
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

from app.core.config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_path_segment(segment: str) -> str:
    """Strip dangerous characters from path components."""
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", (segment or "").strip())
    if not clean or clean in {".", ".."}:
        raise ValueError(f"Invalid path segment: {segment!r}")
    return clean


def compute_sha256(content: bytes) -> str:
    """Return hex-encoded SHA-256 digest of *content*."""
    return hashlib.sha256(content).hexdigest()


def verify_file_hash(file_path: str | Path, expected_hash: str, algorithm: str = "SHA-256") -> bool:
    """
    Read file from disk and compare its hash against *expected_hash*.

    Returns True on match, False on mismatch.
    Does not raise — callers should handle the return value.
    """
    path = Path(file_path)
    if not path.is_file():
        return False
    content = path.read_bytes()
    if algorithm.upper() in {"SHA-256", "SHA256"}:
        computed = compute_sha256(content)
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    return computed.lower() == expected_hash.lower()


# ---------------------------------------------------------------------------
# Abstract storage interface
# ---------------------------------------------------------------------------

class EvidenceStorageBackend(ABC):
    """Abstract interface for evidence file storage."""

    @abstractmethod
    def upload_evidence(
        self,
        subfolder: str,
        filename: str,
        content: bytes,
    ) -> tuple[str, str]:
        """
        Store *content* and return (file_reference, storage_backend_label).

        *file_reference* is the opaque internal key used to retrieve the file.
        It must NEVER be exposed as a public URL.
        """

    @abstractmethod
    def download_evidence(self, file_reference: str) -> bytes:
        """Retrieve and return the raw file bytes for *file_reference*."""

    @abstractmethod
    def delete_evidence(self, file_reference: str) -> bool:
        """Delete the stored file. Returns True on success."""

    @abstractmethod
    def get_evidence_metadata(self, file_reference: str) -> dict:
        """Return dict with keys: exists, size_bytes, last_modified."""

    @abstractmethod
    def verify_integrity(self, file_reference: str, expected_hash: str, algorithm: str = "SHA-256") -> bool:
        """Re-compute and compare the hash of the stored file."""


# ---------------------------------------------------------------------------
# Local storage backend (prototype)
# ---------------------------------------------------------------------------

class LocalEvidenceStorage(EvidenceStorageBackend):
    """
    Stores evidence files in a secure local directory.

    Root defaults to EVIDENCE_ROOT setting (isolated from datasets/ and web root).
    """

    BACKEND_LABEL = "LOCAL"

    def __init__(self, root_dir: str | Path | None = None) -> None:
        self.root = Path(root_dir or getattr(settings, "EVIDENCE_ROOT", "./evidence_store")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, file_reference: str) -> Path:
        """Resolve a file_reference to an absolute path within the storage root."""
        # file_reference is relative to root
        candidate = (self.root / file_reference).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            raise ValueError(f"Path traversal detected in file_reference: {file_reference!r}")
        return candidate

    def upload_evidence(self, subfolder: str, filename: str, content: bytes) -> tuple[str, str]:
        safe_sub = _sanitize_path_segment(subfolder)
        # Use UUID filename to prevent collision and information leakage via names
        ext = Path(filename).suffix.lower() or ".bin"
        stored_name = f"{uuid4().hex}{ext}"
        target_dir = (self.root / safe_sub).resolve()

        if self.root not in target_dir.parents and target_dir != self.root:
            raise ValueError("Path traversal detected in subfolder")

        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / stored_name
        file_path.write_bytes(content)

        # file_reference is relative path (portable if root changes)
        relative = str(Path(safe_sub) / stored_name)
        return relative, self.BACKEND_LABEL

    def download_evidence(self, file_reference: str) -> bytes:
        path = self._resolve_path(file_reference)
        if not path.is_file():
            raise FileNotFoundError(f"Evidence file not found: {file_reference!r}")
        return path.read_bytes()

    def delete_evidence(self, file_reference: str) -> bool:
        try:
            path = self._resolve_path(file_reference)
            if path.is_file():
                path.unlink()
                return True
        except (ValueError, OSError):
            pass
        return False

    def get_evidence_metadata(self, file_reference: str) -> dict:
        try:
            path = self._resolve_path(file_reference)
            if path.is_file():
                stat = path.stat()
                return {
                    "exists": True,
                    "size_bytes": stat.st_size,
                    "last_modified": stat.st_mtime,
                }
        except (ValueError, OSError):
            pass
        return {"exists": False, "size_bytes": 0, "last_modified": None}

    def verify_integrity(self, file_reference: str, expected_hash: str, algorithm: str = "SHA-256") -> bool:
        try:
            path = self._resolve_path(file_reference)
            return verify_file_hash(path, expected_hash, algorithm)
        except (ValueError, OSError):
            return False


# ---------------------------------------------------------------------------
# S3-compatible stub (ready for future implementation)
# ---------------------------------------------------------------------------

class S3EvidenceStorage(EvidenceStorageBackend):
    """
    Stub for S3-compatible object storage (AWS S3, MinIO, Ceph).
    Swap in by setting EVIDENCE_STORAGE_BACKEND=S3 and providing credentials
    via environment variables (never in source code).
    """

    BACKEND_LABEL = "S3"

    def __init__(self) -> None:
        # Credentials come from environment — boto3 picks them up automatically
        # (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION)
        self.bucket = os.environ.get("EVIDENCE_S3_BUCKET", "sentinex-evidence")

    def upload_evidence(self, subfolder: str, filename: str, content: bytes) -> tuple[str, str]:
        raise NotImplementedError("S3 backend not yet configured for this deployment")

    def download_evidence(self, file_reference: str) -> bytes:
        raise NotImplementedError("S3 backend not yet configured for this deployment")

    def delete_evidence(self, file_reference: str) -> bool:
        raise NotImplementedError("S3 backend not yet configured for this deployment")

    def get_evidence_metadata(self, file_reference: str) -> dict:
        raise NotImplementedError("S3 backend not yet configured for this deployment")

    def verify_integrity(self, file_reference: str, expected_hash: str, algorithm: str = "SHA-256") -> bool:
        raise NotImplementedError("S3 backend not yet configured for this deployment")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_evidence_storage() -> EvidenceStorageBackend:
    """
    Return the configured evidence storage backend.
    Backend is selected via EVIDENCE_STORAGE_BACKEND env var (default LOCAL).
    """
    backend_name = os.environ.get("EVIDENCE_STORAGE_BACKEND", "LOCAL").upper()
    if backend_name == "LOCAL":
        return LocalEvidenceStorage()
    if backend_name == "S3":
        return S3EvidenceStorage()
    raise ValueError(f"Unknown EVIDENCE_STORAGE_BACKEND: {backend_name!r}")


# Singleton instance for app lifetime
_evidence_storage: EvidenceStorageBackend | None = None


def evidence_storage() -> EvidenceStorageBackend:
    global _evidence_storage
    if _evidence_storage is None:
        _evidence_storage = get_evidence_storage()
    return _evidence_storage
