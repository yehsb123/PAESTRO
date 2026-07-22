import * as vscode from "vscode";

const ENGINE = "http://127.0.0.1:8756";

// 실행 런타임에서 설치된 확장의 command 를 capability 로 수집 (parse 단계).
// tools/scan.js 의 파일 스캔과 동일 계약이지만, 여기선 VS Code API 로 직접 열람한다.
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
  const capabilities = collectCapabilities();
  const res = await fetch(`${ENGINE}/index`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ capabilities }),
  });
  const json = (await res.json()) as { indexed: number; total: number };
  vscode.window.showInformationMessage(`PAESTRO: ${json.indexed}개 색인 (총 ${json.total})`);
}

async function ask(): Promise<void> {
  const query = await vscode.window.showInputBox({ prompt: "무엇을 하고 싶나요?", placeHolder: "예: 이 파일 lint 자동 수정" });
  if (!query) return;

  const res = await fetch(`${ENGINE}/retrieve`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query, k: 5 }),
  });
  const { hits } = (await res.json()) as { hits: Array<any> };
  if (!hits?.length) {
    vscode.window.showWarningMessage("PAESTRO: 맞는 도구를 찾지 못했습니다. 먼저 재색인을 실행하세요.");
    return;
  }

  const pick = await vscode.window.showQuickPick(
    hits.map((h) => ({
      label: h.intent ?? h.id,
      description: h.plugin,
      detail: `${h.side_effects} · ${h.id}`,
      hit: h,
    })),
    { title: `"${query}" 에 맞는 도구`, placeHolder: "실행할 도구를 고르세요" }
  );
  if (!pick) return;

  // invocation 은 엔진에서 문자열로 직렬화돼 돌아온다 → command id 추출
  const command: string = pick.hit.id.replace(/^vscode\./, "");

  if (pick.hit.side_effects === "irreversible") {
    const ok = await vscode.window.showWarningMessage(
      `되돌릴 수 없는 작업입니다: ${pick.label}. 실행할까요?`,
      { modal: true },
      "실행"
    );
    if (ok !== "실행") return;
  }

  await vscode.commands.executeCommand(command);
}

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("paestro.ask", () => ask().catch((e) => vscode.window.showErrorMessage(`PAESTRO: ${e}`))),
    vscode.commands.registerCommand("paestro.reindex", () => reindex().catch((e) => vscode.window.showErrorMessage(`PAESTRO: ${e}`)))
  );
}

export function deactivate(): void {}
