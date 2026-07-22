"""[3] 임베딩 — fastembed 다국어 모델.

paraphrase-multilingual-MiniLM-L12-v2: 경량 다국어(한/영 포함 50+ 언어).
한국어 질의로 영어 title capability를 찾는 것이 목표(PoC의 KO↔EN 단절 해결).
(e5 계열과 달리 passage:/query: 접두사 불필요.)
"""
from __future__ import annotations

from fastembed import TextEmbedding

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_embedder = TextEmbedding(model_name=MODEL)


def _embed(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _embedder.embed(texts)]


def embed_passages(texts: list[str]) -> list[list[float]]:
    return _embed(texts)


def embed_query(text: str) -> list[float]:
    return _embed([text])[0]
