#!/usr/bin/env python3
"""엔진측 overlay KO 정밀도 하네스 — 실행 중인 엔진 /retrieve로 실측.

오프라인 회귀(eval/overlay_regression.py, search.py 기반)와 달리 **실제 엔진**
(mpnet + Chroma 하이브리드 리콜)의 런타임 정밀도를 잰다. enrich/overlay.json의
34개 고가치 capability를 대표 한글 키워드로 검색해 정답 id가 top-K에 드는지 확인.

전제: 엔진이 떠 있어야 함 → `cd engine && uvicorn app:app --port 8756`
CI에는 넣지 않는다(모델·엔진 기동 필요). 하이브리드 리콜 튜닝의 실측 도구.

  python eval/engine_overlay_eval.py                 # top-3, 127.0.0.1:8756
  python eval/engine_overlay_eval.py --k 1 --base http://127.0.0.1:8756
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent


def post(base: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def pick_query(keywords: list[str]) -> str:
    # 순수 한글 최장 키워드 우선(영문 'git add'류는 gitlens와 겹침) — 회귀와 동일 규칙
    ko = [w for w in keywords if any("가" <= ch <= "힣" for ch in w) and " " in w]
    return max(ko or keywords, key=len)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--base", default="http://127.0.0.1:8756")
    args = ap.parse_args()

    try:
        urllib.request.urlopen(args.base + "/health", timeout=5)
    except (urllib.error.URLError, TimeoutError):
        print(f"✗ 엔진에 연결 불가: {args.base} — `cd engine && uvicorn app:app --port 8756` 먼저 실행")
        return 2

    raw = json.loads((ROOT / "enrich" / "overlay.json").read_text(encoding="utf-8"))
    overlay = {k: v for k, v in raw.items() if not k.startswith("_")}

    passed, failed = [], []
    for cid, meta in overlay.items():
        kws = meta.get("keywords") or []
        if not kws:
            continue
        q = pick_query(kws)
        ids = [h["id"] for h in post(args.base, "/retrieve", {"query": q, "k": args.k})["hits"]]
        (passed if cid in ids else failed).append((q, cid, ids))

    tested = len(passed) + len(failed)
    print(f"엔진 overlay 정밀도: {len(passed)}/{tested} (top-{args.k}) = {len(passed)/tested:.0%}")
    for q, cid, ids in failed:
        print(f"  ✗ '{q}' → 기대 {cid} · 실제 {ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
