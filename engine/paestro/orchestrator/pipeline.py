"""[4] 오케스트레이터 파이프라인 — 멀티스텝 Plan → Retrieve → (Execute는 확장/실행기) → 승인게이트.

복합 요구를 단계로 분해(rule-based planner)하고, 각 단계를 의미검색으로 도구 매칭한 뒤,
하네스 게이트로 위험 단계에 승인 플래그를 단다. 단일 요구면 1단계 계획이 된다.
LLM planner는 ANTHROPIC_API_KEY가 있을 때 rule-based를 대체(향후) — 지금은 규칙 기반.
"""
from __future__ import annotations

import re
from typing import Any

from ..harness import gate
from ..index import store

# 접속: 그리고/그다음 · 한국어 순차 연결어미 '-고 ' · 콤마 · then/and
_SPLIT = re.compile(r"\s*(?:그리고|그다음|그\s*다음|한\s*[뒤후]|,|;|\bthen\b|\band\b)\s*|(?<=[가-힣])고\s+", re.I)


def decompose(query: str) -> list[str]:
    parts = [p.strip(" .·-") for p in _SPLIT.split(query) if p and p.strip(" .·-")]
    return parts or [query]


def orchestrate(query: str, k: int = 5) -> dict[str, Any]:
    """복합 요구 → 단계별 실행 계획."""
    step_texts = decompose(query)
    steps: list[dict[str, Any]] = []
    approvals = 0
    for idx, s in enumerate(step_texts, 1):
        cands = store.query(s, k)
        chosen = gate.gate(cands[0]) if cands else None
        if chosen and chosen["needs_approval"]:
            approvals += 1
        steps.append({
            "n": idx,
            "step": s,
            "chosen": chosen,
            "alternatives": cands[1:],
        })
    return {
        "query": query,
        "multi_step": len(step_texts) > 1,
        "steps": steps,
        "needs_approval": approvals,
        # 하위호환: 단일 요구의 후보 목록
        "candidates": steps[0]["alternatives"] if len(steps) == 1 and steps[0]["chosen"] else
                      (store.query(query, k) if len(step_texts) == 1 else []),
    }
