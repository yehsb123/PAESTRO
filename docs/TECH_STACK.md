# PAESTRO 기술 스택

> 원칙: **엔진은 Python 사이드카, 확장은 얇은 TS 클라이언트.** 임베딩/벡터 생태계는 Python이 강하고, 사용자 접점은 VS Code(=TS)라서 둘을 분리하고 localhost로 잇는다.

## 레이어별 스택

| 레이어 | 기술 | 이유 |
|---|---|---|
| 인터페이스 | **TypeScript + VS Code Extension API** | 마켓플레이스 배포 단위. `vscode.extensions.all`로 타 확장 command를 런타임에 열람, `commands.executeCommand`로 실행 |
| 엔진 사이드카 | **Python 3.11+ · FastAPI · uvicorn** | 임베딩/Chroma가 Python 우선. 확장이 자식 프로세스로 스폰해 HTTP 호출 |
| 지식/색인 | **ChromaDB** (PersistentClient, cosine) | 셀프호스팅·로컬 친화·메타필터. 규모 커지면 인터페이스 유지한 채 pgvector/Milvus로 교체 |
| 임베딩 | **fastembed** + `paraphrase-multilingual-mpnet-base-v2` | ONNX 기반(torch 불필요). **다국어**(768dim). 검증: "git 로그 그래프"→git-graph(0.097), "파이썬 인터프리터 선택"→python.setInterpreter, "컨테이너 삭제"→irreversible. 완고한 음차어(린트)는 #2 LLM 문장형 보강으로 보완 |
| 오케스트레이터 LLM | **Anthropic SDK (Claude)** | 요구 분해·도구 선택·매니페스트 LLM 보강. BYO API 키 |
| 어댑터 | Node(vscode) · `@modelcontextprotocol/sdk`(mcp) · OpenAPI 파서(rest) | 소스별 정규화 → 공통 매니페스트 |

## 컴포넌트 상세

### 확장 (`extension/`, TypeScript)
- 빌드: **esbuild** (번들) · 패키징: **@vscode/vsce**
- 역할: ①설치된 확장에서 capability 수집 → 엔진 `/index` ②자연어 입력 → 엔진 `/retrieve` → 후보 QuickPick → `executeCommand` 실행(+irreversible 승인)

### 엔진 (`engine/`, Python)
- `POST /index` capability 배열 색인 · `POST /retrieve` 의미 검색 · `GET /health`
- e5 계열은 `passage:`/`query:` 접두사로 품질 향상 (구현 반영)

### 오케스트레이터 LLM — Claude 역할 분담
| 작업 | 모델 |
|---|---|
| 복잡한 요구 분해 · 매니페스트 LLM 보강(when_to_use·args_schema) | `claude-opus-4-8` |
| 일반 오케스트레이션(Plan/Execute) | `claude-sonnet-5` |
| 경량 라우팅 · 분류 · 재랭킹 | `claude-haiku-4-5` |

## 통신

```
[VS Code 확장 (TS)]  --HTTP 127.0.0.1:8756-->  [엔진 사이드카 (Python/FastAPI)]
     확장이 사이드카를 자식 프로세스로 스폰 · 로컬 전용(외부 노출 없음)               |
                                                                          [ChromaDB (.chroma)]
```

## 로컬 실행 순서

```bash
# 1) 엔진
cd engine && python -m venv .venv
.venv\Scripts\activate           # (mac/linux: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8756

# 2) 확장
cd extension && npm install && npm run build
# VS Code에서 F5 (Extension Development Host)

# 3) 어댑터 PoC (엔진 없이도 동작 — 뼈대 카탈로그 생성)
node tools/scan.js
```

## 디렉토리 구조

```
schemas/    capability-manifest.schema.json   # 계약 (JSON Schema)
examples/   vscode.eslint.manifest.json       # 정규화 예시
tools/      scan.js                           # VS Code 어댑터 PoC (parse 단계)
extension/  src/extension.ts …                # VS Code 확장 (인터페이스)
engine/     app.py, requirements.txt          # Python 사이드카 (색인·검색)
docs/       TECH_STACK.md                      # 본 문서
```
