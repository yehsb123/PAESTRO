#!/usr/bin/env python3
"""PAESTRO 레지스트리 크롤러 — GitHub/웹의 실제 오픈소스 → 통합 capability 레지스트리.

registry/sources.json의 소스를 긁어(각 소스 → 알맞은 ingest 변환기) 매니페스트로 정규화하고,
safety로 side_effects를 통일 분류한 뒤 계약 검증하여 registry/catalog.json으로 합친다.

- VS Code 확장: GitHub raw package.json(+ package.nls.json) → contributes.commands
- OpenAPI: 스펙 URL → 오퍼레이션
- 실패한 소스는 건너뛴다(네트워크/브랜치 차이). 의존성 0(stdlib).

실행
  python registry/crawl.py                 # sources.json 전체
  python registry/crawl.py --limit 3       # 앞 3개 vscode만(빠른 확인)
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("ingest", "schemas", "enrich"):
    sys.path.insert(0, str(ROOT / sub))

import openapi_to_manifest as oa  # noqa: E402
import vscode_pkg_to_manifest as vs  # noqa: E402
from ko_augment import augment as ko_augment  # noqa: E402
from safety import classify_side_effects  # noqa: E402
from validate import validate_manifest  # noqa: E402

UA = {"User-Agent": "paestro-registry-crawler/0.1"}


def fetch_json(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_vscode(repo: str):
    """main/master 순으로 package.json(+nls) 시도."""
    for branch in ("main", "master"):
        base = f"https://raw.githubusercontent.com/{repo}/{branch}"
        try:
            pkg = fetch_json(f"{base}/package.json")
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
            continue
        nls = {}
        try:
            nls = fetch_json(f"{base}/package.nls.json")
        except Exception:
            pass
        return pkg, nls
    return None, None


def enrich_safety(manifest: dict) -> dict:
    for c in manifest["capabilities"]:
        c["side_effects"] = classify_side_effects(c.get("embedding_text") or c.get("intent", ""))
        ko_augment(c)  # 한국어 동의어 주입 → KO 검색 개선
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="vscode 소스 앞 N개만")
    ap.add_argument("--out", default="registry/catalog.json")
    args = ap.parse_args()

    sources = json.loads((ROOT / "registry" / "sources.json").read_text(encoding="utf-8"))
    manifests, rows = [], []

    vlist = sources.get("vscode", [])
    if args.limit:
        vlist = vlist[: args.limit]
    for s in vlist:
        pkg, nls = fetch_vscode(s["repo"])
        if not pkg:
            rows.append((f"vscode:{s['name']}", "FETCH FAIL", 0))
            continue
        m = enrich_safety(vs.convert(pkg, nls, plugin=f"vscode.{s['name']}"))
        ok = not validate_manifest(m)
        rows.append((f"vscode:{s['name']}", "OK" if ok else "INVALID", len(m["capabilities"])))
        if ok:
            manifests.append(m)

    for s in sources.get("openapi", []):
        try:
            spec = fetch_json(s["url"])
            m = enrich_safety(oa.convert(spec, s["name"], ""))
            ok = not validate_manifest(m)
            rows.append((f"openapi:{s['name']}", "OK" if ok else "INVALID", len(m["capabilities"])))
            if ok:
                manifests.append(m)
        except Exception as e:
            rows.append((f"openapi:{s['name']}", f"FAIL {type(e).__name__}", 0))

    all_caps = [c for m in manifests for c in m["capabilities"]]
    out = ROOT / args.out
    out.write_text(json.dumps(manifests, ensure_ascii=False, indent=2), encoding="utf-8")

    print("소스                     상태          caps")
    print("-" * 46)
    for name, status, n in rows:
        print(f"{name:24} {status:12} {n:5}")
    se: dict[str, int] = {}
    for c in all_caps:
        se[c["side_effects"]] = se.get(c["side_effects"], 0) + 1
    print("-" * 46)
    print(f"플러그인 {len(manifests)}개 · capability {len(all_caps)}개 · side_effects {se}")
    print(f"→ {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
