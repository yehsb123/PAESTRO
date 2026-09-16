# eval — 검색 정확도 평가 하네스

실행 중인 엔진(`/retrieve`)에 라벨된 질의셋을 던져 **top-1 / top-k 정확도 + MRR**을 측정한다.
"필요한 도구를 정확히 검색하는가"를 수치로 확인(RAG-MCP식). KO/EN 혼용으로 **다국어 임베딩 효과**를 본다.

## 실행

```bash
# 1) 엔진 실행 (engine/) + 카탈로그 색인 후
python eval/run_eval.py --k 3          # 기본 = queryset.registry.json (크롤 레지스트리 정렬)
python eval/run_eval.py --lang ko      # 한국어만
python eval/run_eval.py --lang en      # 영어만  → KO vs EN 격차 확인
```

## 하네스 목록

| 파일 | 엔진 필요 | 무엇을 재는가 |
|---|---|---|
| `run_eval.py` | ✓ | top-1/top-3/MRR. 기본 queryset = `queryset.registry.json` |
| `engine_overlay_eval.py` | ✓ | overlay 34개 고가치 cap의 엔진측 KO 정밀도(현재 top-3 100%) |
| `consistency.py` | ✓ | 같은 질의 N회 반복 → 결과 결정성(서명 1종=완전 결정적) + 점수 변동 |
| `overlay_regression.py` | ✗ | overlay KO 매핑 오프라인 회귀(search.py, `pae.py check`에 포함) |
| `regression.py` | ✗ | fixture 기반 검색 회귀(CI 포함) |
| `baseline.py`·`semantic.py`·`hybrid.py` | ✗ | 오프라인 랭킹 방식 비교 |

```bash
python eval/engine_overlay_eval.py --k 3       # 엔진측 overlay KO 정밀도
python eval/consistency.py --runs 100 --k 3    # 100회 정합성(결정성) — 비결정적이면 exit 1
```

### queryset 두 종
- `queryset.registry.json` — **크롤 레지스트리(OSS)** 정답 id. `run_eval` 기본. 엔진(to_index 색인)과 정렬됨.
- `queryset.json` — 확장이 런타임에 수집하는 **VS Code 내장 command**(`vscode.git.clean` 등) 기대. 크롤 레지스트리엔 없으니 이 셋으론 채점하지 말 것(다른 카탈로그용).

- 엔진 필요 하네스는 **CI 제외**(모델·엔진 기동 필요). 의존성 0(stdlib urllib), 엔진 미기동 시 안내 후 종료.

## 용도

- 임베딩 모델 교체(mpnet→bge-m3 등), 하이브리드 리콜/랭킹, 보강(enrich) 전/후를 **같은 잣대로 비교**.
- KO 정확도 ≪ EN 정확도면 다국어 임베딩/키워드 보강이 부족하다는 신호.
- 리콜 재랭크를 손댔는데 `consistency.py` 서명이 갈라지면 → 검색이 비결정적이 된 것(부동소수 정렬 불안정 등) 신호.
