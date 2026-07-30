#!/usr/bin/env python3
"""PAESTRO 오프라인 파이프라인 데모 — 이질 소스 → 정규화 매니페스트 → 계약 검증.

REST(OpenAPI)·MCP·CLI 샘플을 각 인제스트 변환기로 매니페스트화하고, 전부 계약(schemas)을
통과하는지 확인한 뒤 합본 카탈로그를 만든다. "무엇이든 하나의 매니페스트로" 라는 오프라인
lane의 가치 제안을 한 번에 시연/스모크테스트한다. 의존성 0.

실행
  python demo/pipeline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("ingest", "schemas"):
    sys.path.insert(0, str(ROOT / sub))

import cli_to_manifest as cli  # noqa: E402
import mcp_to_manifest as mcp  # noqa: E402
import openapi_to_manifest as oa  # noqa: E402
from validate import validate_manifest  # noqa: E402


def build() -> list[tuple[str, dict]]:
    ig = ROOT / "ingest"
    openapi_spec = json.loads((ig / "sample_openapi.json").read_text(encoding="utf-8"))
    mcp_data = json.loads((ig / "sample_mcp.json").read_text(encoding="utf-8"))
    cli_help = (ig / "sample_cli_help.txt").read_text(encoding="utf-8")
    return [
        ("REST/OpenAPI", oa.convert(openapi_spec, "petstore", "")),
        ("MCP", mcp.convert(mcp_data.get("tools", mcp_data), "github")),
        ("CLI", cli.convert(cli.parse_subcommands(cli_help), "git", "git")),
    ]


def main() -> int:
    manifests = build()
    all_caps = []
    total_err = 0
    print("소스           런타임   caps  side_effects                     계약")
    print("-" * 74)
    for label, m in manifests:
        errs = validate_manifest(m)
        total_err += len(errs)
        caps = m["capabilities"]
        se: dict[str, int] = {}
        for c in caps:
            se[c["side_effects"]] = se.get(c["side_effects"], 0) + 1
        se_str = " ".join(f"{k}={v}" for k, v in sorted(se.items()))
        print(f"{label:14} {m['plugin']['runtime']:7} {len(caps):4}  {se_str:32} {'OK' if not errs else 'FAIL'}")
        all_caps.extend(caps)

    out_dir = ROOT / "demo" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "all_manifests.json").write_text(
        json.dumps([m for _, m in manifests], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    irr = sum(1 for c in all_caps if c["side_effects"] == "irreversible")
    print("-" * 74)
    print(f"합계 {len(all_caps)} capability · irreversible(승인게이트) {irr}개 · 계약오류 {total_err}건")
    print(f"→ {out_dir / 'all_manifests.json'}")
    return 1 if total_err else 0


if __name__ == "__main__":
    raise SystemExit(main())
