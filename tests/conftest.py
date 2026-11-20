from __future__ import annotations

import pytest


@pytest.fixture
def payload_ref() -> dict:
    return {
        "bucket": "sw-traces",
        "key": "runs/r1/step-0/input.json",
        "sha256": "a" * 64,
        "size_bytes": 1024,
    }


@pytest.fixture
def tokens() -> dict:
    return {"input_tokens": 1200, "output_tokens": 300, "cached_input_tokens": 900}


@pytest.fixture
def step_kwargs(payload_ref, tokens) -> dict:
    return {
        "run_id": "r1",
        "step_index": 0,
        "agent_role": "planner",
        "prompt_version": "planner-v3",
        "model": "judge-small-2025-11",
        "input_ref": payload_ref,
        "tokens": tokens,
        "latency_ms": 2100,
        "ttft_ms": 450,
    }