import * as vscode from "vscode";
import * as http from "node:http";
import * as https from "node:https";
import { URL } from "node:url";
import * as engine from "./engineClient";

// 최소 HTTP 클라이언트(node 빌트인). 본문은 2KB로 잘라 요약 표시용.
function httpRequest(
  method: string,
  urlStr: string,
  headers: Record<string, string>,
  body?: string
): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    let u: URL;
    try {
      u = new URL(urlStr);
    } catch {
      reject(new Error(`잘못된 URL: ${urlStr}`));
      return;
    }
    const mod = u.protocol === "http:" ? http : https;
    const req = mod.request(u, { method, headers }, (res) => {
      const chunks: Buffer[] = [];
      res.on("data", (d) => chunks.push(Buffer.from(d)));
      res.on("end", () =>
        resolve({ status: res.statusCode ?? 0, body: Buffer.concat(chunks).toString("utf8").slice(0, 2000) })
      );
    });
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

// [2] VS Code 어댑터 parse — 설치된 확장의 command 를 capability 로 수집(런타임).
function collectCapabilities(): Array<Record<string, unknown>> {
  const caps: Array<Record<string, unknown>> = [];
  for (const ext of vscode.extensions.all) {
    const pkg: any = ext.packageJSON;
    const commands = pkg?.contributes?.commands as Array<any> | undefined;
    if (!commands?.length) continue;
    const short = String(pkg.name || "").replace(/^vscode-/, "");
    const pluginId = `vscode.${short || pkg.name}`;
    for (const c of commands) {
      if (!c?.command) continue;
      const title: string = c.title ?? c.command;
      const category: string | undefined = c.category;
      caps.push({
        id: `vscode.${c.command}`,
        plugin: pluginId,
        runtime: "vscode",
        intent: title,
        side_effects: "read_only",
        invocation: { type: "vscode", command: c.command },
        embedding_text: [title, category, c.command].filter(Boolean).join(" "),
      });
    }
  }
  return caps;
}

async function reindex(): Promise<void> {
  if (!(await engine.health())) {
    vscode.window.showErrorMessage("PAESTRO: 엔진(127.0.0.1:8756)에 연결할 수 없습니다. 엔진을 먼저 실행하세요.");
    return;
  }
  const { indexed, total } = await engine.index(collectCapabilities());
  vscode.window.showInformationMessage(`PAESTRO: ${indexed}개 색인 (총 ${total})`);
}

type MenuItem = vscode.QuickPickItem & { hit?: engine.Hit };

// 실행 가능한 hit의 최소 형태(ask의 Hit·orchestrate의 Chosen 공용).
type Runnable = { id: string; intent?: string; invocation?: string };

type Exec =
  | { kind: "vscode"; command: string; args: unknown[] }
  | { kind: "cli"; argv: string[] }
  | { kind: "rest"; method: string; url: string }
  | { kind: "mcp"; server: string; tool: string }
  | { kind: "unknown"; runtime: string };

// invocation(JSON 문자열) → 런타임별 실행 계획. 파싱 실패 시 id 접두로 폴백.
function parseExec(hit: Runnable): Exec {
  try {
    const inv = JSON.parse(hit.invocation || "{}");
    if (inv.type === "vscode" && inv.command)
      return { kind: "vscode", command: inv.command, args: Array.isArray(inv.args) ? inv.args : [] };
    if (inv.type === "cli" && Array.isArray(inv.argv_template))
      return { kind: "cli", argv: inv.argv_template.map(String) };
    if (inv.type === "rest")
      return { kind: "rest", method: String(inv.method || "GET"), url: `${inv.base_url || ""}${inv.path || ""}` };
    if (inv.type === "mcp")
      return { kind: "mcp", server: String(inv.server || "?"), tool: String(inv.tool || "*") };
    if (inv.type && inv.type !== "vscode") return { kind: "unknown", runtime: String(inv.type) };
  } catch {
    /* 구형 데이터 등 → id 폴백 */
  }
  if (hit.id.startsWith("vscode.")) return { kind: "vscode", command: hit.id.replace(/^vscode\./, ""), args: [] };
  return { kind: "unknown", runtime: hit.id.split(".")[0] };
}

let paeTerminal: vscode.Terminal | undefined;
function cliTerminal(): vscode.Terminal {
  if (!paeTerminal || paeTerminal.exitStatus !== undefined) {
    paeTerminal = vscode.window.createTerminal("PAESTRO");
  }
  return paeTerminal;
}

