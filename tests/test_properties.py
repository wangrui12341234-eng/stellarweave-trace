"""Property tests: no generated payload may sneak past the deterministic layer."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from stellarweave_trace import PayloadRef, Step, TokenUsage

sha = st.text(alphabet="0123456789abcdef", min_size=64, max_size=64)
payload = st.builds(
    dict,
    bucket=st.just("sw-traces"),
    key=st.text(min_size=1, max_size=64),
    sha256=sha,
    size_bytes=st.integers(min_value=0, max_value=10**9),
)


@given(cached=st.integers(min_value=0), inp=st.integers(min_value=0))
@settings(max_examples=200)
def test_cache_invariant_holds_for_all_pairs(cached: int, inp: int):
    if cached > inp:
        try:
            TokenUsage(input_tokens=inp, output_tokens=0, cached_input_tokens=cached)
        except ValidationError:
            return
        raise AssertionError("cache > input accepted")
    t = TokenUsage(input_tokens=inp, output_tokens=0, cached_input_tokens=cached)
    assert t.cached_input_tokens <= t.input_tokens


@given(
    latency=st.integers(min_value=0, max_value=10**7),
    ttft=st.integers(min_value=0, max_value=10**7),
    data=st.data(),
)
@settings(max_examples=200)
def test_ttft_invariant_holds_for_all_pairs(latency: int, ttft: int, data):
    base = data.draw(
        st.fixed_dictionaries(
            {
                "run_id": st.just("r1"),
                "step_index": st.integers(min_value=0, max_value=1000),
                "agent_role": st.sampled_from(["planner", "support", "content"]),
                "prompt_version": st.text(min_size=1, max_size=16),
                "model": st.just("m1"),
                "input_ref": payload,
                "tokens": st.just(
                    {"input_tokens": 10, "output_tokens": 5, "cached_input_tokens": 0}
                ),
            }
        )
    )
    kw = {**base, "latency_ms": latency, "ttft_ms": ttft}
    if ttft > latency:
        try:
            Step(**kw)
        except ValidationError:
            return
        raise AssertionError("ttft > latency accepted")
    assert Step(**kw).ttft_ms <= latency


@given(data=payload)
@settings(max_examples=100)
def test_valid_payloads_always_parse(data):
    assert PayloadRef(**data).sha256 == data["sha256"]