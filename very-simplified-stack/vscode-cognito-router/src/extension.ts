import * as vscode from 'vscode';
import * as http from 'http';
import * as url from 'url';

export function activate(context: vscode.ExtensionContext) {
    console.log('vscode-cognito-router extension is now active');

    // Register Cognito Commands
    const commands = [
        { id: 'vscode-cognito-router.routeTask', title: 'Route Task', handler: () => handleRouteTask() },
        { id: 'vscode-cognito-router.planTask', title: 'Plan Task', handler: () => handlePlanTask() },
        { id: 'vscode-cognito-router.fixSelection', title: 'Fix Selection', handler: () => handleFixSelection() },
        { id: 'vscode-cognito-router.explainSelection', title: 'Explain Selection', handler: () => handleExplainSelection() },
        { id: 'vscode-cognito-router.reviewDiff', title: 'Review Diff', handler: () => handleReviewDiff() },
        { id: 'vscode-cognito-router.routeDiagnostics', title: 'Route Diagnostics', handler: () => handleRouteDiagnostics() },
        { id: 'vscode-cognito-router.cancelTask', title: 'Cancel Task', handler: () => handleCancelTask() },
        { id: 'vscode-cognito-router.retryTask', title: 'Retry Task', handler: () => handleRetryTask() },
        { id: 'vscode-cognito-router.escalateTask', title: 'Escalate Task', handler: () => handleEscalateTask() },
        { id: 'vscode-cognito-router.openWorktree', title: 'Open Worktree', handler: () => handleOpenWorktree() },
        { id: 'vscode-cognito-router.viewHistory', title: 'View History', handler: () => handleViewHistory() }
    ];

    for (const cmd of commands) {
        const disposable = vscode.commands.registerCommand(cmd.id, cmd.handler);
        context.subscriptions.push(disposable);
    }
}

async function handleRouteTask() {
    const taskInput = await vscode.window.showInputBox({
        prompt: "Describe the programming task you want to execute with Cognito/Codex"
    });
    if (!taskInput) { return; }

    const editorContext = getEditorContext();
    if (!editorContext.workspace_folder) {
        vscode.window.showErrorMessage("Please open a workspace before routing a task.");
        return;
    }

    // Call routing preview endpoint
    vscode.window.showInformationMessage(`Routing task with Cognito: ${taskInput}...`);
    try {
        const preview = await callPreviewRoute(taskInput, editorContext);
        showRoutingPanel(taskInput, preview);
    } catch (e: any) {
        vscode.window.showErrorMessage(`Routing preview failed: ${e.message}`);
    }
}

function handlePlanTask() {
    vscode.window.showInformationMessage('Cognito: Planning Task...');
}

function handleFixSelection() {
    vscode.window.showInformationMessage('Cognito: Fixing selection...');
}

function handleExplainSelection() {
    vscode.window.showInformationMessage('Cognito: Explaining selection...');
}

function handleReviewDiff() {
    vscode.window.showInformationMessage('Cognito: Reviewing current diff...');
}

function handleRouteDiagnostics() {
    vscode.window.showInformationMessage('Cognito: Routing active diagnostics...');
}

function handleCancelTask() {
    vscode.window.showInformationMessage('Cognito: Cancelling active task...');
}

function handleRetryTask() {
    vscode.window.showInformationMessage('Cognito: Retrying task...');
}

function handleEscalateTask() {
    vscode.window.showInformationMessage('Cognito: Escalating task...');
}

function handleOpenWorktree() {
    vscode.window.showInformationMessage('Cognito: Opening worktree folder...');
}

function handleViewHistory() {
    vscode.window.showInformationMessage('Cognito: Viewing task history...');
}

// ══════════════════════════════════════════════════════════════════════════════
// Helpers
// ══════════════════════════════════════════════════════════════════════════════

interface EditorContext {
    workspace_folder: string;
    active_file: string;
    selected_language: string;
    selected_text: string;
    diagnostics_summary: any;
    git_status_summary: string;
}

function getEditorContext(): EditorContext {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || "";
    const activeEditor = vscode.window.activeTextEditor;
    const activeFile = activeEditor?.document.fileName || "";
    const selectedLanguage = activeEditor?.document.languageId || "";
    const selectedText = activeEditor?.document.getText(activeEditor.selection) || "";

    // Grab VS Code diagnostics
    const diagnostics = activeEditor ? vscode.languages.getDiagnostics(activeEditor.document.uri) : [];
    const diagnosticsSummary = diagnostics.map(d => ({
        message: d.message,
        severity: d.severity,
        range: d.range
    }));

    return {
        workspace_folder: workspaceFolder,
        active_file: activeFile,
        selected_language: selectedLanguage,
        selected_text: selectedText,
        diagnostics_summary: diagnosticsSummary,
        git_status_summary: "clean"
    };
}

