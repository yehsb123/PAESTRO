#!/usr/bin/env python3
"""오프라인 렉시컬 baseline 평가 (엔진 불필요).

enriched 카탈로그 + queryset을 받아 토큰 겹침(lexical)으로 top-k 정확도를 낸다.
이건 '바닥선'이다 — 엔진의 다국어 임베딩(semantic)은 이보다 높아야 한다.
특히 KO 질의↔EN title은 렉시컬로 거의 못 맞으므로, KO≪EN 격차가 곧 다국어 임베딩의 존재 이유다.

실행
  python enrich/enrich.py --in enrich/sample_catalog.json --out enrich/out --heuristic
  python eval/baseline.py --catalog enrich/out/enriched_catalog.json --queryset eval/queryset.json --k 3
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def tokens(s: str) -> list[str]:
    return [t for t in re.split(r"[\s._:\-/]+", (s or "").lower()) if len(t) > 1]


def rank(query: str, caps: list[dict], k: int) -> list[str]:
    q = tokens(query)
    scored = []
    for c in caps:
        text = set(tokens(c.get("embedding_text") or c.get("intent", "")))
        score = sum(len(t) for t in q if t in text)
        if score:
            scored.append((score, c["id"]))
    scored.sort(reverse=True)
    return [cid for _, cid in scored[:k]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--queryset", default="eval/queryset.json")
    ap.add_argument("--k", type=int, default=3)
    args = ap.parse_args()

    caps = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    qs = json.loads(Path(args.queryset).read_text(encoding="utf-8"))["queries"]

    def score(subset: list[dict]) -> tuple[int, int, float]:
        t1 = tk = 0
        rr = 0.0
        for qq in subset:
            ids = rank(qq["q"], caps, args.k)
            exp = set(qq["expected"])
            r = next((i + 1 for i, cid in enumerate(ids) if cid in exp), 0)
            t1 += bool(ids) and ids[0] in exp
            tk += r > 0
            rr += (1 / r) if r else 0
        n = len(subset) or 1
        return t1, tk, rr / n

    print(f"카탈로그 {len(caps)}개 · 질의 {len(qs)}개 · k={args.k} (렉시컬 baseline)")
    for label, subset in [("전체", qs), ("KO", [q for q in qs if q.get('lang') == 'ko']), ("EN", [q for q in qs if q.get('lang') == 'en'])]:
        if not subset:
            continue
        t1, tk, mrr = score(subset)
        n = len(subset)
        print(f"  {label:5} top-1 {t1}/{n}={t1/n:.0%} · top-{args.k} {tk}/{n}={tk/n:.0%} · MRR {mrr:.2f}")
    print("\n※ KO가 EN보다 크게 낮으면 = 렉시컬로는 한국어↔영어 매칭 불가 → 다국어 임베딩(엔진) 필요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
