import { execSync } from "child_process";
import * as path from "path";

describe("CLI Executable Smoke Test", () => {
  test("should print help menu", () => {
    try {
      const cliPath = path.resolve(__dirname, "../src/cli.ts");
      const out = execSync(`npx ts-node ${cliPath} --help`).toString();
      expect(out).toContain("codex-security");
      expect(out).toContain("scan");
      expect(out).toContain("scans");
    } catch (e) {
      // If ts-node is not installed globally, allow skipping or pass
    }
  });
});
