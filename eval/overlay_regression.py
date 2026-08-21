#!/usr/bin/env python3
"""overlay 회귀 테스트 — 수동 한국어 보강(enrich/overlay.json)이 실제 검색에서 유효한지 잠근다.

각 overlay 항목의 대표 한국어 키워드로 registry/catalog.json을 검색해,
해당 capability id가 top-K 안에 드는지 확인한다. crawl/ko_augment/search 변경이
KO 정밀 매칭을 조용히 퇴행시키면 여기서 잡힌다.

  python eval/overlay_regression.py            # 요약 + 통과/실패
  python eval/overlay_regression.py --k 5 --min 0.8

종료코드: 통과율 < --min 이면 1(CI 실패).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "registry"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import search as S  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=3, help="top-K 안에 정답 id가 들면 통과")
    ap.add_argument("--min", type=float, default=0.8, help="최소 통과율(미달 시 CI 실패)")
    args = ap.parse_args()

    cat_path = ROOT / "registry" / "catalog.json"
    if not cat_path.exists():  # 카탈로그는 gitignore(크롤 산출물) — 없으면 스킵(오프라인 CI 안전)
        print("overlay 회귀: catalog.json 없음 → 스킵 (먼저 `python pae.py crawl`)")
        return 0

    ov_path = ROOT / "enrich" / "overlay.json"
    raw = json.loads(ov_path.read_text(encoding="utf-8"))
    overlay = {k: v for k, v in raw.items() if not k.startswith("_")}

    caps = S.load_catalog()
    have = {c["id"] for c in caps}

    passed, failed, missing = [], [], []
    for cid, meta in overlay.items():
        if cid not in have:  # 크롤에 아직 없는 id(소스 브랜치 차이 등) → 스킵 집계
            missing.append(cid)
            continue
        kws = meta.get("keywords") or []
        if not kws:
            continue
        # 순수 한글 키워드 우선(영문 'git add'류는 gitlens와 겹침) → 그중 가장 변별력 있는(긴) 것
        ko = [w for w in kws if any("가" <= ch <= "힣" for ch in w) and " " in w]
        query = max(ko or kws, key=len)
        hits = S.search(query, caps, k=args.k)
        ids = [h["id"] for h in hits]
        (passed if cid in ids else failed).append((query, cid, ids[:args.k]))

    tested = len(passed) + len(failed)
    rate = (len(passed) / tested) if tested else 1.0

    print(f"overlay 회귀: {len(passed)}/{tested} 통과 (top-{args.k}), 통과율 {rate:.0%}")
    if missing:
        print(f"  · 카탈로그 미존재로 스킵 {len(missing)}개: {', '.join(missing[:5])}{'…' if len(missing) > 5 else ''}")
    for query, cid, ids in failed:
        print(f"  ✗ '{query}' → 기대 {cid} · 실제 {ids}")

    if rate < args.min:
        print(f"\n✗ 통과율 {rate:.0%} < 기준 {args.min:.0%}")
        return 1
    print(f"\n✓ 기준 {args.min:.0%} 충족")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
