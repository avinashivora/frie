"""Add FRIE six-dimension assessment fields to the predictions table."""

from __future__ import annotations

from app.db.session import engine
from sqlalchemy import inspect, text

COLUMNS = {
    "algorithm_version": ("VARCHAR(64) DEFAULT 'FRIE-6D-v1.0'"),
    "frie_maximum": ("FLOAT DEFAULT 600.0"),
    "scoring_profile": ("VARCHAR(16) DEFAULT 'neutral'"),
    "dimensions_json": ("TEXT DEFAULT '{}'"),
    "overall_coverage": ("FLOAT"),
    "overall_confidence": ("VARCHAR(16)"),
}


def main() -> None:
    inspector = inspect(engine)

    if "predictions" not in inspector.get_table_names():
        raise RuntimeError(
            "The predictions table does not exist. "
            "Start the application once so the base schema is created."
        )

    columns = {column["name"]: column for column in inspector.get_columns("predictions")}

    with engine.begin() as connection:
        confidence = columns.get("overall_confidence")
        if confidence and "CHAR" not in str(confidence["type"]).upper():
            # Preserve legacy numeric data under an explicit legacy name.
            # SQLite cannot change a column's affinity in place; adding a new
            # qualitative column avoids unsafe table rebuilds/FK rewrites.
            if "overall_confidence_legacy" not in columns:
                connection.execute(text(
                    "ALTER TABLE predictions RENAME COLUMN overall_confidence "
                    "TO overall_confidence_legacy"
                ))
                print("[RENAME] overall_confidence -> overall_confidence_legacy")
            connection.execute(text(
                "ALTER TABLE predictions ADD COLUMN overall_confidence VARCHAR(16)"
            ))
            print("[ADD] overall_confidence VARCHAR(16)")

        existing = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(predictions)"))
        }
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
