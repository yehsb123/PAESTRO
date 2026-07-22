# eval — 검색 정확도 평가 하네스

실행 중인 엔진(`/retrieve`)에 라벨된 질의셋을 던져 **top-1 / top-k 정확도 + MRR**을 측정한다.
"필요한 도구를 정확히 검색하는가"를 수치로 확인(RAG-MCP식). KO/EN 혼용으로 **다국어 임베딩 효과**를 본다.

## 실행

```bash
# 1) 엔진 실행 (engine/) + 카탈로그 색인 후
python eval/run_eval.py --engine http://127.0.0.1:8756 --k 3
python eval/run_eval.py --lang ko     # 한국어만
python eval/run_eval.py --lang en     # 영어만  → KO vs EN 격차 확인
```

- `eval/queryset.json` — KO/EN 질의 + 정답 capability id 라벨. **설치 카탈로그에 맞게 `expected`를 조정**할 것.
- 의존성 0(stdlib urllib). 엔진이 안 떠 있으면 안내 후 종료.

## 용도

- 임베딩 모델 교체(e5-small→large / bge-m3), 하이브리드 랭킹, 보강(enrich) 전/후를 **같은 잣대로 비교**.
- KO 정확도 ≪ EN 정확도면 다국어 임베딩/키워드 보강이 부족하다는 신호.
