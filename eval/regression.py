#!/usr/bin/env python3
"""검색 회귀 테스트 — 커밋된 fixture 카탈로그 위에서 실제 search.py 로직의 top-3 정확도를 재고,
임계 이하로 떨어지면 실패(비0 종료). CI에서 검색 품질을 지킨다(엔진·크롤 불필요).

  python eval/regression.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "registry"))
import search as S  # noqa: E402

# 임계(현재 fixture 실측 대비 여유): 회귀 감지가 목적
MIN = {"전체": 0.70, "KO": 0.62, "EN": 0.80}


def main() -> int:
    caps = json.loads((ROOT / "eval" / "fixture_catalog.json").read_text(encoding="utf-8"))
    qs = json.loads((ROOT / "eval" / "queryset.registry.json").read_text(encoding="utf-8"))["queries"]

    def hit(q, k=3):
        ids = {c["id"] for c in S.search(q["q"], caps, k)}
        return bool(ids & set(q["expected"]))

    buckets = {"전체": qs, "KO": [q for q in qs if q["lang"] == "ko"], "EN": [q for q in qs if q["lang"] == "en"]}
    fail = []
    print(f"검색 회귀 테스트 · fixture {len(caps)}개 · 질의 {len(qs)}개 (top-3)")
    for label, sub in buckets.items():
        n = len(sub) or 1
        acc = sum(hit(q) for q in sub) / n
        mark = "OK" if acc >= MIN[label] else "FAIL"
        if acc < MIN[label]:
            fail.append(f"{label} {acc:.0%} < {MIN[label]:.0%}")
        print(f"  {label:5} {acc:.0%}  (임계 {MIN[label]:.0%})  {mark}")
    if fail:
        print("회귀 감지: " + ", ".join(fail))
        return 1
    print("통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
