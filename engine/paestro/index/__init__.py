"""[3] 지식 — capability 색인·검색.

Chroma PersistentClient + fastembed 다국어 임베딩(e5-small).
- store.py     Chroma 컬렉션 래퍼 (upsert / query / count)
- embedding.py 임베딩 함수 (passage:/query: 접두사)
- reindex.py   플러그인 버전 diff 재색인 (ScaleMCP 방식)
현재는 app.py에 인라인 → 이리로 이관 예정.
"""
