from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

from app.core.config import settings

DATASET_DIRECTORY_BY_CATEGORY: dict[str, str] = {
    "MISSING": "missing_persons",
    "WANTED": "wanted_persons",
}


def sanitize_path_segment(segment: str) -> str:
    """Strip dangerous characters and directory traversal attempts from path components."""
    # Allow alphanumeric, hyphens, and underscores only for folder names like case numbers
    clean = re.sub(r"[^a-zA-Z0-9_\-]", "_", segment.strip())
    if not clean or clean in {".", ".."}:
        raise ValueError("Invalid path segment")
    return clean


class StorageBackend(ABC):
    """Abstract storage backend to support local and future cloud/object storage."""

    @abstractmethod
    def save(self, category: str, case_number: str, filename: str, content: bytes) -> tuple[str, str]:
        """Save file content and return (file_path, storage_type)."""
        pass

    @abstractmethod
    def delete(self, file_path: str) -> bool:
        """Delete stored file at file_path. Return True if deleted, False otherwise."""
        pass

    @abstractmethod
    def exists(self, file_path: str) -> bool:
        """Check if file exists at file_path."""
        pass

    @abstractmethod
    def get_dataset_dir(self, category: str, case_number: str) -> Path:
        """Get or create the storage directory for the given category and case."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, root_dir: str | Path | None = None) -> None:
        self.root_dir = Path(root_dir or settings.DATASET_ROOT).resolve()

    def _resolve_case_dir(self, category: str, case_number: str) -> Path:
        cat_upper = category.upper()
        folder_name = DATASET_DIRECTORY_BY_CATEGORY.get(cat_upper)
        if not folder_name:
            raise ValueError(f"Unsupported dataset category: {category}")

        safe_case_number = sanitize_path_segment(case_number)
        target_dir = (self.root_dir / folder_name / safe_case_number).resolve()

        # Path traversal guard
        if self.root_dir not in target_dir.parents:
            raise ValueError("Unsafe dataset directory path traversal detected")

        return target_dir

    def get_dataset_dir(self, category: str, case_number: str) -> Path:
        target_dir = self._resolve_case_dir(category, case_number)
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def save(self, category: str, case_number: str, filename: str, content: bytes) -> tuple[str, str]:
        case_dir = self.get_dataset_dir(category, case_number)
        safe_filename = Path(filename).name  # Prevent path traversal in filename
        target_file = (case_dir / safe_filename).resolve()

        if case_dir not in target_file.parents:
            raise ValueError("Unsafe file path traversal detected")

        target_file.write_bytes(content)
        return str(target_file), "LOCAL"

    def delete(self, file_path: str) -> bool:
        target = Path(file_path).resolve()
        if self.root_dir in target.parents and target.is_file():
            try:
                target.unlink()
                return True
            except OSError:
                return False
        return False

    def exists(self, file_path: str) -> bool:
        target = Path(file_path).resolve()
        return self.root_dir in target.parents and target.is_file()


class FileManager:
    """Coordinates file management across configured storage backends."""

    def __init__(self, backend: StorageBackend | None = None) -> None:
        self.backend: StorageBackend = backend or LocalStorageBackend()

    def generate_filename(self, extension: str) -> str:
        clean_ext = extension if extension.startswith(".") else f".{extension}"
        return f"{uuid4().hex}{clean_ext}"

    def save_image(
        self,
        category: str,
        case_number: str,
        extension: str,
        content: bytes,
    ) -> tuple[str, str, str]:
        """
        Saves an image under the correct category and case directory.
        Returns: (stored_file_name, file_path, storage_type)
        """
        stored_file_name = self.generate_filename(extension)
        file_path, storage_type = self.backend.save(category, case_number, stored_file_name, content)
        return stored_file_name, file_path, storage_type

    def remove_file(self, file_path: str) -> bool:
        return self.backend.delete(file_path)

    def get_dataset_directory(self, category: str, case_number: str) -> Path:
        return self.backend.get_dataset_dir(category, case_number)


# Default singleton instance
default_file_manager = FileManager()


# Convenience wrappers for backward compatibility
def dataset_directory(category: str, case_number: str) -> Path:
    return default_file_manager.get_dataset_directory(category, case_number)


def generate_stored_filename(extension: str) -> str:
    return default_file_manager.generate_filename(extension)


def remove_stored_file(file_path: str) -> None:
    default_file_manager.remove_file(file_path)
