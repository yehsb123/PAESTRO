#!/usr/bin/env python3
"""PAESTRO 검색 정확도 평가 하네스.

실행 중인 엔진(/retrieve)에 질의셋을 던져 top-1 / top-3 정확도와 MRR을 측정한다.
RAG-MCP식으로 "필요한 도구를 정확히 검색하는가"를 수치로 본다. KO/EN 혼용으로 다국어 임베딩 효과 확인.

사전준비
  1) 엔진 실행:  uvicorn app:app --port 8756   (engine/)
  2) 카탈로그 색인:  enrich 산출물을 /index 에 투입 (또는 확장의 재색인)

실행
  python eval/run_eval.py --engine http://127.0.0.1:8756 --k 3
  python eval/run_eval.py --queryset eval/queryset.json --lang ko   # 언어별 필터
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def retrieve(engine: str, query: str, k: int) -> list[str]:
    req = urllib.request.Request(
        f"{engine.rstrip('/')}/retrieve",
        data=json.dumps({"query": query, "k": k}).encode("utf-8"),
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        hits = json.loads(r.read()).get("hits", [])
    return [h.get("id") for h in hits]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="http://127.0.0.1:8756")
    ap.add_argument("--queryset", default="eval/queryset.json")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--lang", choices=["ko", "en"], help="언어 필터(미지정=전체)")
    args = ap.parse_args()

    qs = json.loads(Path(args.queryset).read_text(encoding="utf-8"))["queries"]
    if args.lang:
        qs = [q for q in qs if q.get("lang") == args.lang]
    if not qs:
        print("질의 없음", file=sys.stderr)
        return 1

    top1 = top_k = 0
    rr_sum = 0.0
    rows = []
    for q in qs:
        try:
            ids = retrieve(args.engine, q["q"], args.k)
        except Exception as e:  # 엔진 미실행 등
            print(f"[엔진 호출 실패] {e}\n엔진을 먼저 띄우고 카탈로그를 색인하세요.", file=sys.stderr)
            return 2
        expected = set(q["expected"])
        rank = next((i + 1 for i, cid in enumerate(ids) if cid in expected), 0)
        hit1 = bool(ids) and ids[0] in expected
        hitk = rank > 0
        top1 += hit1
        top_k += hitk
        rr_sum += (1.0 / rank) if rank else 0.0
        rows.append((q["q"], "✓1" if hit1 else (f"✓{rank}" if hitk else "✗"), ids[0] if ids else "-"))

    n = len(qs)
    print(f"\n질의 {n}개 · k={args.k}" + (f" · lang={args.lang}" if args.lang else ""))
    for qtext, mark, top in rows:
        print(f"  {mark:4} {qtext[:34]:36} → {top}")
    print(f"\ntop-1  {top1}/{n} = {top1/n:.1%}")
    print(f"top-{args.k}  {top_k}/{n} = {top_k/n:.1%}")
    print(f"MRR    {rr_sum/n:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