// argv_template의 {placeholder} 를 사용자 입력으로 채운다(#2 인자 전달). 취소 시 null.
async function fillPlaceholders(argv: string[]): Promise<string[] | null> {
  const out: string[] = [];
  for (const tok of argv) {
    const m = tok.match(/^\{(.+)\}$/);
    if (!m) { out.push(tok); continue; }
    const val = await vscode.window.showInputBox({ prompt: `인자 '${m[1]}' 값`, ignoreFocusOut: true });
    if (val === undefined) return null; // 사용자 취소
    out.push(val);
  }
  return out;
}

// 런타임별 실제 실행. 승인 게이트는 호출부(ask/orchestrate)에서 이미 처리한다.
// 반환: 사용자에게 보일 결과 요약.
async function executeHit(hit: Runnable): Promise<string> {
  const ex = parseExec(hit);
  const name = hit.intent || hit.id;
  switch (ex.kind) {
    case "vscode":
      await vscode.commands.executeCommand(ex.command, ...ex.args); // #2 인자 전달(invocation.args)
      return `실행: ${name}`;
    case "cli": {
      const argv = await fillPlaceholders(ex.argv); // #1 CLI 실행 + #2 인자 채움
      if (!argv) return "취소됨";
      const cmd = argv.join(" ");
      const t = cliTerminal();
      t.show();
      t.sendText(cmd, false); // 자동 실행 대신 터미널에 '준비' — 검토 후 Enter (안전)
      vscode.window.showInformationMessage(`PAESTRO: 터미널에 준비됨 (검토 후 Enter): ${cmd}`);
      return `CLI 준비: ${cmd}`;
    }
    case "rest": {
      const req = `${ex.method} ${ex.url}`;
      let host = "";
      try {
        host = new URL(ex.url).host;
      } catch {
        /* host 파싱 실패 → 미허용 취급 */
      }
      const allow = vscode.workspace.getConfiguration("paestro").get<string[]>("rest.allowlist", []);
      const allowed = !!host && allow.some((h) => h === "*" || host === h || host.endsWith(`.${h}`));

      // 허용목록에 없으면: 자동 호출 금지 → 표시/복사/설정안내만 (기본 안전)
      if (!allowed) {
        const pick = await vscode.window.showInformationMessage(
          `PAESTRO: REST는 허용목록에 없어 자동 실행하지 않습니다. 요청: ${req}`,
          "복사",
          "설정 열기"
        );
        if (pick === "복사") await vscode.env.clipboard.writeText(req);
        else if (pick === "설정 열기")
          await vscode.commands.executeCommand("workbench.action.openSettings", "paestro.rest.allowlist");
        return `REST 표시: ${req}`;
      }

      // 허용목록 → 매 호출 승인(외부 서비스에 실제 전송)
      const go = await vscode.window.showWarningMessage(
        `외부 REST 호출: ${req}\n외부 서비스에 실제 요청이 전송됩니다. 실행할까요?`,
        { modal: true },
        "실행"
      );
      if (go !== "실행") return "취소됨";

      const headers: Record<string, string> = { "Content-Type": "application/json" };
      let body: string | undefined;
      if (ex.method !== "GET" && ex.method !== "DELETE") {
        body = await vscode.window.showInputBox({ prompt: "요청 본문(JSON, 선택)", ignoreFocusOut: true });
      }
      // 인증값은 매 호출 입력받고 저장하지 않음(시크릿 비저장)
      const auth = await vscode.window.showInputBox({
        prompt: "Authorization 헤더 값(선택 · 저장 안 함)",
        password: true,
        ignoreFocusOut: true,
      });
      if (auth) headers["Authorization"] = auth;

      try {
        const r = await httpRequest(ex.method, ex.url, headers, body);
        await vscode.window.showInformationMessage(`PAESTRO: REST ${r.status} — ${req}`);
        return `REST ${r.status}`;
      } catch (e) {
        vscode.window.showErrorMessage(`PAESTRO: REST 실패 — ${e}`);
        return "REST 오류";
      }
    }
    case "mcp":
      await vscode.window.showInformationMessage(
        `PAESTRO: MCP 도구 ${ex.server}/${ex.tool} — MCP 클라이언트 연결이 필요해 자동 실행은 아직 미지원입니다.`
      );
      return `MCP 안내: ${ex.server}/${ex.tool}`;
    default:
      vscode.window.showInformationMessage(`PAESTRO: [${ex.runtime}] 런타임은 아직 실행을 지원하지 않습니다: ${name}`);
      return `미지원(${ex.runtime})`;
  }
}

