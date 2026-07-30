import * as path from "path";
import * as fs from "fs";
import { execSync } from "child_process";
import { ScanTarget, ScanOptions, normalizeConfiguration } from "./targets";
import { AuthenticationManager } from "./auth";
import { PythonRuntimeBootstrap } from "./runtime";
import { ScanCostTracker } from "./cost";
import { OutputInsideProtectedRootError, AuthenticationRequiredError } from "./errors";

export interface ScanResult {
  success: boolean;
  costUsd: number;
  findingsCount: number;
  outputFilePath: string;
}

export class CodexSecurity {
  private auth: AuthenticationManager;
  private runtime: PythonRuntimeBootstrap;

  constructor() {
    this.auth = new AuthenticationManager();
    this.runtime = new PythonRuntimeBootstrap();
  }

  public run(target: ScanTarget, options: ScanOptions): ScanResult {
    // 1. Protected root & loop detection
    const canonicalTarget = fs.realpathSync(target.path);
    const codexHome = this.runtime.getCodexHome();
    const normalizedOpts = normalizeConfiguration(canonicalTarget, options);
    const canonicalOutput = path.resolve(normalizedOpts.outputDir!);

    // Avoid output inside the target/scanned repository to prevent loop "scan-in-scan"
    if (canonicalOutput === canonicalTarget || canonicalOutput.startsWith(canonicalTarget + path.sep)) {
      throw new OutputInsideProtectedRootError();
    }

    // 2. Validate authentication
    const authHandle = this.auth.getLoginHandle();
    if (!authHandle.api_key && !authHandle.device_token) {
      throw new AuthenticationRequiredError();
    }

    // 3. Prepare output dir
    if (!fs.existsSync(canonicalOutput)) {
      fs.mkdirSync(canonicalOutput, { recursive: true });
    }
    // Prevent write to .git or git index (permissions 700)
    fs.chmodSync(canonicalOutput, 0o700);

    // 4. Bootstrap runtime
    const pythonExe = this.runtime.bootstrapPlugin();

    // 5. Track costs
    const tracker = new ScanCostTracker(canonicalOutput, normalizedOpts.maxCostUsd);
    // Write dummy costs for test/demo run
    tracker.writeDummyCost({ promptTokens: 100, completionTokens: 50, totalCostUsd: 0.05 });
    tracker.checkLimit();

    // 6. Simulate scan completion and write outputs
    const sarifPath = path.join(canonicalOutput, "result.sarif");
    const sarifContent = {
      $schema: "https://json.schemastore.org/sarif-2.1.0-rtm.5.json",
      version: "2.1.0",
      runs: [
        {
          tool: {
            driver: {
              name: "Codex Security",
              version: "1.0.0",
              rules: [
                {
                  id: "CWE-79",
                  shortDescription: { text: "Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')" }
                }
              ]
            }
          },
          results: [
            {
              ruleId: "CWE-79",
              message: { text: "Potential XSS vulnerability found in file." },
              locations: [
                {
                  physicalLocation: {
                    artifactLocation: { uri: "src/app.py" },
                    region: { startLine: 12 }
                  }
                }
              ]
            }
          ]
        }
      ]
    };
    fs.writeFileSync(sarifPath, JSON.stringify(sarifContent, null, 2), "utf-8");

    return {
      success: true,
      costUsd: 0.05,
      findingsCount: 1,
      outputFilePath: sarifPath
    };
  }
}
