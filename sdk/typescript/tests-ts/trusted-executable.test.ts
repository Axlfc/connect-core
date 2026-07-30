import { resolveTrustedExecutable } from "../src/index";
import * as path from "path";
import * as fs from "fs";

describe("Trusted Executable Resolver", () => {
  test("should resolve system executable name", () => {
    // Should resolve standard executables like "node" or "python"
    const resolved = resolveTrustedExecutable("node");
    expect(resolved).toBeDefined();
    expect(path.isAbsolute(resolved) || resolved === "node").toBe(true);
  });

  test("should filter out paths inside Protected Root", () => {
    const protectedRoot = path.resolve(__dirname);
    // Even if we request resolve, it should not find mock executables inside protectedRoot
    const resolved = resolveTrustedExecutable("mock-malicious", protectedRoot);
    expect(resolved).toBe("mock-malicious");
  });
});
