"""[2] 어댑터 — 소스를 표준 매니페스트로 정규화.

출력 계약 = schemas/capability-manifest.schema.json.
- base.py    어댑터 인터페이스 (SPI)
- rest.py    OpenAPI → 매니페스트
- mcp.py     MCP tool 목록 → 매니페스트
- cli.py     CLI/스크립트 → 매니페스트
- enrich.py  LLM 보강 패스: when_to_use·keywords·args_schema·side_effects 채움 (★검색 품질의 관건)

VS Code adapter의 parse 단계는 확장(TS 런타임)과 tools/scan.js가 담당 → 여기선 enrich만 관여.
"""
