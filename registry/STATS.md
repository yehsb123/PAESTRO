# PAESTRO 레지스트리 스냅샷

크롤 결과 요약 (전체 `catalog.json`은 생성물이라 gitignore — 이 파일은 버전관리용 기록).

- **총 1954 capability · 35 소스 · 4 런타임**

## 런타임

| 런타임 | capability |
|---|---|
| vscode | 1228 |
| rest | 522 |
| cli | 149 |
| mcp | 55 |

## 안전 등급

| 등급 | 수 |
|---|---|
| read_only | 1473 |
| reversible | 343 |
| irreversible | 138 |

승인 게이트 대상(irreversible): **138**

## 소스별 (상위)

| 소스 | 런타임 | caps |
|---|---|---|
| vscode.gitlens | vscode | 914 |
| vscode.pr-github | vscode | 172 |
| mcp.registry | mcp | 55 |
| cli.docker | cli | 51 |
| cli.gh | cli | 38 |
| cli.kubectl | cli | 37 |
| rest.stripe | rest | 35 |
| rest.slack | rest | 35 |
| rest.digitalocean | rest | 35 |
| rest.github | rest | 35 |
| rest.box | rest | 35 |
| rest.sendgrid | rest | 35 |
| rest.asana | rest | 35 |
| rest.spotify | rest | 35 |
| rest.zoom | rest | 35 |
| rest.trello | rest | 35 |
| rest.bitbucket | rest | 35 |
| rest.gitlab | rest | 35 |
| rest.docusign | rest | 35 |
| rest.linode | rest | 35 |

> `python pae.py crawl`로 재생성 · `python pae.py stats`로 실시간 확인
