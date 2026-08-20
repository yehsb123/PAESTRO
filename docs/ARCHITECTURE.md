# PAESTRO 파일 구조 (목표 트리)

6개 설계 노드(depth 1)에 디렉토리를 매핑한다. `✓` = 이미 존재, `·` = 뼈대만, `☐` = 예정.

```
PAESTRO/
├─ README.md                              ✓  프로젝트 소개 (계약 오너)
├─ .gitignore                             ✓
│
├─ schemas/                               ✓  [계약] 모든 어댑터의 출력 계약
│   └─ capability-manifest.schema.json    ✓
├─ examples/                              ✓  [계약] 정규화 완성 예시
│   └─ vscode.eslint.manifest.json        ✓
│
├─ docs/
│   ├─ TECH_STACK.md                      ✓  기술 스택
│   └─ ARCHITECTURE.md                    ✓  본 문서 (파일 구조 맵)
│
├─ extension/                             ✓  [1. 인터페이스] TS VS Code 확장
│   ├─ package.json / tsconfig / .vscodeignore  ✓
│   └─ src/
│       ├─ extension.ts                   ✓  진입점 (activate, 명령 등록)
│       ├─ engineClient.ts                ✓  엔진 HTTP 클라이언트 (index·retrieve·orchestrate)
│       └─ (UI는 extension.ts)            ✓  입력·번호메뉴·승인 다이얼로그·orchestrate
│
├─ engine/                                ✓  [엔진 사이드카] Python/FastAPI
│   ├─ app.py                             ✓  FastAPI 진입점 (현재 색인·검색 인라인)
│   ├─ requirements.txt                   ✓
│   └─ paestro/                           ·  파이썬 패키지 (app.py 로직이 이리로 이관)
│       ├─ index/                         ✓  [3. 지식] store.py·embedding.py (리랭커 예정)
│       ├─ orchestrator/                  ✓  [4] pipeline.py 멀티스텝(분해→검색→계획) + LLM planner 폴백
│       ├─ harness/                       ✓  [5] gate.py side_effects 승인 게이트
│       ├─ adapters/                      ·  [2. 어댑터] enrich.py(결정적: side_effects+한국어) ✓ / rest·mcp·cli·LLM보강 예정
│       └─ llm/                           ·  Claude 클라이언트
│
├─ tools/
│   └─ scan.js                            ✓  VS Code 어댑터 PoC (parse, 오프라인)
│
└─ registry/                              ·  [6. 거버넌스] 팀 공유 레지스트리 (뼈대 확립)
```

## 노드 ↔ 디렉토리 매핑

| # | Depth 1 | 위치 |
|---|---|---|
| 1 | 인터페이스 | `extension/` |
| 2 | 어댑터 | `tools/scan.js`(parse PoC) + `engine/paestro/adapters/`(정규화·보강) |
| 3 | 지식 | `engine/paestro/index/` |
| 4 | 오케스트레이터 | `engine/paestro/orchestrator/` |
| 5 | 하네스·안전 | `engine/paestro/harness/` |
| 6 | 거버넌스·운영 | `registry/` |

## 언어 경계

- **TS (extension)**: 사용자 접점, VS Code API로 확장 command 열람·실행.
- **Python (engine)**: 임베딩·Chroma·오케스트레이션·LLM 보강 — 무거운 로직 전부.
- 둘은 `127.0.0.1` HTTP로만 통신. VS Code adapter의 parse는 확장(런타임)과 `tools/scan.js`(오프라인)가 공유하는 계약.
