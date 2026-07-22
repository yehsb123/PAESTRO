"""[2] 어댑터 보강 — 결정적(heuristic) 패스.

parse 단계 capability는 side_effects가 전부 read_only이고 embedding_text가 영어뿐이라
①승인 게이트가 안 뜨고 ②한국어 질의(특히 음차어 '린트')를 못 잡는다.
이 패스가 API 키 없이 두 문제를 완화한다:
  - side_effects를 명령/의도 텍스트에서 재분류
  - 한국어 동의어를 embedding_text에 주입 (크로스링구얼 recall↑)
LLM 보강(when_to_use·args_schema)은 이 위에 얹는 다음 단계.
"""
from __future__ import annotations

from typing import Any

# 영어 토큰 → 한국어 동의어 (embedding_text 보강용)
KO_SYNONYMS: dict[str, list[str]] = {
    "lint": ["린트", "린팅", "코드검사"], "eslint": ["린트", "이에스린트"],
    "format": ["포맷", "서식", "정렬"], "prettier": ["포맷", "정렬"],
    "git": ["깃", "버전관리"], "commit": ["커밋"], "branch": ["브랜치", "분기"],
    "merge": ["머지", "병합"], "push": ["푸시"], "pull": ["풀", "받기"],
    "debug": ["디버그", "디버깅"], "test": ["테스트", "검사"], "build": ["빌드"],
    "run": ["실행", "구동"], "restart": ["재시작"], "reload": ["새로고침", "재적재"],
    "docker": ["도커"], "container": ["컨테이너"], "image": ["이미지"],
    "python": ["파이썬"], "interpreter": ["인터프리터"], "java": ["자바"],
    "refactor": ["리팩터", "리팩토링"], "rename": ["이름바꾸기", "리네임"],
    "search": ["검색", "찾기"], "find": ["찾기", "검색"],
    "open": ["열기"], "close": ["닫기"], "delete": ["삭제", "지우기"],
    "remove": ["제거", "삭제"], "install": ["설치"], "uninstall": ["제거", "삭제"],
    "create": ["생성", "만들기"], "fix": ["고치기", "수정"],
    "problem": ["문제", "오류"], "error": ["오류", "에러"],
    "terminal": ["터미널"], "task": ["작업", "태스크"], "prune": ["정리", "삭제"],
}

_IRREVERSIBLE = ("delete", "remove", "uninstall", "prune", "reset", "revert",
                 "discard", "drop", "publish", "deploy", "destroy", "force")
_REVERSIBLE = ("fix", "format", "rename", "install", "add", "create", "edit",
               "apply", "restart", "autofix", "pin", "unpin", "generate")


def _classify(text: str) -> str:
    t = text.lower()
    if any(k in t for k in _IRREVERSIBLE):
        return "irreversible"
    if any(k in t for k in _REVERSIBLE):
        return "reversible"
    return "read_only"


def enrich(cap: dict[str, Any]) -> dict[str, Any]:
    text = f"{cap.get('intent', '')} {cap.get('id', '')}"
    low = text.lower()

    cap["side_effects"] = _classify(low)

    kws: list[str] = []
    for en, kos in KO_SYNONYMS.items():
        if en in low:
            kws.extend(kos)
    if kws:
        base = cap.get("embedding_text") or cap.get("intent", "")
        cap["embedding_text"] = base + " " + " ".join(dict.fromkeys(kws))
    return cap
