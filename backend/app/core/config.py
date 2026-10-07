"""Environment-aware application settings with path-safe model locations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil


@dataclass(frozen=True)
class Settings:
    """Runtime settings. No production secrets are defined; demo credential
    defaults below are prototype-only and documented as such."""

    backend_dir: Path
    model_path: Path
    model_config_path: Path
    cors_origins: tuple[str, ...]
    database_url: str
    session_days: int
    seed_demo_user: bool
    demo_email: str
    demo_password: str
    storage_dir: Path
    max_upload_mb: int
    tesseract_cmd: str | None


def _cors_origins_from_environment() -> tuple[str, ...]:
    raw_origins = os.getenv("FRIE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())


def _flag_from_environment(name: str, default: bool) -> bool:
    return os.getenv(name, "true" if default else "false").strip().lower() in ("1", "true", "yes")


def _positive_int_from_environment(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _tesseract_command() -> str | None:
    """Locate the Tesseract binary: explicit env, PATH lookup, standard install path."""

    configured = (os.getenv("FRIE_TESSERACT_CMD") or "").strip()
    if configured and Path(configured).is_file():
        return configured
    on_path = shutil.which("tesseract")
    if on_path:
        return on_path
    standard = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if standard.is_file():
        return str(standard)
    return None


def get_settings() -> Settings:
    """Build settings from paths relative to this module, not the working directory."""

    backend_dir = Path(__file__).resolve().parents[2]
    models_dir = backend_dir / "models"
    return Settings(
        backend_dir=backend_dir,
        model_path=models_dir / "frie_xgboost_final_pipeline_v2.joblib",
        model_config_path=models_dir / "frie_model_config_v2.json",
        cors_origins=_cors_origins_from_environment(),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./frie.db"),
        session_days=int(os.getenv("FRIE_SESSION_DAYS", "7")),
        seed_demo_user=_flag_from_environment("FRIE_SEED_DEMO_USER", False),
        demo_email=os.getenv("FRIE_DEMO_EMAIL", "individual@frie.demo"),
        demo_password=os.getenv("FRIE_DEMO_PASSWORD", "FRIE123"),
        storage_dir=Path(os.getenv("FRIE_STORAGE_DIR", str(backend_dir / "storage" / "documents"))),
        max_upload_mb=_positive_int_from_environment("FRIE_MAX_UPLOAD_MB", 10),
        tesseract_cmd=_tesseract_command(),
    )
