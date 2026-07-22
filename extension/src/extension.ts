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

  const hits = await engine.orchestrate(query, 4);
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

  const command = pick.hit.id.replace(/^vscode\./, "");
  await vscode.commands.executeCommand(command);
}

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("paestro.ask", () =>
      ask().catch((e) => vscode.window.showErrorMessage(`PAESTRO: ${e}`))
    ),
    vscode.commands.registerCommand("paestro.reindex", () =>
      reindex().catch((e) => vscode.window.showErrorMessage(`PAESTRO: ${e}`))
    )
  );
}

export function deactivate(): void {}
