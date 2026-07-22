"""PAESTRO 엔진 파이썬 패키지.

app.py(FastAPI 진입점)의 인라인 로직이 하위 모듈로 점진 이관된다:
  index/         [3] 색인·검색 (Chroma + 다국어 임베딩)
  orchestrator/  [4] Plan → Retrieve → Assemble → Execute → Verify
  harness/       [5] side_effects 승인 게이트·재시도·정책
  adapters/      [2] rest·mcp·cli 소스 정규화 + LLM 보강
  llm/           Claude 클라이언트
"""

__version__ = "0.1.0"
