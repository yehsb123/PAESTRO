"""PAESTRO 안전 분류 정책 — side_effects 판정의 단일 소스(single source of truth).

등급  read_only  <  reversible  <  irreversible
원칙  보수적. 애매하면 더 위험한 쪽으로 올린다(오탐이 미탐보다 안전).

이 판정값이 확장의 승인 게이트를 결정한다:
  irreversible → 실행 직전 사용자 승인 모달 필수
  reversible   → 실행하되 되돌리기 가능
  read_only    → 자동 실행
"""
from __future__ import annotations

import re

# 되돌릴 수 없는/외부에 영향: 삭제·초기화·배포·발행·강제
IRREVERSIBLE = re.compile(
    r"\b(delete|remove|reset|revert|discard|drop|destroy|wipe|clean|prune|purge|"
    r"uninstall|publish|deploy|release|push|force|overwrite|erase|kill|terminate|"
    r"clear\s*all|hard\s*reset)\b|"
    r"삭제|제거|초기화|되돌|폐기|버리|배포|발행|덮어|강제|종료",
    re.I,
)
# 상태·파일 변경(되돌리기 가능): 수정·생성·저장·이동
REVERSIBLE = re.compile(
    r"\b(fix|format|rename|edit|apply|add|create|generate|write|save|refactor|"
    r"organize|sort|insert|replace|install|update|move|convert|import|commit|stage|"
    r"rewrite|fold|comment|indent)\b|"
    r"수정|고치|정리|생성|저장|추가|변경|바꾸|커밋|서식|포맷",
    re.I,
)


def classify_side_effects(text: str) -> str:
    """명령 텍스트(intent+keywords+command)로 side_effects 등급을 판정."""
    if IRREVERSIBLE.search(text or ""):
        return "irreversible"
    if REVERSIBLE.search(text or ""):
        return "reversible"
    return "read_only"
