"""Export JSON Schema for the assertion layer (PR4 consumes these).

Single source of truth: Pydantic models -> JSON Schema files, checked
into schemas/ so the assertion DSL can validate traces without importing
Python (and so schema diffs show up in PR review).
"""

from __future__ import annotations

import json
from pathlib import Path

from .schema import TABLE_MODELS

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


def export_all(dest: Path = SCHEMA_DIR) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for table, model in TABLE_MODELS.items():
        path = dest / f"{table}.schema.json"
        path.write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


if __name__ == "__main__":
    for p in export_all():
        print(p)