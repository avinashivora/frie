"""Add FRIE six-dimension assessment fields to the predictions table."""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.db.session import engine


COLUMNS = {
    "algorithm_version": ("VARCHAR(64) DEFAULT 'FRIE-6D-v1.0'"),
    "frie_maximum": ("FLOAT DEFAULT 600.0"),
    "scoring_profile": ("VARCHAR(16) DEFAULT 'neutral'"),
    "dimensions_json": ("TEXT DEFAULT '{}'"),
    "overall_coverage": ("FLOAT"),
    "overall_confidence": ("FLOAT"),
}


def main() -> None:
    inspector = inspect(engine)

    if "predictions" not in inspector.get_table_names():
        raise RuntimeError(
            "The predictions table does not exist. "
            "Start the application once so the base schema is created."
        )

    existing = {column["name"] for column in inspector.get_columns("predictions")}

    with engine.begin() as connection:
        for column_name, definition in COLUMNS.items():
            if column_name in existing:
                print(f"[SKIP] {column_name} already exists.")
                continue

            statement = f"ALTER TABLE predictions ADD COLUMN {column_name} {definition}"

            connection.execute(text(statement))

            print(f"[ADD] {column_name}")

    print("FRIE-6D assessment migration completed.")


if __name__ == "__main__":
    main()
