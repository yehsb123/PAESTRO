#!/usr/bin/env python3
"""멀티스텝 오케스트레이션 데모 — 복합 요청 → 단계 분해 → 각 단계를 엔진에서 검색 → 실행 계획.

"환불하고 깃허브 이슈 남기고 슬랙 알림" 같은 한 문장을 접속사로 쪼개, 각 하위 작업을
살아있는 엔진(/retrieve)에서 검색해 크로스-런타임(REST·MCP·VS Code) 실행 계획을 만든다.
irreversible 단계는 ⚠ 승인 게이트로 표시. (분해는 규칙 기반 스파이크 — 이후 LLM planner로 대체)

준비:  엔진 실행 + 레지스트리 색인(python registry/to_index.py --post ...)
실행:  python demo/orchestrate.py "환불하고 깃허브 이슈 남기고 슬랙에 알림" --engine http://127.0.0.1:8756
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 접속: 그리고/그다음 · 한국어 순차 연결어미 '-고 '(환불하고, 만들고) · 콤마 · then/and
SPLIT = re.compile(r"\s*(?:그리고|그다음|그\s*다음|한\s*[뒤후]|,|;|\bthen\b|\band\b)\s*|(?<=[가-힣])고\s+", re.I)


def decompose(req: str) -> list[str]:
    parts = [p.strip(" .·-") for p in SPLIT.split(req) if p.strip(" .·-")]
    return parts or [req]


def retrieve(engine: str, query: str, k: int) -> list[dict]:
    body = json.dumps({"query": query, "k": k}).encode("utf-8")
    r = urllib.request.Request(f"{engine.rstrip('/')}/retrieve", data=body,
                               headers={"content-type": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read()).get("hits", [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("request", nargs="+")
    ap.add_argument("--engine", default="http://127.0.0.1:8756")
    ap.add_argument("-k", type=int, default=3)
    args = ap.parse_args()
    req = " ".join(args.request)

    steps = decompose(req)
    print(f'\n요청: "{req}"')
    print(f"→ {len(steps)}단계로 분해\n")

    plan, needs_approval = [], 0
    for i, s in enumerate(steps, 1):
        try:
            hits = retrieve(args.engine, s, args.k)
        except Exception as e:
            print(f"  [{i}] {s} — 엔진 호출 실패({e})", file=sys.stderr)
            return 2
        if not hits:
            print(f"  [{i}] {s}\n        (매칭 도구 없음)")
            continue
        top = hits[0]
        se = top.get("side_effects", "read_only")
        warn = "  ⚠ 승인필요" if se == "irreversible" else ""
        rt = (top.get("id", "").split(".")[0])
        print(f"  [{i}] \"{s}\"")
        print(f"        → {top.get('intent', top.get('id'))}  [{rt}]{warn}")
        for alt in hits[1:args.k]:
            print(f"          · 대안: {alt.get('intent', alt.get('id'))}")
        plan.append((s, top))
        needs_approval += se == "irreversible"

    print(f"\n실행 계획: {len(plan)}단계" + (f" · 승인 필요 {needs_approval}건 ⚠" if needs_approval else ""))
    print("(규칙 기반 분해 스파이크 — 실제 제품은 LLM planner + Verify 루프로 확장)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
