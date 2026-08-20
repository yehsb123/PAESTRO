#!/usr/bin/env python3
"""오프라인 멀티스텝 오케스트레이터 — 복합 요청 → 단계 분해 → 각 단계 검색 → 크로스-런타임 실행 계획.

엔진 불필요(레지스트리 catalog에서 직접 검색). 한 문장의 복합 요청을 접속사(한국어 '-고'·그리고·then/and·콤마)로
쪼개, 각 하위 작업을 search.py로 검색해 도구를 고르고, 위험(irreversible) 단계는 승인 게이트로 표시한다.
규칙 기반 분해(스파이크). ANTHROPIC_API_KEY가 있으면 향후 LLM planner로 대체 가능.

  python registry/orchestrate.py "저장소 복제하고 컨테이너 실행하고 이슈 생성"
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "registry"))
import search as S  # noqa: E402

# 접속: 그리고/그다음 · 한국어 순차 연결어미 '-고 ' · 콤마 · then/and
SPLIT = re.compile(r"\s*(?:그리고|그다음|그\s*다음|한\s*[뒤후]|,|;|\bthen\b|\band\b)\s*|(?<=[가-힣])고\s+", re.I)


def decompose(req: str) -> list[str]:
    parts = [p.strip(" .·-") for p in SPLIT.split(req) if p and p.strip(" .·-")]
    return parts or [req]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("request", nargs="+")
    ap.add_argument("-k", type=int, default=2, help="단계별 대안 개수")
    args = ap.parse_args()
    req = " ".join(args.request)

    caps = S.load_catalog()
    steps = decompose(req)
    print(f'\n요청: "{req}"')
    print(f"→ {len(steps)}단계 분해 · 레지스트리 {len(caps)}개에서 계획\n")

    plan = []
    need_approval = 0
    for i, s in enumerate(steps, 1):
        hits = S.search(s, caps, args.k)
        if not hits:
            print(f"  {i}. \"{s}\"  → (매칭 도구 없음)")
            continue
        top = hits[0]
        rt = top["id"].split(".")[0]
        warn = "  ⚠ 승인필요" if top.get("side_effects") == "irreversible" else ""
        print(f"  {i}. \"{s}\"")
        print(f"       → {top.get('intent', top['id'])}  [{rt}]{warn}")
        for alt in hits[1:]:
            print(f"         · 대안: {alt.get('intent', alt['id'])}")
        plan.append((s, top))
        need_approval += top.get("side_effects") == "irreversible"

    print(f"\n실행 계획: {len(plan)}/{len(steps)}단계" + (f" · 승인 필요 {need_approval}건 ⚠" if need_approval else ""))
    print("(규칙 기반 분해 · 실제 실행은 확장(executeCommand)/엔진이 담당. LLM planner로 업그레이드 가능)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
