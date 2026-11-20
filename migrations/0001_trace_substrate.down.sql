-- Rollback for 0001_trace_substrate.up.sql. Order matters: children first.
BEGIN;
DROP TABLE IF EXISTS tool_calls;
DROP TABLE IF EXISTS steps;
DROP TABLE IF EXISTS runs;
COMMIT;