import * as path from "path";
import * as fs from "fs";

export function resolveTrustedExecutable(executableName: string, protectedRoot?: string): string {
  // Simple trusted executable finder that sanitizes the PATH
  const rawPath = process.env.PATH || "";
  const paths = rawPath.split(path.delimiter);

  // Filter out paths that are inside protectedRoot to prevent loop "scan-in-scan"
  const safePaths = paths.filter(p => {
    if (!protectedRoot) return true;
    try {
      const canonicalPath = fs.realpathSync(p);
      const canonicalRoot = fs.realpathSync(protectedRoot);
      return !(canonicalPath === canonicalRoot || canonicalPath.startsWith(canonicalRoot + path.sep));
    } catch {
      return true;
    }
  });

  for (const p of safePaths) {
    const fullPath = path.join(p, executableName);
    if (fs.existsSync(fullPath)) {
      // Ignore batch/cmd scripts on Windows
      if (process.platform === "win32" && (fullPath.endsWith(".bat") || fullPath.endsWith(".cmd"))) {
        continue;
      }
      return fs.realpathSync(fullPath);
    }
  }

  return executableName;
}