// [4] 오케스트레이터 흐름: 요구 → 후보 번호 메뉴 → [5]게이트 → 실행.
async function ask(): Promise<void> {
  if (!(await engine.health())) {
    vscode.window.showErrorMessage("PAESTRO: 엔진에 연결할 수 없습니다. 엔진을 먼저 실행하세요.");
    return;
  }
  const query = await vscode.window.showInputBox({
    prompt: "무엇을 하고 싶나요?",
    placeHolder: "예: 이 파일 lint 자동 수정",
  });
  if (!query) return;

  const hits = await engine.retrieve(query, 4);
  const items: MenuItem[] = hits.map((h, i) => ({
    label: `${i + 1}. ${h.intent || h.id}`,
    description: h.plugin,
    detail: `${h.side_effects} · ${h.id}`,
    hit: h,
  }));
  items.push({ label: "5. 직접 지정 / 설정…", detail: "모든 명령에서 직접 고르기" });

  const pick = await vscode.window.showQuickPick(items, {
    title: `"${query}" 에 맞는 도구`,
    placeHolder: "번호를 고르세요",
  });
  if (!pick) return;

  // 5번(직접 지정) → 명령 팔레트로
  if (!pick.hit) {
    await vscode.commands.executeCommand("workbench.action.showCommands");
    return;
  }

  // [5] 하네스 게이트: 되돌릴 수 없는 작업은 승인 요구
  if (pick.hit.side_effects === "irreversible") {
    const ok = await vscode.window.showWarningMessage(
      `되돌릴 수 없는 작업입니다: ${pick.hit.intent}. 실행할까요?`,
      { modal: true },
      "실행"
    );
    if (ok !== "실행") return;
  }

  await executeHit(pick.hit);
}

// [4] 멀티스텝 오케스트레이션: 복합 요구 → 단계 계획 → 승인 게이트 → 순차 실행.
async function orchestrate(): Promise<void> {
  if (!(await engine.health())) {
    vscode.window.showErrorMessage("PAESTRO: 엔진에 연결할 수 없습니다. 엔진을 먼저 실행하세요.");
    return;
  }
  const query = await vscode.window.showInputBox({
    prompt: "복합 요구를 입력하세요 (여러 단계 가능)",
    placeHolder: "예: lint 자동수정하고 커밋 메시지 생성",
  });
  if (!query) return;

  const plan = await engine.orchestrate(query, 3);
  if (!plan.steps.length) {
    vscode.window.showWarningMessage("PAESTRO: 계획을 세우지 못했습니다.");
    return;
  }

  const lines = plan.steps.map(
    (s) => `${s.n}. ${s.step} → ${s.chosen ? s.chosen.intent : "(매칭 없음)"}${s.chosen?.needs_approval ? "  ⚠승인" : ""}`
  );
  const header = `실행 계획 (${plan.steps.length}단계${plan.needs_approval ? `, 승인 ${plan.needs_approval}건` : ""})`;
  const runAll = await vscode.window.showInformationMessage(
    `${header}\n\n${lines.join("\n")}`,
    { modal: true },
    "전체 실행"
  );
  if (runAll !== "전체 실행") return;

  let ran = 0;
  for (const s of plan.steps) {
    if (!s.chosen) continue;
    if (s.chosen.needs_approval) {
      const ok = await vscode.window.showWarningMessage(
        `되돌릴 수 없는 작업: ${s.chosen.intent}. 실행할까요?`,
        { modal: true },
        "실행"
      );
      if (ok !== "실행") continue;
    }
    await executeHit(s.chosen); // 런타임별 실행(vscode 실행 · cli 터미널 준비 · rest/mcp 안내)
    ran++;
  }
  vscode.window.showInformationMessage(`PAESTRO: 계획 실행 완료 (${ran}/${plan.steps.length}단계)`);
}

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("paestro.ask", () =>
      ask().catch((e) => vscode.window.showErrorMessage(`PAESTRO: ${e}`))
    ),
    vscode.commands.registerCommand("paestro.reindex", () =>
      reindex().catch((e) => vscode.window.showErrorMessage(`PAESTRO: ${e}`))
    ),
    vscode.commands.registerCommand("paestro.orchestrate", () =>
      orchestrate().catch((e) => vscode.window.showErrorMessage(`PAESTRO: ${e}`))
    )
  );
}

export function deactivate(): void {}
