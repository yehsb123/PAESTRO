#!/usr/bin/env python3
"""정합성/결정성 하네스 — queryset을 엔진 /retrieve로 N회 반복해 결과가 흔들리는지 검증.

같은 질의를 여러 번 던졌을 때 엔진이 **매번 동일한 top-k**를 주는지(결정성)와
top-1/top-3/MRR의 회차 간 변동을 잰다. 반환 id 목록을 이어붙여 해시(서명)를 내고,
서명 종류가 1이면 완전 결정적. 검색 결정성이 깨지면(리랭크 불안정·부동소수 흔들림 등)
여기서 서명이 갈라져 즉시 드러난다.

전제: 엔진 실행 + 색인 →  `cd engine && uvicorn app:app --port 8756`
CI 제외(모델·엔진 기동 필요). 종료코드: 비결정적(서명>1)이면 1.

  python eval/consistency.py                 # 100회, top-3, 레지스트리 queryset
  python eval/consistency.py --runs 20 --k 1
  python eval/consistency.py --queryset eval/queryset.registry.json --base http://127.0.0.1:8756
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent


def retrieve(base: str, query: str, k: int) -> list[str]:
    req = urllib.request.Request(
        base + "/retrieve",
        data=json.dumps({"query": query, "k": k}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return [h["id"] for h in json.loads(r.read().decode("utf-8"))["hits"]]


def score_run(base: str, queries: list[dict], k: int) -> tuple[int, int, float, str]:
    top1 = topk = 0
    rr = 0.0
    sig_parts = []
    for q in queries:
        ids = retrieve(base, q["q"], k)
        sig_parts.append("|".join(ids))
        exp = set(q.get("expected", []))
        rank = next((i + 1 for i, c in enumerate(ids) if c in exp), 0)
        top1 += bool(ids) and ids[0] in exp
        topk += rank > 0
        rr += (1.0 / rank) if rank else 0.0
    sig = hashlib.sha1("\n".join(sig_parts).encode("utf-8")).hexdigest()[:12]
    return top1, topk, rr / len(queries), sig


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--base", default="http://127.0.0.1:8756")
    ap.add_argument("--queryset", default="eval/queryset.registry.json")
    args = ap.parse_args()

    try:
        urllib.request.urlopen(args.base + "/health", timeout=5)
    except (urllib.error.URLError, TimeoutError):
        print(f"✗ 엔진 연결 불가: {args.base} — `cd engine && uvicorn app:app --port 8756` 먼저 실행")
        return 2

    queries = json.loads((ROOT / args.queryset).read_text(encoding="utf-8"))["queries"]
    n = len(queries)

    top1s, topks, mrrs, sigs = [], [], [], {}
    t0 = time.time()
    for i in range(args.runs):
        a, b, m, s = score_run(args.base, queries, args.k)
        top1s.append(a); topks.append(b); mrrs.append(m)
        sigs[s] = sigs.get(s, 0) + 1
        if (i + 1) % 20 == 0:
            print(f"  ...{i + 1}/{args.runs}회")
    dt = time.time() - t0

    print(f"\n=== 정합성 {args.runs}회 (문항 {n} · k={args.k} · 총 {args.runs * n} 검색 · {dt:.1f}s) ===")
    print(f"top-1  {min(top1s)}~{max(top1s)}/{n}  ({min(top1s)/n:.1%}~{max(top1s)/n:.1%})")
    print(f"top-{args.k}  {min(topks)}~{max(topks)}/{n}  ({min(topks)/n:.1%}~{max(topks)/n:.1%})")
    print(f"MRR    {min(mrrs):.4f}~{max(mrrs):.4f}  (평균 {statistics.mean(mrrs):.4f})")
    deterministic = len(sigs) == 1
    print(f"서명 종류 = {len(sigs)}  → {'✓ 전 회차 동일(완전 결정적)' if deterministic else '⚠ 회차별 변동(비결정적)'}")
    for s, c in sorted(sigs.items(), key=lambda x: -x[1]):
        print(f"   {s} × {c}회")
    return 0 if deterministic else 1


if __name__ == "__main__":
    raise SystemExit(main())
