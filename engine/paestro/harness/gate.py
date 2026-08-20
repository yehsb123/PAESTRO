"""[5] 하네스 안전 게이트 — side_effects 기반 실행 승인 판단.

read_only/reversible → 자동 실행 가능. irreversible → 실행 전 사람 승인 필요.
오케스트레이터의 Execute 단계와 확장(executeCommand 직전)이 이 판단을 경유한다.
"""
from __future__ import annotations

from typing import Any

APPROVAL_REQUIRED = {"irreversible"}


def needs_approval(side_effects: str | None) -> bool:
    """이 side_effects 등급이 실행 전 사용자 승인을 요구하는가."""
    return (side_effects or "read_only") in APPROVAL_REQUIRED


def gate(capability: dict[str, Any]) -> dict[str, Any]:
    """capability에 승인 필요 여부를 표시해 돌려준다(비파괴)."""
    se = capability.get("side_effects", "read_only")
    return {**capability, "needs_approval": needs_approval(se)}
