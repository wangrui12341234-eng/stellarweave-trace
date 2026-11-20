"""DDL <-> model contract: a model change without a migration fails CI.

We parse the up-migration column list (no live Postgres needed in PR1)
and assert it matches the Pydantic-derived column list exactly, in both
directions. PR2 adds a live-database round-trip on top of this.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from stellarweave_trace.schema import TABLE_MODELS, table_columns
from stellarweave_trace.schema_export import export_all

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "migrations" / "0001_trace_substrate.up.sql"
DOWN = ROOT / "migrations" / "0001_trace_substrate.down.sql"


def ddl_columns(sql: str, table: str) -> list[str]:
    body = re.search(
        rf"CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\);", sql, re.S
    )
    assert body, f"table {table} missing from up-migration"
    cols: list[str] = []
    for line in body.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith(("UNIQUE", "CHECK", "FOREIGN", "PRIMARY")):
            continue
        m = re.match(r"([a-z_]+)\s+", line)
        if m:
            cols.append(m.group(1))
    return cols


def test_every_table_present_and_columns_match():
    sql = UP.read_text(encoding="utf-8")
    for table in TABLE_MODELS:
        assert ddl_columns(sql, table) == table_columns(table), (
            f"{table}: DDL and Pydantic model disagree — write a migration"
        )


def test_down_drops_children_before_parents():
    sql = DOWN.read_text(encoding="utf-8")
    order = re.findall(r"DROP TABLE IF EXISTS ([a-z_]+);", sql)
    assert order == ["tool_calls", "steps", "runs"]


def test_up_is_transactional():
    sql = UP.read_text(encoding="utf-8")
    statements = "\n".join(
        ln for ln in sql.splitlines() if ln.strip() and not ln.strip().startswith("--")
    )
    assert statements.strip().startswith("BEGIN;")
    assert statements.strip().endswith("COMMIT;")


def test_json_schema_export_roundtrip(tmp_path):
    paths = export_all(tmp_path)
    assert {p.stem for p in paths} == {
        "runs.schema", "steps.schema", "tool_calls.schema"
    }
    for p in paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        assert doc["type"] == "object"
        assert "properties" in doc


def test_exported_schemas_are_current(tmp_path):
    """Committed schemas/ must equal a fresh export — stale schema = CI fail."""
    committed = ROOT / "schemas"
    if not committed.exists():
        return  # first export happens in CI bootstrap
    fresh = export_all(tmp_path)
    for p in fresh:
        c = committed / p.name
        assert c.exists(), f"{p.name} not committed"
        assert json.loads(c.read_text()) == json.loads(p.read_text()), (
            f"{p.name} is stale — re-run schema_export"
        )