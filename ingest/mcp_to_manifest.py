#!/usr/bin/env python3
"""MCP 서버 tool 목록 → PAESTRO Capability 매니페스트 (오프라인 인제스트, 의존성 0).

MCP `tools/list` 응답(JSON)을 받아 tool 하나를 capability 하나로 정규화한다.
side_effects는 MCP annotations 힌트 우선(readOnlyHint/destructiveHint), 없으면 이름 기반 폴백.

입력  tools/list 결과 — {"tools":[...]} 또는 [...] 모두 허용. 각 tool: {name, description, inputSchema, annotations?}
실행
  python ingest/mcp_to_manifest.py --in ingest/sample_mcp.json --server github --out ingest/out
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_DESTRUCTIVE = re.compile(r"\b(delete|remove|drop|destroy|reset|revert|purge|deploy|publish)\b", re.I)
_READONLY = re.compile(r"\b(get|list|read|search|find|query|fetch|show|view)\b", re.I)


def side_effects(tool: dict) -> str:
    ann = tool.get("annotations") or {}
    if ann.get("readOnlyHint"):
        return "read_only"
    if ann.get("destructiveHint"):
        return "irreversible"
    if "readOnlyHint" in ann or "destructiveHint" in ann:
        return "reversible"  # 힌트 명시됐고 위 둘 다 아님
    name = tool.get("name", "")
    if _DESTRUCTIVE.search(name):
        return "irreversible"
    if _READONLY.search(name):
        return "read_only"
    return "reversible"


def convert(tools: list[dict], server: str) -> dict:
    caps = []
    for t in tools:
        name = t.get("name")
        if not name:
            continue
        desc = t.get("description") or name
        schema = t.get("inputSchema") or {}
        props = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        inputs = {
            k: {"type": (v or {}).get("type", "string"), "required": k in required,
                "description": (v or {}).get("description", "")}
            for k, v in props.items()
        }
        kw = sorted({*re.split(r"[\s_./-]+", name.lower())} - {""})
        caps.append({
            "id": f"mcp.{server}.{re.sub(r'[^A-Za-z0-9._-]', '_', name)}",
            "intent": desc.split("\n")[0][:200],
            "keywords": kw,
            "when_to_use": "",
            "when_not_to_use": "",
            "invocation": {"type": "mcp", "server": server, "tool": name},
            "inputs": inputs,
            "side_effects": side_effects(t),
            "embedding_text": f"{desc} {name}".strip(),
        })
    return {
        "plugin": {
            "id": f"mcp.{server}",
            "displayName": server,
            "version": "0",
            "runtime": "mcp",
            "source": {"kind": "mcp-manifest"},
            "auth": {"type": "none"},
            "sandbox": "recommended",
        },
        "capabilities": caps,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--server", required=True, help="MCP 서버 이름 (예: github)")
    ap.add_argument("--out", default="ingest/out")
    args = ap.parse_args()

    data = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    tools = data.get("tools", data) if isinstance(data, dict) else data
    manifest = convert(tools, args.server)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"mcp.{args.server}.manifest.json"
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    caps = manifest["capabilities"]
    se = {}
    for c in caps:
        se[c["side_effects"]] = se.get(c["side_effects"], 0) + 1
    print(f"→ {out_path} · capability {len(caps)}개 · side_effects {se}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
