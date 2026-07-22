#!/usr/bin/env python3
"""OpenAPI(REST) 스펙 → PAESTRO Capability 매니페스트 (오프라인 인제스트, 의존성 0).

각 오퍼레이션(path+method)을 capability 하나로 정규화한다. 실행은 엔진(runtime)이 담당하고
이 스크립트는 '카탈로그 생산'만 한다(=scan.js의 REST판). 출력은 schemas/capability-manifest 계약 준수.

side_effects는 HTTP 메서드로 1차 판정(GET=read_only, DELETE=irreversible, 그 외=reversible).

실행
  python ingest/openapi_to_manifest.py --in ingest/sample_openapi.json --plugin petstore --out ingest/out
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

METHOD_SIDE = {
    "get": "read_only", "head": "read_only", "options": "read_only",
    "post": "reversible", "put": "reversible", "patch": "reversible",
    "delete": "irreversible",
}


def sanitize(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", s).strip("_")


def op_id(method: str, path: str, op: dict) -> str:
    if op.get("operationId"):
        return sanitize(op["operationId"])
    return sanitize(f"{method}_{path}")


def convert(spec: dict, plugin: str, base_url: str) -> dict:
    if not base_url:
        servers = spec.get("servers") or []
        base_url = servers[0].get("url", "") if servers else ""
    caps = []
    for path, item in (spec.get("paths") or {}).items():
        for method, op in item.items():
            m = method.lower()
            if m not in METHOD_SIDE or not isinstance(op, dict):
                continue
            oid = op_id(m, path, op)
            intent = op.get("summary") or op.get("description") or f"{method.upper()} {path}"
            tags = [t for t in (op.get("tags") or []) if isinstance(t, str)]
            inputs = {}
            for p in op.get("parameters", []) or []:
                if p.get("name"):
                    inputs[p["name"]] = {
                        "type": (p.get("schema") or {}).get("type", "string"),
                        "required": bool(p.get("required")),
                        "description": p.get("description", ""),
                    }
            kw = sorted({*(t.lower() for t in tags), *re.split(r"[\s_./{}-]+", oid.lower())} - {""})
            caps.append({
                "id": f"rest.{plugin}.{oid}",
                "intent": intent,
                "keywords": kw,
                "when_to_use": "",
                "when_not_to_use": "",
                "invocation": {"type": "rest", "method": method.upper(), "path": path, "base_url": base_url},
                "inputs": inputs,
                "side_effects": METHOD_SIDE[m],
                "embedding_text": " ".join(x for x in [intent, " ".join(tags), oid] if x),
            })
    return {
        "plugin": {
            "id": f"rest.{plugin}",
            "displayName": plugin,
            "version": str((spec.get("info") or {}).get("version", "0")),
            "runtime": "rest",
            "source": {"kind": "openapi"},
            "auth": {"type": "bearer"},
            "sandbox": "required",
        },
        "capabilities": caps,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--plugin", required=True, help="플러그인 이름 (예: stripe)")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--out", default="ingest/out")
    args = ap.parse_args()

    spec = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    manifest = convert(spec, args.plugin, args.base_url)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"rest.{args.plugin}.manifest.json"
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    caps = manifest["capabilities"]
    se = {}
    for c in caps:
        se[c["side_effects"]] = se.get(c["side_effects"], 0) + 1
    print(f"→ {out_path} · capability {len(caps)}개 · side_effects {se}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
