import * as vscode from "vscode";
import * as engine from "./engineClient";

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

// invocation(JSON 문자열)에서 실행할 vscode command 추출. 다른 런타임이거나 파싱 실패 시 처리.
// 반환: {command} 실행 가능 · {runtime} 확장에서 실행 불가(REST/CLI/MCP) · null 알 수 없음
function resolveExec(hit: engine.Hit): { command?: string; runtime?: string } {
  try {
    const inv = JSON.parse(hit.invocation || "{}");
    if (inv.type === "vscode" && inv.command) return { command: inv.command };
    if (inv.type && inv.type !== "vscode") return { runtime: inv.type };
  } catch {
    /* 구형 데이터 등 → id 폴백 */
  }
  if (hit.id.startsWith("vscode.")) return { command: hit.id.replace(/^vscode\./, "") };
  return { runtime: hit.id.split(".")[0] };
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

  const exec = resolveExec(pick.hit);
  if (!exec.command) {
    vscode.window.showInformationMessage(
      `PAESTRO: 이 도구는 [${exec.runtime ?? "?"}] 런타임이라 확장에서 직접 실행할 수 없습니다: ${pick.hit.intent}`
    );
    return;
  }
  await vscode.commands.executeCommand(exec.command);
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
    const exec = resolveExec(s.chosen);
    if (!exec.command) {
      vscode.window.showInformationMessage(`PAESTRO: ${s.n}단계 [${exec.runtime ?? "?"}]는 확장에서 직접 실행 불가 — 건너뜀`);
      continue;
    }
    if (s.chosen.needs_approval) {
      const ok = await vscode.window.showWarningMessage(
        `되돌릴 수 없는 작업: ${s.chosen.intent}. 실행할까요?`,
        { modal: true },
        "실행"
      );
      if (ok !== "실행") continue;
    }
    await vscode.commands.executeCommand(exec.command);
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
