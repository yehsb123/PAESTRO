#!/usr/bin/env python3
"""레지스트리 → 엔진 색인 레코드 변환 (오프라인 레지스트리 ↔ 런타임 엔진의 다리).

nested catalog(플러그인별)을 엔진 /index 가 먹는 flat capability 레코드로 펴서 저장한다.
엔진이 떠 있으면 --post 로 바로 색인까지.

flat 레코드: { id, plugin, runtime, intent, embedding_text, side_effects, invocation }

실행
  python registry/to_index.py                              # index_records.json 생성만
  python registry/to_index.py --post http://127.0.0.1:8756 # 엔진에 색인까지
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
FIELDS = ("id", "intent", "embedding_text", "side_effects", "invocation")


def flatten(catalog: list[dict]) -> list[dict]:
    recs = []
    for m in catalog:
        pid = m["plugin"]["id"]
        runtime = m["plugin"].get("runtime", "vscode")
        for c in m["capabilities"]:
            rec = {k: c.get(k) for k in FIELDS}
            rec["plugin"] = pid
            rec["runtime"] = runtime
            if not rec.get("embedding_text"):
                rec["embedding_text"] = rec.get("intent", "")
            recs.append(rec)
    return recs


def post_index(engine: str, records: list[dict], batch: int = 200) -> None:
    for i in range(0, len(records), batch):
        chunk = records[i : i + batch]
        body = json.dumps({"capabilities": chunk}).encode("utf-8")
        req = urllib.request.Request(f"{engine.rstrip('/')}/index", data=body,
                                     headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            res = json.loads(r.read())
        print(f"  색인 {min(i + batch, len(records))}/{len(records)} · {res}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="registry/catalog.json")
    ap.add_argument("--out", default="registry/index_records.json")
    ap.add_argument("--post", help="엔진 URL로 바로 색인 (예: http://127.0.0.1:8756)")
    args = ap.parse_args()

    cat_path = ROOT / args.catalog
    if not cat_path.exists():
        cat_path = ROOT / "registry/catalog.sample.json"
    catalog = json.loads(cat_path.read_text(encoding="utf-8"))
    records = flatten(catalog)

    out = ROOT / args.out
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"flat 레코드 {len(records)}개 → {out} ({out.stat().st_size // 1024} KB)")

    if args.post:
        try:
            post_index(args.post, records)
            print("엔진 색인 완료.")
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            print(f"엔진 색인 실패({e}) — 엔진(/index)이 떠 있는지 확인. 파일은 생성됨.", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
