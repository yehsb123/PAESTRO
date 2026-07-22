"""[4] 오케스트레이터 파이프라인 — 단일-스텝 스파이크.

지금: query → Retrieve(의미검색) → 후보 조립.
다음(depth-3): planner(요구 분해)·executor(다중 도구 체이닝)·Verify 루프 추가.
LLM planning은 ANTHROPIC_API_KEY 의존이라 이 단계에선 뺀다.
"""
from __future__ import annotations

from typing import Any

from ..index import store


def orchestrate(query: str, k: int = 5) -> dict[str, Any]:
    candidates = store.query(query, k)
    return {"query": query, "candidates": candidates}
