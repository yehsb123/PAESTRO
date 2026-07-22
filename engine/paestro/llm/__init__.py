"""Claude 클라이언트 — 오케스트레이션·보강용 LLM 접근.

Anthropic SDK 래퍼. BYO API 키(env: ANTHROPIC_API_KEY).
역할별 모델(TECH_STACK.md):
- claude-opus-4-8    복잡한 요구 분해 · 매니페스트 LLM 보강
- claude-sonnet-5    일반 오케스트레이션
- claude-haiku-4-5   경량 라우팅 · 분류 · 재랭킹
"""