async function callPreviewRoute(userTask: str, editor: EditorContext): Promise<any> {
    const config = vscode.workspace.getConfiguration('cognito');
    const backendUrl = config.get<string>('backendUrl') || 'http://localhost:8000';

    const payload = {
        user_task: userTask,
        workspace_folder: editor.workspace_folder,
        active_file: editor.active_file,
        selected_language: editor.selected_language,
        diagnostics_summary: editor.diagnostics_summary,
        git_status_summary: editor.git_status_summary
    };

    return new Promise((resolve, reject) => {
        const parsedUrl = url.parse(`${backendUrl}/api/agent/route/preview`);
        const data = JSON.stringify(payload);

        const options = {
            hostname: parsedUrl.hostname,
            port: parsedUrl.port ? parseInt(parsedUrl.port) : 80,
            path: parsedUrl.path,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(data)
            }
        };

        const req = http.request(options, (res) => {
            let body = '';
            res.setEncoding('utf8');
            res.on('data', (chunk) => body += chunk);
            res.on('end', () => {
                if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
                    try {
                        resolve(JSON.parse(body));
                    } catch (e) {
                        reject(e);
                    }
                } else {
                    reject(new Error(`Server returned status code ${res.statusCode}: ${body}`));
                }
            });
        });

        req.on('error', (e) => reject(e));
        req.write(data);
        req.end();
    });
}

function showRoutingPanel(userTask: string, preview: any) {
    const panel = vscode.window.createWebviewPanel(
        'cognitoRouter',
        'Cognito Route Decision',
        vscode.ViewColumn.Two,
        { enableScripts: true }
    );

    panel.webview.html = getWebviewContent(userTask, preview);

    // Handle messages from the webview (overrides, approvals, execution starts)
    panel.webview.onDidReceiveMessage(message => {
        switch (message.command) {
            case 'startExecution':
                vscode.window.showInformationMessage(`Starting execution on ${message.tier} tier...`);
                // Calls backend to start execution
                break;
            case 'cancelTask':
                vscode.window.showInformationMessage('Task execution cancelled by user.');
                panel.dispose();
                break;
        }
    });
}

function getWebviewContent(userTask: string, preview: any): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cognito Routing Decision</title>
    <style>
        body { font-family: sans-serif; padding: 20px; color: var(--vscode-foreground); background-color: var(--vscode-editor-background); }
        h1, h2 { color: var(--vscode-textLink-foreground); }
        .card { border: 1px solid var(--vscode-widget-border); padding: 15px; margin-bottom: 20px; border-radius: 5px; }
        .badge { display: inline-block; padding: 5px 10px; border-radius: 3px; font-weight: bold; margin-right: 10px; }
        .high { background-color: #ff3b30; color: white; }
        .medium { background-color: #ff9500; color: white; }
        .low { background-color: #34c759; color: white; }
        .btn { background-color: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; padding: 10px 15px; cursor: pointer; border-radius: 3px; font-weight: bold; }
        .btn:hover { background-color: var(--vscode-button-hoverBackground); }
        .btn-secondary { background-color: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground); margin-left: 10px; }
        select { background-color: var(--vscode-settings-selectBackground); color: var(--vscode-settings-selectForeground); border: 1px solid var(--vscode-settings-selectBorder); padding: 5px; margin-right: 15px; }
    </style>
</head>
<body>
    <h1>Cognito Intelligent Router</h1>

    <div class="card">
        <h2>User Task</h2>
        <p>${userTask}</p>
    </div>

    <div class="card">
        <h2>Routing Decision Preview</h2>
        <p><strong>Executor:</strong> ${preview.executor}</p>
        <p><strong>Logical Tier:</strong> <span id="current-tier">${preview.logical_tier}</span></p>
        <p><strong>Resolved Model:</strong> ${preview.resolved_model_identifier}</p>
        <p><strong>Risk Assessment:</strong> <span class="badge ${preview.risk}">${preview.risk.toUpperCase()}</span></p>
        <p><strong>Confidence:</strong> ${(preview.confidence * 100).toFixed(0)}%</p>
        <p><strong>Mode:</strong> ${preview.mode}</p>
    </div>

    <div class="card">
        <h2>Policy & Sandbox</h2>
        <p><strong>Sandbox Allowed Writable Roots:</strong> ${preview.execution_policy?.sandbox?.allowed_writable_roots?.join(', ') || 'N/A'}</p>
        <p><strong>Approval Policy:</strong> Require approval for shell: ${preview.execution_policy?.approval?.require_approval_for_shell ? 'YES' : 'NO'}</p>
    </div>

    <div class="card">
        <h2>Decision Reasons</h2>
        <ul>
            ${preview.reasons.map((r: string) => `<li>${r}</li>`).join('')}
        </ul>
    </div>

    <div class="card">
        <h2>Manual Override / Actions</h2>
        <label for="tier-override">Select Route Override:</label>
        <select id="tier-override" onchange="updateSelection()">
            <option value="Automatic" selected>Automatic (${preview.logical_tier})</option>
            <option value="Local">Local (Ollama)</option>
            <option value="Luna">Luna (Codex Economy)</option>
            <option value="Terra">Terra (Codex Balanced)</option>
            <option value="Sol">Sol (Codex Maximum-Capability)</option>
        </select>

        <button class="btn" onclick="startExecution()">Approve & Start Execution</button>
        <button class="btn btn-secondary" onclick="cancelTask()">Cancel</button>
    </div>

    <script>
        const vscode = acquireVsCodeApi();

        function updateSelection() {
            const sel = document.getElementById('tier-override').value;
            document.getElementById('current-tier').innerText = sel === 'Automatic' ? '${preview.logical_tier}' : sel.toLowerCase();
        }

        function startExecution() {
            const override = document.getElementById('tier-override').value;
            vscode.postMessage({
                command: 'startExecution',
                tier: override
            });
        }

        function cancelTask() {
            vscode.postMessage({
                command: 'cancelTask'
            });
        }
    </script>
</body>
</html>`;
}

export function deactivate() {}
type str = string;
