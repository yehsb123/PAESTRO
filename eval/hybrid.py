#!/usr/bin/env python3
"""하이브리드 검색 평가 — dense(임베딩) + lexical(단어일치)를 RRF로 융합 (엔진 방식 재현).

크롤 레지스트리 위에서 dense-only가 약한 KO를, lexical(한국어 주입 덕분)이 건져
hybrid가 얼마나 오르는지 실측한다. 엔진이 hybrid(dense+lexical 재랭크)를 쓰는 이유의 증명.

준비:  python -m pip install fastembed
실행:  python eval/hybrid.py --k 3
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def toks(s: str):
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s or "")
    return [t for t in re.split(r"[\s._:/!-]+", s.lower()) if len(t) > 1]


def cos(a, b):
    s = d1 = d2 = 0.0
    for x, y in zip(a, b):
        s += x * y; d1 += x * x; d2 += y * y
    return s / ((d1 ** 0.5) * (d2 ** 0.5) + 1e-9)


def rrf(rank_lists, weights=None, k=60):
    weights = weights or [1.0] * len(rank_lists)
    score: dict = {}
    for w, ranks in zip(weights, rank_lists):
        for r, cid in enumerate(ranks):
            score[cid] = score.get(cid, 0.0) + w / (k + r)
    return [cid for cid, _ in sorted(score.items(), key=lambda x: -x[1])]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="registry/catalog.json")
    ap.add_argument("--queryset", default="eval/queryset.registry.json")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--pool", type=int, default=50, help="각 랭커 상위 pool개만 융합")
    ap.add_argument("--w-lex", type=float, default=2.0, help="hybrid에서 lexical 가중")
    ap.add_argument("--w-dense", type=float, default=0.5,
                    help="hybrid에서 dense 가중(약한 dense는 낮게; 강한 mpnet/bge-m3면 올려라)")
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
    ids, texts = [], []
    for m in catalog:
        for c in m["capabilities"]:
            ids.append(c["id"]); texts.append(c.get("embedding_text") or c.get("intent", ""))
    doc_tok = [set(toks(t)) for t in texts]
    qs = json.loads((ROOT / args.queryset).read_text(encoding="utf-8"))["queries"]

    print(f"임베딩 {len(ids)}개 ({MODEL}) …", file=sys.stderr)
    emb = TextEmbedding(model_name=MODEL)
    dv = [v.tolist() for v in emb.embed(texts)]
    qv = [v.tolist() for v in emb.embed([q["q"] for q in qs])]

    def dense_rank(i):
        return [ids[j] for _, j in sorted(((cos(qv[i], dv[j]), j) for j in range(len(ids))), reverse=True)[:args.pool]]

    def lex_rank(q):
        qt = set(toks(q))
        sc = [(len(qt & doc_tok[j]), ids[j]) for j in range(len(ids))]
        sc = [(s, cid) for s, cid in sc if s]
        return [cid for _, cid in sorted(sc, reverse=True)[:args.pool]]

    def evalset(subset, ranker):
        t1 = tk = 0
        for i, q in enumerate(qs):
            if q not in subset:
                continue
            r = ranker(i, q)[:args.k]
            exp = set(q["expected"])
            t1 += bool(r) and r[0] in exp
            tk += bool(set(r) & exp)
        n = len(subset) or 1
        return t1, tk, n

    rankers = {
        "dense": lambda i, q: dense_rank(i),
        "lexical": lambda i, q: lex_rank(q["q"]),
        "hybrid": lambda i, q: rrf([dense_rank(i), lex_rank(q["q"])], weights=[args.w_dense, args.w_lex]),
    }
    buckets = {"전체": qs, "KO": [q for q in qs if q["lang"] == "ko"], "EN": [q for q in qs if q["lang"] == "en"]}

    print(f"\n크롤 레지스트리 {len(ids)}개 · k={args.k}\n")
    print(f"{'':9}" + "".join(f"{lbl:>10}" for lbl in buckets))
    for rn, rk in rankers.items():
        cells = []
        for _, subset in buckets.items():
            t1, tk, n = evalset(subset, rk)
            cells.append(f"{tk}/{n}={tk/n:.0%}")
        print(f"{rn:9}" + "".join(f"{c:>10}" for c in cells) + "   (top-%d)" % args.k)
    print(f"\n※ 각 셀 = top-{args.k} 정확도. 기본 가중 = lexical {args.w_lex} : dense {args.w_dense}.")
    print("   발견: 약한 dense(MiniLM)는 동등 융합 시 KO 손해 → lexical 우세 가중으로 hybrid≥lexical 달성.")
    print("   강한 dense(엔진 mpnet/bge-m3) 도입 시 --w-dense를 올려 semantic recall을 더 살릴 것.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
