#!/usr/bin/env python3
"""self-contained 의미 검색 평가 — 크롤 레지스트리에 대한 다국어 임베딩 정확도 (엔진 불필요).

fastembed 다국어 모델로 catalog의 embedding_text와 질의를 임베딩해 cosine top-k 정확도를 낸다.
baseline(렉시컬)이 못 넘던 KO↔EN을 semantic이 얼마나 넘는지 실데이터로 증명한다.

준비:  python -m pip install fastembed
실행:  python eval/semantic.py --catalog registry/catalog.json --queryset eval/queryset.registry.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
# 경량 다국어(엔진은 더 큰 mpnet-base-v2 사용). 필요시 교체.
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def cos(a, b) -> float:
    s = d1 = d2 = 0.0
    for x, y in zip(a, b):
        s += x * y
        d1 += x * x
        d2 += y * y
    return s / ((d1 ** 0.5) * (d2 ** 0.5) + 1e-9)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="registry/catalog.json")
    ap.add_argument("--queryset", default="eval/queryset.registry.json")
    ap.add_argument("--k", type=int, default=3)
    args = ap.parse_args()

    try:
        from fastembed import TextEmbedding
    except ImportError:
        print("fastembed 필요 → python -m pip install fastembed", file=sys.stderr)
        return 2

    cat_path = ROOT / args.catalog
    if not cat_path.exists():
        cat_path = ROOT / "registry/catalog.sample.json"
    catalog = json.loads(cat_path.read_text(encoding="utf-8"))
    caps = [(c["id"], c.get("embedding_text") or c.get("intent", ""))
            for m in catalog for c in m["capabilities"]]
    qs = json.loads((ROOT / args.queryset).read_text(encoding="utf-8"))["queries"]

    print(f"임베딩 {len(caps)}개 capability + 질의 {len(qs)}개 ({MODEL}) …", file=sys.stderr)
    emb = TextEmbedding(model_name=MODEL)
    doc_vecs = [v.tolist() for v in emb.embed([t for _, t in caps])]
    q_vecs = [v.tolist() for v in emb.embed([q["q"] for q in qs])]

    def top_ids(qv, k):
        scored = sorted(((cos(qv, doc_vecs[i]), caps[i][0]) for i in range(len(caps))), reverse=True)
        return [cid for _, cid in scored[:k]]

    buckets = {"전체": qs, "KO": [q for q in qs if q["lang"] == "ko"], "EN": [q for q in qs if q["lang"] == "en"]}
    idx = {id(q): top_ids(q_vecs[i], args.k) for i, q in enumerate(qs)}

    print(f"\n의미 검색 정확도 (k={args.k}) · 크롤 레지스트리 {len(caps)}개")
    for label, subset in buckets.items():
        if not subset:
            continue
        t1 = sum(1 for q in subset if idx[id(q)] and idx[id(q)][0] in set(q["expected"]))
        tk = sum(1 for q in subset if set(idx[id(q)]) & set(q["expected"]))
        n = len(subset)
        print(f"  {label:5} top-1 {t1}/{n}={t1/n:.0%} · top-{args.k} {tk}/{n}={tk/n:.0%}")
    print("\n※ baseline(렉시컬) KO 0% 대비, 다국어 임베딩이 한국어 질의→영어 명령을 얼마나 잇는지가 핵심.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
