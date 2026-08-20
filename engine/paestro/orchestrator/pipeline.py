"""[4] 오케스트레이터 파이프라인 — 멀티스텝 Plan → Retrieve → (Execute는 확장/실행기) → 승인게이트.

복합 요구를 단계로 분해(rule-based planner)하고, 각 단계를 의미검색으로 도구 매칭한 뒤,
하네스 게이트로 위험 단계에 승인 플래그를 단다. 단일 요구면 1단계 계획이 된다.
LLM planner는 ANTHROPIC_API_KEY가 있을 때 rule-based를 대체(향후) — 지금은 규칙 기반.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from ..harness import gate
from ..index import store

# 접속: 그리고/그다음 · 한국어 순차 연결어미 '-고 ' · 콤마 · then/and
_SPLIT = re.compile(r"\s*(?:그리고|그다음|그\s*다음|한\s*[뒤후]|,|;|\bthen\b|\band\b)\s*|(?<=[가-힣])고\s+", re.I)


def _rule_decompose(query: str) -> list[str]:
    parts = [p.strip(" .·-") for p in _SPLIT.split(query) if p and p.strip(" .·-")]
    return parts or [query]


def _llm_decompose(query: str) -> list[str] | None:
    """ANTHROPIC_API_KEY가 있으면 Claude planner로 분해. 없거나 실패하면 None(규칙기반 폴백)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        from anthropic import Anthropic

        client = Anthropic()
        model = os.environ.get("PAESTRO_PLANNER_MODEL", "claude-sonnet-5")
        msg = client.messages.create(
            model=model, max_tokens=512,
            messages=[{"role": "user", "content":
                       f"사용자 요구를 실행 가능한 개별 작업 단계로 분해해라. 각 단계는 도구 하나로 수행 가능한 짧은 구.\n"
                       f"JSON 문자열 배열만 출력(설명 금지).\n\n요구: {query}"}],
        )
        text = re.sub(r"^```(?:json)?|```$", "", msg.content[0].text.strip(), flags=re.M).strip()
        steps = [str(s).strip() for s in json.loads(text) if str(s).strip()]
        return steps or None
    except Exception:
        return None


def decompose(query: str) -> list[str]:
    """LLM planner 우선(키 있을 때), 실패 시 규칙 기반."""
    return _llm_decompose(query) or _rule_decompose(query)


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
