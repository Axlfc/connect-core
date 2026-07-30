import { CodexSecurity, OutputInsideProtectedRootError, AuthenticationRequiredError } from "../src/index";
import * as path from "path";
import * as fs from "fs";

describe("CodexSecurity API Orchestrator", () => {
  let codex: CodexSecurity;

  beforeEach(() => {
    codex = new CodexSecurity();
  });

  test("should raise OutputInsideProtectedRootError if output dir lies inside protected target path", () => {
    const targetPath = path.resolve(__dirname);
    const options = { outputDir: path.join(targetPath, "nested") };

    expect(() => {
      codex.run({ path: targetPath, type: "full" }, options);
    }).toThrow(OutputInsideProtectedRootError);
  });

  test("should raise AuthenticationRequiredError if no API keys are present", () => {
    const originalKey = process.env.OPENAI_API_KEY;
    delete process.env.OPENAI_API_KEY;
    delete process.env.CODEX_API_KEY;

    const targetPath = path.resolve(__dirname);
    const options = { outputDir: path.resolve(process.cwd(), "external-output-dir") };

    expect(() => {
      codex.run({ path: targetPath, type: "full" }, options);
    }).toThrow(AuthenticationRequiredError);

    // Restore
    if (originalKey) {
      process.env.OPENAI_API_KEY = originalKey;
    }
  });

  test("should run full scan successfully when properly authenticated", () => {
    process.env.OPENAI_API_KEY = "sk-mock-key-for-unit-testing";
    const targetPath = path.resolve(__dirname);
    const outputDir = path.resolve(process.cwd(), "external-test-output-success");

    const result = codex.run({ path: targetPath, type: "full" }, { outputDir });
    expect(result.success).toBe(true);
    expect(result.findingsCount).toBeGreaterThanOrEqual(1);
    expect(fs.existsSync(result.outputFilePath)).toBe(true);

    // Clean up
    if (fs.existsSync(outputDir)) {
      fs.rmSync(outputDir, { recursive: true });
    }
  });
});
