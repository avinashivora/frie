"""Local filesystem storage for uploaded prototype documents.

Validation implemented here (and only here):
- non-empty file
- size limit (configurable, default 10 MB; never truncated, rejected whole)
- allow-listed extension (pdf, png, jpg, jpeg; case-insensitive)
- magic-byte check per type (PDF header, PNG signature, JPEG SOI marker)
- browser-provided MIME is advisory only and must not contradict the magic bytes

Deliberately NOT implemented: antivirus scanning, encrypted storage,
production hardening (documented as future scope, never claimed).

Stored filenames are generated hex identifiers; the original filename is
kept only as database metadata and never used as a filesystem path.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.core.config import get_settings

ALLOWED_EXTENSIONS = ("pdf", "png", "jpg", "jpeg")

EXPECTED_MIME = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}

MAGIC_BYTES = {
    "pdf": (b"%PDF-",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
}

_CHUNK_BYTES = 1024 * 1024


class UploadValidationError(ValueError):
    """Rejected upload. `kind` selects the HTTP mapping in the route."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def storage_root() -> Path:
    """Configured storage directory, created on demand. Never inside source code by default."""

    root = get_settings().storage_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


def max_upload_bytes() -> int:
    return max(1, get_settings().max_upload_mb) * 1024 * 1024


def generate_filename(extension: str) -> str:
    """Random hex filename preserving only the validated extension."""

    return f"{uuid.uuid4().hex}.{extension}"


def resolve_storage_path(filename: str) -> Path:
    """Resolve a stored filename inside the storage root, blocking traversal."""

    candidate = (storage_root() / filename).resolve()
    if candidate.parent != storage_root().resolve():
        raise UploadValidationError("path", "Invalid storage reference.")
    return candidate


def original_basename(filename: str | None) -> str:
    """Display-only basename of a client-supplied name. Never used as a path."""

    if not filename:
        return "upload"
    return Path(filename).name[-255:] or "upload"


def validate_upload(*, filename: str | None, content_type: str | None, data: bytes) -> str:
    """Validate an in-memory upload, returning its safe extension. Raises on any failure."""

    if not data:
        raise UploadValidationError("empty", "The uploaded file is empty.")
    if len(data) > max_upload_bytes():
        raise UploadValidationError("too_large", "The uploaded file exceeds the size limit.")
    extension = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise UploadValidationError("extension", "Unsupported file type. Use PDF, PNG, or JPEG.")
    if not data.startswith(MAGIC_BYTES[extension]):
        raise UploadValidationError("content", "File content does not match its extension.")
    if content_type and content_type not in ("application/octet-stream", EXPECTED_MIME[extension]):
        raise UploadValidationError("content", "File content type does not match its extension.")
    return extension


def store_file(data: bytes, extension: str) -> str:
    """Write validated bytes under a generated name. Returns the storage reference."""

    filename = generate_filename(extension)
    resolve_storage_path(filename).write_bytes(data)
    return filename


def load_file(filename: str) -> tuple[bytes, str]:
    """Read a stored file, returning bytes and its safe content type."""

    data = resolve_storage_path(filename).read_bytes()
    extension = filename.rsplit(".", 1)[-1].lower()
    return data, EXPECTED_MIME.get(extension, "application/octet-stream")


def delete_file(filename: str) -> None:
    """Best-effort removal used for orphan cleanup. Never raises for a missing file."""

    try:
        resolve_storage_path(filename).unlink(missing_ok=True)
    except UploadValidationError:
        return
