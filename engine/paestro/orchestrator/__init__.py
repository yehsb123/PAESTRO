"""[4] 오케스트레이터 — 요구를 실행으로. PAESTRO의 척추(spine).

파이프라인: Plan → Retrieve → Assemble → Execute → Verify (실패 시 재검색 루프).
- planner.py    요구를 검증 가능한 하위 작업으로 분해 (Claude)
- retriever.py  하위 작업별 index 의미검색 (JIT, top-k → 리랭크)
- executor.py   invocation 실행 (vscode/rest/mcp/cli), harness 경유
- pipeline.py   위 단계 조립 + Verify 루프 + 다중 도구 체이닝

이 모듈의 입출력 계약이 나머지 노드(2·3·5·1)의 규격을 강제한다.
"""
