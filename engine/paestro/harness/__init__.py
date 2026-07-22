"""[5] 하네스·안전 — 실행 규율.

- gate.py     side_effects 판단: read_only/reversible → 자동, irreversible → 사람 승인 요구
- retry.py    실패 재시도·폴백
- policy.py   교체 가능한 하네스 슬롯 (OSS 편입, 예: Ponytail)
오케스트레이터의 Execute 단계가 반드시 이 게이트를 경유한다.
"""
