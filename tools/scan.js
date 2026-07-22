#!/usr/bin/env node
/*
 * PAESTRO VS Code 어댑터 — Phase 0 PoC (parse 단계)
 *
 * 설치된 VS Code 확장의 package.json → contributes.commands 를 긁어
 * schemas/capability-manifest.schema.json 형식의 뼈대 매니페스트로 정규화한다.
 *
 * 이건 어댑터 2단계 중 1단계(parse)만 수행한다.
 *   1) parse       ← 여기: id·command·title 뼈대 추출 (본 스크립트)
 *   2) llm_enrich  ← 다음: when_to_use·keywords·side_effects·args_schema 를 LLM으로 보강
 *
 * 의존성 0 (순수 Node). 생성물 catalog.json 은 .gitignore 처리됨.
 */
const fs = require("fs");
const path = require("path");

const EXT_DIR = path.join(process.env.USERPROFILE || process.env.HOME, ".vscode", "extensions");
const OUT = path.join(__dirname, "..", "catalog.json");

// %key% (i18n) → package.nls.json 값으로 치환
function loadNls(dir) {
  const p = path.join(dir, "package.nls.json");
  if (!fs.existsSync(p)) return {};
  try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch { return {}; }
}
const nlsResolve = (s, nls) =>
  typeof s === "string" ? s.replace(/^%(.+)%$/, (_, k) => (nls[k] != null ? nls[k] : s)) : s;

// 확장 하나 → 매니페스트 { plugin, capabilities[] } (스키마 준수)
function toManifest(root, pkg) {
  const nls = loadNls(root);
  const shortName = String(pkg.name || "").replace(/^vscode-/, "");
  const pluginId = `vscode.${shortName || pkg.name}`;
  const commands = (pkg.contributes && pkg.contributes.commands) || [];

  const capabilities = commands
    .filter((c) => c && c.command)
    .map((c) => {
      const title = nlsResolve(c.title, nls);
      const category = nlsResolve(c.category, nls);
      return {
        id: `vscode.${c.command}`,
        intent: title || c.command,
        keywords: [category].filter(Boolean),
        when_to_use: "",                 // ← llm_enrich 단계에서 채움
        when_not_to_use: "",
        invocation: { type: "vscode", command: c.command, args_schema: {} },
        inputs: {},
        outputs: {},
        side_effects: "read_only",       // ← 보수적 기본값. 파괴적 명령은 enrich 단계에서 재분류
        cost_hint: "local",
        depends_on: [],
        examples: [],
        embedding_text: [title, category, c.command].filter(Boolean).join(" "),
      };
    });

  if (!capabilities.length) return null;
  return {
    plugin: {
      id: pluginId,
      displayName: pkg.displayName || pkg.name,
      version: pkg.version || "0.0.0",
      runtime: "vscode",
      source: { kind: "marketplace", uri: `${pkg.publisher || "?"}.${pkg.name}`, extractedBy: "vscode-adapter@0.1-poc" },
      auth: { type: "none" },
      sandbox: "none",
    },
    capabilities,
  };
}

function scan() {
  const manifests = [];
  const stats = { extensions: 0, withCommands: 0, capabilities: 0 };
  if (!fs.existsSync(EXT_DIR)) { console.error("확장 폴더 없음:", EXT_DIR); return { manifests, stats }; }

  for (const name of fs.readdirSync(EXT_DIR)) {
    if (name.startsWith(".")) continue;
    const root = path.join(EXT_DIR, name);
    const pkgPath = path.join(root, "package.json");
    if (!fs.statSync(root).isDirectory() || !fs.existsSync(pkgPath)) continue;
    let pkg;
    try { pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8")); } catch { continue; }
    stats.extensions++;
    const m = toManifest(root, pkg);
    if (m) { manifests.push(m); stats.withCommands++; stats.capabilities += m.capabilities.length; }
  }
  return { manifests, stats };
}

// 렉시컬 랭킹 (임베딩 자리표시자 — engine 사이드카가 다국어 임베딩으로 대체)
function rank(query, manifests, k = 5) {
  const q = query.toLowerCase().split(/\s+/).filter(Boolean);
  const flat = manifests.flatMap((m) => m.capabilities.map((c) => ({ plugin: m.plugin.id, c })));
  return flat
    .map((x) => {
      const t = x.c.embedding_text.toLowerCase();
      let s = 0; for (const tok of q) if (t.includes(tok)) s += tok.length;
      return { ...x, s };
    })
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s)
    .slice(0, k);
}

const { manifests, stats } = scan();
fs.writeFileSync(OUT, JSON.stringify(manifests, null, 2));
console.log("═══ PAESTRO 카탈로그 스캔 (parse 단계) ═══");
console.log(`확장 ${stats.extensions}개 · 명령 보유 ${stats.withCommands}개 · capability ${stats.capabilities}개`);
console.log(`→ ${path.relative(process.cwd(), OUT)} 저장\n`);

for (const query of ["git 로그 그래프", "lint 자동 수정", "docker 컨테이너", "python 디버그"]) {
  console.log(`▶ "${query}"`);
  const hits = rank(query, manifests);
  if (!hits.length) console.log("   (매칭 없음)");
  else hits.forEach(({ plugin, c, s }, i) => console.log(`   ${i + 1}. [${plugin}] ${c.intent} → ${c.invocation.command} (${s})`));
  console.log();
}
